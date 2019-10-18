# -*- coding: utf-8 -*-
# Copyright 2014-2016 OpenMarket Ltd
# Copyright 2018-2019 New Vector Ltd
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
import platform
import re

import synapse
from synapse.http.server import JsonResource
from synapse.http.servlet import RestServlet
from synapse.util.versionstring import get_version_string

logger = logging.getLogger(__name__)


def historical_admin_path_patterns(path_regex):
    """Returns the list of patterns for an admin endpoint, including historical ones

    This is a backwards-compatibility hack. Previously, the Admin API was exposed at
    various paths under /_matrix/client. This function returns a list of patterns
    matching those paths (as well as the new one), so that existing scripts which rely
    on the endpoints being available there are not broken.

    Note that this should only be used for existing endpoints: new ones should just
    register for the /_synapse/admin path.
    """
    return list(
        re.compile(prefix + path_regex)
        for prefix in (
            "^/_synapse/admin/v1",
            "^/_matrix/client/api/v1/admin",
            "^/_matrix/client/unstable/admin",
            "^/_matrix/client/r0/admin",
        )
    )


async def assert_requester_is_admin(auth, request) -> None:
    """Verify that the requester is an admin user

    WARNING: MAKE SURE YOU AWAIT THE RESULT!

    Args:
        auth (synapse.api.auth.Auth):
        request (twisted.web.server.Request): incoming request

    Returns:
        Deferred

    Raises:
        AuthError if the requester is not an admin
    """
    requester = await auth.get_user_by_req(request)
    await assert_user_is_admin(auth, requester.user)


async def assert_user_is_admin(auth, user_id) -> None:
    """Verify that the given user is an admin user

    WARNING: MAKE SURE YOU AWAIT ON THE RESULT!

    Args:
        auth (synapse.api.auth.Auth):
        user_id (UserID):

    Raises:
        AuthError if the user is not an admin
    """

    is_admin = await auth.is_server_admin(user_id)
    if not is_admin:
        raise AuthError(403, "You are not a server admin")


class VersionServlet(RestServlet):
    PATTERNS = (re.compile("^/_synapse/admin/v1/server_version$"),)

    def __init__(self, hs):
        self.res = {
            "server_version": get_version_string(synapse),
            "python_version": platform.python_version(),
        }

    def on_GET(self, request):
        return 200, self.res


class AdminRestResource(JsonResource):
    """The REST resource which gets mounted at /_synapse/admin"""

    def __init__(self, hs):
        JsonResource.__init__(self, hs, canonical_json=False)
        register_servlets(hs, self)


def register_servlets(hs, http_server):
    """
    Register all the admin servlets.
    """
    from synapse.rest.admin.rooms import PurgeRoomServlet
    from synapse.rest.admin.users import UserAdminServlet
    from synapse.rest.admin.server_notice_servlet import SendServerNoticeServlet

    register_servlets_for_client_rest_resource(hs, http_server)
    PurgeRoomServlet(hs).register(http_server)
    SendServerNoticeServlet(hs).register(http_server)
    VersionServlet(hs).register(http_server)
    UserAdminServlet(hs).register(http_server)


def register_servlets_for_client_rest_resource(hs, http_server):
    """Register only the servlets which need to be exposed on /_matrix/client/xxx"""
    from synapse.rest.admin.groups import DeleteGroupAdminRestServlet
    from synapse.rest.admin.media import (
        ListMediaInRoom,
        register_servlets_for_media_repo,
    )
    from synapse.rest.admin.rooms import (
        PurgeHistoryRestServlet,
        PurgeHistoryStatusRestServlet,
        PurgeRoomServlet,
        ShutdownRoomRestServlet,
    )
    from synapse.rest.admin.users import (
        AccountValidityRenewServlet,
        DeactivateAccountRestServlet,
        GetUsersPaginatedRestServlet,
        ResetPasswordRestServlet,
        SearchUsersRestServlet,
        UserAdminServlet,
        UserRegisterServlet,
        UsersRestServlet,
        WhoisRestServlet,
    )

    WhoisRestServlet(hs).register(http_server)
    PurgeHistoryStatusRestServlet(hs).register(http_server)
    DeactivateAccountRestServlet(hs).register(http_server)
    PurgeHistoryRestServlet(hs).register(http_server)
    UsersRestServlet(hs).register(http_server)
    ResetPasswordRestServlet(hs).register(http_server)
    GetUsersPaginatedRestServlet(hs).register(http_server)
    SearchUsersRestServlet(hs).register(http_server)
    ShutdownRoomRestServlet(hs).register(http_server)
    UserRegisterServlet(hs).register(http_server)
    DeleteGroupAdminRestServlet(hs).register(http_server)
    AccountValidityRenewServlet(hs).register(http_server)

    # Load the media repo ones if we're using them. Otherwise load the servlets which
    # don't need a media repo (typically readonly admin APIs).
    if hs.config.can_load_media_repo:
        register_servlets_for_media_repo(hs, http_server)
    else:
        ListMediaInRoom(hs).register(http_server)

    # don't add more things here: new servlets should only be exposed on
    # /_synapse/admin so should not go here. Instead register them in AdminRestResource.


__all__ = [
    "register_servlets",
    "register_servlets_for_client_rest_resource",
    "assert_requester_is_admin",
]
