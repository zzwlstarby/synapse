# -*- coding: utf-8 -*-
# Copyright 2014-2016 OpenMarket Ltd
# Copyright 2018-2019 New Vector Ltd
# Copyright 2019 The Matrix.org Foundation C.I.C.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import logging
import re

from synapse.api.constants import Membership
from synapse.api.errors import Codes, NotFoundError, SynapseError
from synapse.http.servlet import (
    RestServlet,
    assert_params_in_dict,
    parse_json_object_from_request,
)
from synapse.rest.admin import (
    assert_requester_is_admin,
    assert_user_is_admin,
    historical_admin_path_patterns,
)
from synapse.types import create_requester

logger = logging.getLogger(__name__)


class PurgeRoomServlet(RestServlet):
    """Servlet which will remove all trace of a room from the database

    POST /_synapse/admin/v1/purge_room
    {
        "room_id": "!room:id"
    }

    returns:

    {}
    """

    PATTERNS = (re.compile("^/_synapse/admin/v1/purge_room$"),)

    def __init__(self, hs):
        """
        Args:
            hs (synapse.server.HomeServer): server
        """
        self.hs = hs
        self.auth = hs.get_auth()
        self.pagination_handler = hs.get_pagination_handler()

    async def on_POST(self, request):
        await assert_requester_is_admin(self.auth, request)

        body = parse_json_object_from_request(request)
        assert_params_in_dict(body, ("room_id",))

        await self.pagination_handler.purge_room(body["room_id"])

        return 200, {}


class ShutdownRoomRestServlet(RestServlet):
    """Shuts down a room by removing all local users from the room and blocking
    all future invites and joins to the room. Any local aliases will be repointed
    to a new room created by `new_room_user_id` and kicked users will be auto
    joined to the new room.
    """

    PATTERNS = historical_admin_path_patterns("/shutdown_room/(?P<room_id>[^/]+)")

    DEFAULT_MESSAGE = (
        "Sharing illegal content on this server is not permitted and rooms in"
        " violation will be blocked."
    )

    PERMISSION_CODE = "ROOM_SHUTDOWN"

    def __init__(self, hs):
        self.hs = hs
        self.store = hs.get_datastore()
        self.state = hs.get_state_handler()
        self._room_creation_handler = hs.get_room_creation_handler()
        self.event_creation_handler = hs.get_event_creation_handler()
        self.room_member_handler = hs.get_room_member_handler()
        self.auth = hs.get_auth()

    async def on_POST(self, request, room_id):

        authorised_by_token = await self.check_authorized_admin_token_in_use(request)

        if authorised_by_token:
            requester_user_id = self.hs.config.admin_token_user
        else:
            requester = await self.auth.get_user_by_req(request)
            await assert_user_is_admin(self.auth, requester.user)
            requester_user_id = requester.user.to_string()

        content = parse_json_object_from_request(request)
        assert_params_in_dict(content, ["new_room_user_id"])
        new_room_user_id = content["new_room_user_id"]

        room_creator_requester = create_requester(new_room_user_id)

        message = content.get("message", self.DEFAULT_MESSAGE)
        room_name = content.get("room_name", "Content Violation Notification")

        info = await self._room_creation_handler.create_room(
            room_creator_requester,
            config={
                "preset": "public_chat",
                "name": room_name,
                "power_level_content_override": {"users_default": -10},
            },
            ratelimit=False,
        )
        new_room_id = info["room_id"]

        logger.info(
            "Shutting down room %r, joining to new room: %r", room_id, new_room_id
        )

        # This will work even if the room is already blocked, but that is
        # desirable in case the first attempt at blocking the room failed below.
        await self.store.block_room(room_id, requester_user_id)

        users = await self.state.get_current_users_in_room(room_id)
        kicked_users = []
        failed_to_kick_users = []
        for user_id in users:
            if not self.hs.is_mine_id(user_id):
                continue

            logger.info("Kicking %r from %r...", user_id, room_id)

            try:
                target_requester = create_requester(user_id)
                await self.room_member_handler.update_membership(
                    requester=target_requester,
                    target=target_requester.user,
                    room_id=room_id,
                    action=Membership.LEAVE,
                    content={},
                    ratelimit=False,
                    require_consent=False,
                )

                await self.room_member_handler.forget(target_requester.user, room_id)

                await self.room_member_handler.update_membership(
                    requester=target_requester,
                    target=target_requester.user,
                    room_id=new_room_id,
                    action=Membership.JOIN,
                    content={},
                    ratelimit=False,
                    require_consent=False,
                )

                kicked_users.append(user_id)
            except Exception:
                logger.exception(
                    "Failed to leave old room and join new room for %r", user_id
                )
                failed_to_kick_users.append(user_id)

        await self.event_creation_handler.create_and_send_nonmember_event(
            room_creator_requester,
            {
                "type": "m.room.message",
                "content": {"body": message, "msgtype": "m.text"},
                "room_id": new_room_id,
                "sender": new_room_user_id,
            },
            ratelimit=False,
        )

        aliases_for_room = await self.store.get_aliases_for_room(room_id)

        await self.store.update_aliases_for_room(
            room_id, new_room_id, requester_user_id
        )

        return (
            200,
            {
                "kicked_users": kicked_users,
                "failed_to_kick_users": failed_to_kick_users,
                "local_aliases": aliases_for_room,
                "new_room_id": new_room_id,
            },
        )


