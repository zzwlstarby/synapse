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
# -*- coding: utf-8 -*

from twisted.internet import defer

from synapse.types import RoomName
from base import RestServlet, InvalidHttpRequestError


class ClientDirectoryServer(RestServlet):
    PATTERN = re.compile("^/ds/room/(?P<room_name>[^/]*)$")

    def on_GET(self, request, room_name):
        # TODO(erikj): Handle request
        pass

    def on_PUT(self, request, room_name):
        # TODO(erikj): Exceptions
        content = json.loads(request.content.read())

        room_name_obj = RoomName.from_string(room_name, self.hs)

        room_id = content["room_id"]
        servers = content["servers"]

        # TODO(erikj): Check types.

        # TODO(erikj): Handle request
