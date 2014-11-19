# -*- coding: utf-8 -*-
# Copyright 2014 OpenMarket Ltd
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

from ._base import SQLBaseStore

import time


class StateStore(SQLBaseStore):
    """ Keeps track of the state at a given event.

    This is done by the concept of `state groups`. Every event is a assigned
    a state group (identified by an arbitrary string), which references a
    collection of state events. The current state of an event is then the
    collection of state events referenced by the event's state group.

    Hence, every change in the current state causes a new state group to be
    generated. However, if no change happens (e.g., if we get a message event
    with only one parent it inherits the state group from its parent.)

    There are three tables:
      * `state_groups`: Stores group name, first event with in the group and
        room id.
      * `event_to_state_groups`: Maps events to state groups.
      * `state_groups_state`: Maps state group to state events.
    """

    def get_state_groups(self, event_ids, auth_only=False):
        """ Get the state groups for the given list of event_ids

        The return value is a dict mapping group names to lists of events.
        """

        def f(txn):
            if not event_ids:
                return {}

            sql = (
                "SELECT s.state_group, e.* FROM events as e "
                "INNER JOIN state_groups_state as s "
                "ON e.event_id = s.event_id "
                "INNER JOIN event_to_state_groups as es "
                "ON s.state_group = es.state_group "
                "WHERE "
            )

            sql = sql + " OR ".join(["es.event_id = ? " for _ in event_ids])

            c = txn.execute(sql, event_ids)
            ds = self.cursor_to_dict(c)

            if auth_only:
                ds[:] = [
                    (r.pop("state_group"), self._parse_event_from_row(r))
                    for r in ds
                ]
            else:
                ds[:] = [
                    (
                        r.pop("state_group"),
                        self._parse_events_txn(txn, [r])
                    )
                    for r in ds
                ]

            ret = {}
            for r in ds:
                ret.setdefault(r[0], []).append(r[1])

            return ret

        return self.runInteraction(
            "get_state_groups",
            f,
        )

    def store_state_groups(self, event):
        return self.runInteraction(
            "store_state_groups",
            self._store_state_groups_txn, event
        )

    def _store_state_groups_txn(self, txn, event):
        if not event.state_events:
            return

        state_group = event.state_group
        if not state_group:
            state_group = self._simple_insert_txn(
                txn,
                table="state_groups",
                values={
                    "room_id": event.room_id,
                    "event_id": event.event_id,
                },
                or_ignore=True,
            )

            for state in event.state_events.values():
                self._simple_insert_txn(
                    txn,
                    table="state_groups_state",
                    values={
                        "state_group": state_group,
                        "room_id": state.room_id,
                        "type": state.type,
                        "state_key": state.state_key,
                        "event_id": state.event_id,
                    },
                    or_ignore=True,
                )

        self._simple_insert_txn(
            txn,
            table="event_to_state_groups",
            values={
                "state_group": state_group,
                "event_id": event.event_id,
            },
            or_replace=True,
        )
