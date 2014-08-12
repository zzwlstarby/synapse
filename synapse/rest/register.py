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
"""This module contains REST servlets to do with registration: /register"""
from twisted.internet import defer

from base import RestServlet, InvalidHttpRequestError, client_path_pattern

import json
import urllib


class RegisterRestServlet(RestServlet):
    PATTERN = client_path_pattern("/register$")

    @defer.inlineCallbacks
    def on_POST(self, request):
        desired_user_id = None
        password = None
        try:
            register_json = json.loads(request.content.read())
            if "password" in register_json:
                password = register_json["password"]

            if type(register_json["user_id"]) == unicode:
                desired_user_id = register_json["user_id"]
                if urllib.quote(desired_user_id) != desired_user_id:
                    raise InvalidHttpRequestError(
                        400,
                        "User ID must only contain characters which do not " +
                        "require URL encoding.")
        except ValueError:
            defer.returnValue((400, "No JSON object."))
        except InvalidHttpRequestError as e:
            defer.returnValue((e.get_status_code(), e.get_response_body()))
        except KeyError:
            pass  # user_id is optional

        handler = self.handlers.registration_handler
        (user_id, token) = yield handler.register(
            localpart=desired_user_id,
            password=password)
        defer.returnValue((200,
                           {"user_id": user_id, "access_token": token}))

    def on_OPTIONS(self, request):
        return (200, {})


def register_servlets(hs, http_server):
    RegisterRestServlet(hs).register(http_server)
