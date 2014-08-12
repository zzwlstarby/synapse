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
"""Contains exceptions and error codes."""

import logging

class CodeMessageException(Exception):
    """An exception with code and message attributes."""

    def __init__(self, code, msg):
        logging.error("%s: %s, %s", type(self).__name__, code, msg)
        super(CodeMessageException, self).__init__("%d: %s" % (code, msg))
        self.code = code
        self.msg = msg


class SynapseError(CodeMessageException):
    """A base error which can be caught for all synapse events."""
    pass


class RoomError(SynapseError):
    """An error raised when a room event fails."""
    pass


class RegistrationError(SynapseError):
    """An error raised when a registration event fails."""
    pass


class AuthError(SynapseError):
    """An error raised when there was a problem authorising an event."""
    pass


class EventStreamError(SynapseError):
    """An error raised when there a problem with the event stream."""
    pass


class LoginError(SynapseError):
    """An error raised when there was a problem logging in."""
    pass


class StoreError(SynapseError):
    """An error raised when there was a problem storing some data."""
    pass


def cs_error(msg, code=0, **kwargs):
    """ Utility method for constructing an error response for client-server
    interactions.

    Args:
        msg (str): The error message.
        code (int): The error code.
        kwargs : Additional keys to add to the response.
    Returns:
        A dict representing the error response JSON.
    """
    err = {"error": msg, "errcode": code}
    for key, value in kwargs.iteritems():
        err[key] = value
    return err
