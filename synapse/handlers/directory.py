# Copyright 2014 matrix.org
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
# -*- coding: utf-8 -*-

from twisted.internet import defer
from ._base import BaseHandler

import logging
import json

logger = logging.getLogger(__name__)


class DirectoryHandler(BaseHandler):

    def __init__(self, hs):
        super(DirectoryHandler, self).__init__(hs)
        self.hs = hs
        self.clock = hs.get_clock()

    def create_association(self, room_name, room_id, servers):
        # TODO(erikj): Do auth.

        if not room_name.is_mine:
            raise Exception("foo")  # TODO(erikj): Change this.

        # TODO(erikj): Add transactions.

        # TODO(erikj): Check if there is a current association.

        yield self.store.create_room_name_association(
            room_name,
            room_id,
            servers
        )

    @defer.inlineCallbacks
    def get_association(self, room_name):
        # TODO(erikj): Do auth

        if room_name.is_mine:
            result = yield self.store.get_association_from_room_name(
                room_name.to_string()
            )
        else:
            # TODO(erikj): Hit out to remote HS.
            pass

        # TODO(erikj): Handle result

        if not result:
            defer.returnValue({})
            return

        room_id = result.room_id
        servers = results.servers

        defer.returnValue({
            "room_id": room_id,
            "servers": servers,
        })
        return
