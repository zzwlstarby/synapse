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

from synapse.api.errors import SynapseError
from synapse.http.servlet import RestServlet
from synapse.rest.admin import assert_user_is_admin, historical_admin_path_patterns


class DeleteGroupAdminRestServlet(RestServlet):
    """Allows deleting of local groups
    """

    PATTERNS = historical_admin_path_patterns("/delete_group/(?P<group_id>[^/]*)")

    def __init__(self, hs):
        self.group_server = hs.get_groups_server_handler()
        self.is_mine_id = hs.is_mine_id
        self.auth = hs.get_auth()

    async def on_POST(self, request, group_id):
        requester = await self.auth.get_user_by_req(request)
        await assert_user_is_admin(self.auth, requester.user)

        if not self.is_mine_id(group_id):
            raise SynapseError(400, "Can only delete local groups")

        await self.group_server.delete_group(group_id, requester.user.to_string())
        return 200, {}