class PurgeHistoryRestServlet(RestServlet):
    PATTERNS = historical_admin_path_patterns(
        "/purge_history/(?P<room_id>[^/]*)(/(?P<event_id>[^/]+))?"
    )

    def __init__(self, hs):
        """

        Args:
            hs (synapse.server.HomeServer)
        """
        self.pagination_handler = hs.get_pagination_handler()
        self.store = hs.get_datastore()
        self.auth = hs.get_auth()

    async def on_POST(self, request, room_id, event_id):
        await assert_requester_is_admin(self.auth, request)

        body = parse_json_object_from_request(request, allow_empty_body=True)

        delete_local_events = bool(body.get("delete_local_events", False))

        # establish the topological ordering we should keep events from. The
        # user can provide an event_id in the URL or the request body, or can
        # provide a timestamp in the request body.
        if event_id is None:
            event_id = body.get("purge_up_to_event_id")

        if event_id is not None:
            event = await self.store.get_event(event_id)

            if event.room_id != room_id:
                raise SynapseError(400, "Event is for wrong room.")

            token = await self.store.get_topological_token_for_event(event_id)

            logger.info("[purge] purging up to token %s (event_id %s)", token, event_id)
        elif "purge_up_to_ts" in body:
            ts = body["purge_up_to_ts"]
            if not isinstance(ts, int):
                raise SynapseError(
                    400, "purge_up_to_ts must be an int", errcode=Codes.BAD_JSON
                )

            stream_ordering = await self.store.find_first_stream_ordering_after_ts(ts)

            r = await self.store.get_room_event_after_stream_ordering(
                room_id, stream_ordering
            )
            if not r:
                logger.warn(
                    "[purge] purging events not possible: No event found "
                    "(received_ts %i => stream_ordering %i)",
                    ts,
                    stream_ordering,
                )
                raise SynapseError(
                    404, "there is no event to be purged", errcode=Codes.NOT_FOUND
                )
            (stream, topo, _event_id) = r
            token = "t%d-%d" % (topo, stream)
            logger.info(
                "[purge] purging up to token %s (received_ts %i => "
                "stream_ordering %i)",
                token,
                ts,
                stream_ordering,
            )
        else:
            raise SynapseError(
                400,
                "must specify purge_up_to_event_id or purge_up_to_ts",
                errcode=Codes.BAD_JSON,
            )

        purge_id = await self.pagination_handler.start_purge_history(
            room_id, token, delete_local_events=delete_local_events
        )

        return 200, {"purge_id": purge_id}


class PurgeHistoryStatusRestServlet(RestServlet):
    PATTERNS = historical_admin_path_patterns(
        "/purge_history_status/(?P<purge_id>[^/]+)"
    )

    def __init__(self, hs):
        """

        Args:
            hs (synapse.server.HomeServer)
        """
        self.pagination_handler = hs.get_pagination_handler()
        self.auth = hs.get_auth()

    async def on_GET(self, request, purge_id):
        await assert_requester_is_admin(self.auth, request)

        purge_status = self.pagination_handler.get_purge_status(purge_id)
        if purge_status is None:
            raise NotFoundError("purge id '%s' not found" % purge_id)

        return 200, purge_status.asdict()
