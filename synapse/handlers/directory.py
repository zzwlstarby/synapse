# -*- coding: utf-8 -*-

from twisted.internet import defer
from ._base import BaseHandler

from synapse.api.errors import SynapseError

import logging
import json
import urllib


logger = logging.getLogger(__name__)


# TODO(erikj): This needs to be factored out somewere
PREFIX = "/matrix/client/api/v1"


class DirectoryHandler(BaseHandler):

    def __init__(self, hs):
        super(DirectoryHandler, self).__init__(hs)
        self.hs = hs
        self.http_client = hs.get_http_client()
        self.clock = hs.get_clock()

    @defer.inlineCallbacks
    def create_association(self, room_alias, room_id, servers):
        # TODO(erikj): Do auth.

        if not room_alias.is_mine:
            raise SynapseError(400, "Room alias must be local")
            # TODO(erikj): Change this.

        # TODO(erikj): Add transactions.

        # TODO(erikj): Check if there is a current association.

        yield self.store.create_room_alias_association(
            room_alias,
            room_id,
            servers
        )

    @defer.inlineCallbacks
    def get_association(self, room_alias, local_only=False):
        # TODO(erikj): Do auth

        room_id = None
        if room_alias.is_mine:
            result = yield self.store.get_association_from_room_alias(
                room_alias
            )

            room_id = result.room_id
            servers = result.servers
        elif not local_only:
            path = "%s/ds/room/%s?local_only=1" % (
                PREFIX,
                urllib.quote(room_alias.to_string())
            )

            result = yield self.http_client.get_json(
                destination=room_alias.domain,
                path=path,
            )

            if "room_id" in result and "servers" in result:
                room_id = result["room_id"]
                servers = result["servers"]

        if not room_id:
            defer.returnValue({})
            return

        defer.returnValue({
            "room_id": room_id,
            "servers": servers,
        })
        return
