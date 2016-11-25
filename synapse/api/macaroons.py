# -*- coding: utf-8 -*-
# Copyright 2014 - 2016 OpenMarket Ltd
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

import pymacaroons

import synapse.api.errors
import synapse.util.stringutils


def get_caveat_from_macaroon(macaroon, key, operator="="):
    """
    Search for a particular caveat in a macaroon

    Args:
        macaroon (pymacaroons.Macaroon): deserialised macaroon
        key: the key of the caveat to look for
        operator: the operator to look for

    Returns:
        str: the suffix (after the operator) of the *first* matching caveat
        None: if no caveat matched
    """
    prefix = "%s %s " % (key, operator)
    for caveat in macaroon.caveats:
        if caveat.caveat_id.startswith(prefix):
            return caveat.caveat_id[len(prefix):]
    return None


class Macaroons(object):
    def __init__(self, hs):
        """
        Args:
            hs (synapse.server.HomeServer):
        """
        self._clock = hs.get_clock()
        self._config = hs.config
        self._location = hs.config.server_name

    #
    # Macaroon generation utilities
    #

    def generate_access_token(self, user_id, extra_caveats=None):
        extra_caveats = extra_caveats or []
        macaroon = self._generate_base_macaroon(user_id)
        macaroon.add_first_party_caveat("type = access")
        for caveat in extra_caveats:
            macaroon.add_first_party_caveat(caveat)
        return macaroon.serialize()

    def generate_refresh_token(self, user_id):
        m = self._generate_base_macaroon(user_id)
        m.add_first_party_caveat("type = refresh")
        # Important to add a nonce, because otherwise every refresh token for a
        # user will be the same.
        m.add_first_party_caveat("nonce = %s" % (
            synapse.util.stringutils.random_string_with_symbols(16),
        ))
        return m.serialize()

    def generate_short_term_login_token(self, user_id, duration_in_ms=(2 * 60 * 1000)):
        macaroon = self._generate_base_macaroon(user_id)
        macaroon.add_first_party_caveat("type = login")
        now = self._clock.time_msec()
        expiry = now + duration_in_ms
        macaroon.add_first_party_caveat("time < %d" % (expiry,))
        return macaroon.serialize()

    def generate_delete_pusher_token(self, user_id):
        macaroon = self._generate_base_macaroon(user_id)
        macaroon.add_first_party_caveat("type = delete_pusher")
        return macaroon.serialize()

    def _generate_base_macaroon(self, user_id):
        macaroon = pymacaroons.Macaroon(
            location=self._location,
            identifier="key",
            key=self._config.macaroon_secret_key)
        macaroon.add_first_party_caveat("gen = 1")
        macaroon.add_first_party_caveat("user_id = %s" % (user_id,))
        return macaroon

    #
    # Macaroon validation utilities
    #

    def validate_access_token_and_extract_user_id(self, macaroon_str, rights):
        """
        Validate an access_token for the current request

        Args:
            macaroon_str(str): The serialised macaroon

            rights(str): The kind of token required (e.g. "access", "refresh",
                              "delete_pusher")

        Returns:
            (str, boolean): user id, is_guest

        Raises:
            ValueError if there is no user_id caveat in the macaroon
            MacaroonVerificationFailedException if the macaroon is not valid for
            the current request
        """
        macaroon = pymacaroons.Macaroon.deserialize(macaroon_str)
        user_id = self._validate_macaroon(
            macaroon,
            rights,
            verify_expiry=self._config.expire_access_token,
        )
        guest = False
        for caveat in macaroon.caveats:
            if caveat.caveat_id == "guest = true":
                guest = True
        return user_id, guest

    def validate_short_term_login_token_and_get_user_id(self, login_token):
        macaroon = pymacaroons.Macaroon.deserialize(login_token)

        user_id = self._validate_macaroon(
            macaroon,
            type_string="login",
        )
        return user_id

    def _validate_macaroon(self, macaroon, type_string,
                           verify_expiry=True):
        """
        Extract a user ID from a Macaroon, and validate it for the current
        request

        Args:
            macaroon(pymacaroons.Macaroon): The macaroon to validate

            type_string(str): The kind of token required (e.g. "access", "refresh",
                              "delete_pusher")

            verify_expiry(bool): Whether to verify whether the macaroon has expired.
                This should really always be True, but there exist access tokens
                in the wild which expire when they should not, so we can't
                enforce expiry yet.

        Returns:
            str: user id

        Raises:
            ValueError if there is no user_id caveat in the macaroon
            MacaroonVerificationFailedException if the macaroon is not valid for
            the current request
        """

        user_id = get_caveat_from_macaroon(macaroon, "user_id")
        if user_id is None:
            raise ValueError("No user caveat in macaroon")

        v = pymacaroons.Verifier()

        # the verifier runs a test for every caveat on the macaroon, to check
        # that it is met for the current request. Each caveat must match at
        # least one of the predicates specified by satisfy_exact or
        # specify_general.
        v.satisfy_exact("gen = 1")
        v.satisfy_exact("type = " + type_string)
        v.satisfy_exact("user_id = %s" % user_id)
        v.satisfy_exact("guest = true")
        if verify_expiry:
            v.satisfy_general(lambda c: self._verify_expiry(c))
        else:
            v.satisfy_general(lambda c: c.startswith("time < "))

        v.verify(macaroon, self._config.macaroon_secret_key)

        return user_id

    def _verify_expiry(self, caveat):
        prefix = "time < "
        if not caveat.startswith(prefix):
            return False
        expiry = int(caveat[len(prefix):])
        return self._clock.time_msec() < expiry


