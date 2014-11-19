from twisted.internet import defer, reactor
from synapse.app import homeserver
from synapse.crypto.event_signing import add_hashes_and_signatures, compute_event_signature
from synapse.util.stringutils import random_string

import json
import shutil
import sqlite3
import sys
import time


def cursor_to_dict(cursor):
    col_headers = list(column[0] for column in cursor.description)
    results = list(
        dict(zip(col_headers, row)) for row in cursor.fetchall()
    )
    return results


def run(conn):
    c = conn.cursor()

    c.execute(
        "SELECT e.*, s.state_key FROM events as e "
        "LEFT JOIN state_events as s "
        "ON e.event_id = s.event_id "
        "ORDER BY topological_ordering ASC, stream_ordering ASC"
    )

    raw_rows = cursor_to_dict(c)

    rows = []
    for r in raw_rows:
        d = dict(r)
        unrec = d["unrecognized_keys"]
        d.update(json.loads(unrec))
        del d["unrecognized_keys"]
        d["content"] = json.loads(d["content"])
        rows.append(d)

    rows[:] = [r for r in rows if r["user_id"] != '_homeserver_' and r["type"] not in ["m.room.invite_join"]]

    rooms = set([row["room_id"] for row in rows])

    print "No. rooms: %d" %(len(rooms),)
    print "No. events: %d" %(len(rows),)

    uncreated_rooms = rooms
    names = {}
    aliases = {}
    rooms_to_events = {}
    for r in rows:
        rooms_to_events.setdefault(r["room_id"], []).append(r)

        if r["type"] == "m.room.create":
            uncreated_rooms.discard(r["room_id"])

        r.pop("depth", None)
        #r.pop("topological_ordering", None)
        #r.pop("stream_ordering", None)
        r.pop("age_ts", None)
        r.pop("processed", None)
        r.pop("origin", None)
        r.pop("prev_events", None)
        r.pop("auth_events", None)
        r.pop("prev_state", None)
        r.pop("is_state", None)
        r.pop("power_level", None)
        r.pop("outlier", None)
        r.pop("destinations", None)
        r.pop("required_power_level", None)

        if "origin_server_ts" not in r:
            r["origin_server_ts"] = r.pop("ts", 0)
        else:
            r.pop("ts", 0)

        r["content"].pop("hsob_ts", None)

        if "state_key" in r and r["state_key"] is None:
            del r["state_key"]

        if r["type"] == "m.room.name":
            nm = r["content"].get("name", None)
            if nm:
                names[r["room_id"]] = nm
        elif r["type"] == "m.room.aliases":
            if r["user_id"].startswith("@"):
                r["user_id"] = r["user_id"].split(":", 1)[1]
            al = r["content"].get("aliases")
            if al:
                aliases.setdefault(r["room_id"], []).extend(al)
        elif r["type"] == "m.room.member":
            r["content"].pop("prev", None)

    print "No. uncreated_rooms: %d" % (len(uncreated_rooms), )

    uncreated_local_rooms = [r for r in uncreated_rooms if r.endswith("matrix.org")]

    print "No. uncreated local rooms: %d" % (len(uncreated_local_rooms),)


    for room_id, events in rooms_to_events.items():
        topo = 0
        stream = 0
        to_move = []

        for e in events:
            if e["type"] == "m.room.member" and e["content"]["membership"] == "join" and e["topological_ordering"] in [0, 1]:
                to_move.append(e)

        for e in to_move:
            events.remove(e)

        to_move = sorted(to_move, key=lambda e: e["stream_ordering"])

        for t in to_move:
            for i, e in enumerate(events):
                if e["stream_ordering"] > t["stream_ordering"]:
                    events.insert(i, t)
                    inserted = True
                    break
            else:
                events.append(t)

#        for e in events:
#            e.pop("topological_ordering", None)
#            e.pop("stream_ordering", None)




    def create_event_id(domain="matrix.org"):
        return "$%s%s:%s" % (str(int(time.time()*1000)), random_string(5), domain,)

    for room_id in uncreated_local_rooms:
        creator = rooms_to_events[room_id][0]["user_id"]
        if room_id in ["!cURbafjkfsMDVwdRDQ:matrix.org"]:
            creator = "@erikj:matrix.org"
        print "Room %s creator: %s" % (room_id, creator)

        creator_origin = creator.split(":", 1)[1]

        create = {
            "origin_server_ts": 0,
            "event_id": create_event_id(creator_origin),
            "state_key": "",
            "content": {
                "creator": creator,
            },
            "room_id": room_id,
            "user_id": creator,
            "type": "m.room.create"
        }

        join = {
            "origin_server_ts": 0,
            "event_id": create_event_id(creator_origin),
            "state_key": creator,
            "content": {
                "membership": "join"
            },
            "room_id": room_id,
            "user_id": creator,
            "type": "m.room.member"
        }

        join_rule = "public" if room_id in ["!cURbafjkfsMDVwdRDQ:matrix.org", "!XqBunHwQIXUiqCaoxq:matrix.org", "!vfFxDRtZSSdspfTSEr:matrix.org"] else "invite"

        join_rules = {
            "origin_server_ts": 0,
            "event_id": create_event_id(creator_origin),
            "state_key": "",
            "content": {
                "join_rule": join_rule,
            },
            "room_id": room_id,
            "user_id": creator,
            "type": "m.room.join_rules",
        }

        # rooms_to_events[room_id] = [create, join, join_rules] + rooms_to_events[room_id]

        prefix_events = [create, join, join_rules]

        # Now we need to add all the extra invite and joins.
        events = rooms_to_events[room_id]

        joined = set([creator])
        to_join = set()
        for e in events:
            if e["type"] == "m.room.member":
                joined.add(e["user_id"])
            elif e["user_id"] not in joined:
                if e["user_id"].startswith("@"):
                    to_join.add(e["user_id"])

        joins = []
        for u in to_join:
            if join_rule == "invite":
                invite = {
                    "origin_server_ts": 0,
                    "event_id": create_event_id(creator_origin),
                    "state_key": u,
                    "content": {
                        "membership": "invite"
                    },
                    "room_id": room_id,
                    "user_id": creator,
                    "type": "m.room.member"
                }

                prefix_events.append(invite)

            origin = u.split(":", 1)[1]

            join = {
                "origin_server_ts": 0,
                "event_id": create_event_id(origin),
                "state_key": u,
                "content": {
                    "membership": "join"
                },
                "room_id": room_id,
                "user_id": u,
                "type": "m.room.member"
            }

            prefix_events.append(join)

        rooms_to_events[room_id] = prefix_events + rooms_to_events[room_id]


    # Fix room alias positions in graph
    pos_stats = {}
    for room_id, events in rooms_to_events.items():
        if room_id in uncreated_rooms and room_id not in uncreated_local_rooms:
            continue

        joined = set()
        joined_domains = set()
        join_pos = None
        alias = None
        alias_pos = None

        mis_ordered = []
        for i, event in enumerate(events):
            if event["type"] not in ["m.room.create", "m.room.member"]:
                if event["user_id"] not in joined | joined_domains:
                    mis_ordered.append(event)
                    if event["type"] == "m.room.message":
                        print json.dumps(event, indent=4)
            if event["type"] == "m.room.member":
                if event["state_key"].startswith("@"):
                    joined.add(event["state_key"])
                    joined_domains.add(event["state_key"].split(':', 1)[1])
                else:
                    joined_domains.add(event["state_key"])

        for e in mis_ordered:
            events.remove(e)

        users_to_find = set([e["user_id"] for e in mis_ordered])

        found_users = {}
        found_domains = {}
        if mis_ordered:
            for i, event in enumerate(events):
                if event["type"] == "m.room.member":
                    user = event["state_key"]
                    domain = user.split(':', 1)[1]
                    if event["state_key"] in users_to_find or domain in users_to_find:
                        domain = user.split(':', 1)[1]

                        users_to_find.discard(user)
                        users_to_find.discard(domain)

                        if user not in found_users:
                            found_users[user] = i

                        if domain not in found_domains:
                            found_domains[domain] = i

            assert len(users_to_find) == 0, "users_to_find not empty: %s %s" % (users_to_find, room_id, )

            print "Room %s mis ordered: %d" % (room_id, len(mis_ordered),)
            for event in reversed(mis_ordered):
                sender = event["user_id"]
                pos = found_users[sender] if sender in found_users else found_domains[sender]
                events.insert(pos + 1, event)
                pos_stats[event["type"]] = pos_stats.get(event["type"], 0) + 1

    print json.dumps(pos_stats, indent=4)


    # Fix power level events:
    for room_id, events in rooms_to_events.items():
        if events[0]["type"] != "m.room.create":
            continue

        creator = events[0]["content"]["creator"]

        prev = {
            "redact": 50,
            "events_default": 0,
            "users": {creator: 100},
            "ban": 50,
            "state_default": 50,
            "events": {
                #"m.room.name": 50,
                #"m.room.power_levels": 50
            },
            "kick": 50,
            "users_default": 0
        }

        for i, event in enumerate(events):
            #if event["type"] in ["m.room.add_state_level", "m.room.ops_levels", "m.room.power_levels", "m.room.send_event_level"]:
            if event["type"] == "m.room.add_state_level":
                prev["state_default"] = event["content"]["level"]
                event["content"] = prev
            elif event["type"] == "m.room.ops_levels":
                if "redact_level" in event["content"]:
                    prev["redact"] = event["content"]["redact_level"]
                prev["ban"] = event["content"]["ban_level"]
                prev["kick"] = event["content"]["kick_level"]
                event["content"] = prev
            elif event["type"] == "m.room.power_levels":
                for k, v in event["content"].items():
                    if k.startswith("@"):
                        prev["users"][k] = int(v)
                    elif k == "default":
                        prev["users_default"] = int(v)
                event["content"] = prev
            elif event["type"] == "m.room.send_event_level":
                prev["events_default"] = event["content"]["level"]
                event["content"] = prev
            else:
                continue

            event["type"] = "m.room.power_levels"

            events[i] = event

    rooms_to_state = {}
    for r in rows:
        if "state_key" in r and r["state_key"] is not None:
            rooms_to_state.setdefault(r["room_id"], []).append(r)

    print "No. of loaclhost rooms: %d" % (len([r for r in rooms if "localhost" in r]),)
    print "Room hosts: %s" % (set([r.split(':', 1)[1] for r in rooms]),)

    print "Remote hosts: %s" % (set(r["user_id"].split(":",1)[1] for r in rows if "user_id" in r and ":" in r["user_id"]),)

    room_tables = [
        "context_depth",
        "current_state",
        "current_state_events",
        "events",
        "feedback",
        "pdu_backward_extremities",
        "pdu_destinations",
        "pdu_edges",
        "pdu_forward_extremities",
        "pdus",
        "redactions",
        "room_add_state_levels",
        "room_default_levels",
        "room_hosts",
        "room_join_rules",
        "room_memberships",
        "room_names",
        "room_ops_levels",
        "room_power_levels",
        "room_send_event_levels",
        "rooms",
        "state_events",
        "state_pdus",
        "topics",
        "transaction_id_to_pdu",
    ]

    shutil.copyfile("/home/erikj/temp/test/homeserver.db", "/home/erikj/temp/test/output.db")
    conn2 = sqlite3.connect("/home/erikj/temp/test/output.db")

    for table in room_tables:
        conn2.execute("DROP TABLE IF EXISTS %s" % table)
    conn2.execute("PRAGMA user_version = 0")
    conn2.commit()

    args = (
        "-H matrix.org "
        "-d /home/erikj/temp/test/output.db "
        "--signing-key-path /home/erikj/temp/keys/matrix.org.signing.key "
        "--tls-certificate-path /home/erikj/temp/keys/matrix.org.tls.crt "
        "--tls-private-key-path /home/erikj/temp/keys/matrix.org.tls.key "
        "--tls-dh-params-path /home/erikj/temp/keys/matrix.org.tls.dh "
        "--log-file hs-convert.log"
    )

    hs = homeserver.main(
        args.split(" "),
        run_http=False,
    )


    @defer.inlineCallbacks
    def process():
        print "Starting processing"

        store = hs.get_datastore()
        factory = hs.get_event_factory()
        state_handler = hs.get_state_handler()
        auth = hs.get_auth()

        # print "Rooms: %d" % (len(rooms_to_events.items()),)

        for room_id, events in rooms_to_events.items():
            exclude = [
                "!hgcQjHRQfJDyobDBWG:arasphere.net",
                "!LjXjnHjCGMeQfgzHpS:matrix.org",
                "!xoLPEcMZCAEBTCESgL:matrix.org",
                "!cTeEVrLNCKbSQBBeAh:matrix.org",
                "!EqLLhRGueYGTtKMhWB:matrix.org",
                "!QnFnIqmQGumwjwCUyb:matrix.org",
                #"!QyCHwajcREvYdSRFEY:matrix.org",
                # "!zOmsiVucpWbRRDjSwe:matrix.org", # matrix-internal
            ]
            if room_id in exclude:
                # Screw those rooms.
                continue

            #if room_id != "!zOmsiVucpWbRRDjSwe:matrix.org":
            #    continue

            if room_id in uncreated_rooms and room_id not in uncreated_local_rooms:
                # We're ignoring these
                print "Ignoring: %s" % (room_id,)
                continue

            print "Room: %s, events: %d" % (room_id, len(events),)
            #print json.dumps(events, indent=4)
            f = open(room_id,'w')
            f.write(json.dumps(events, indent=4))
            f.close()

            #print "No. of banbRxMxWT:matrix.org: %d" % (len([e for e in events if e["event_id"] == "banbRxMxWT@matrix.org"]),)
            #break

            t_snapshot = 0
            t_state = 0
            t_auth = 0
            t_persist = 0

            failures = 0

            i = 0
            for e in events:
                # print "Before: " + json.dumps(e, indent=4)

                e.pop("event_id", None)

                if "@" in e["user_id"]:
                    origin = e["user_id"].split(":", 1)[1]
                else:
                    origin = e["user_id"]

                e["event_id"] = create_event_id(origin)

                ev = factory.create_event(etype=e["type"], **e)


                start = time.clock()*1000
                snapshot = yield store.snapshot_room(ev)
                t_snapshot += time.clock()*1000 - start

                snapshot.fill_out_prev_events(ev)

                start = time.clock()*1000
                yield state_handler.annotate_event_with_state(ev)
                t_state += time.clock()*1000 - start

                start = time.clock()*1000
                yield auth.add_auth_events(ev)
                t_auth +=time.clock()*1000 - start

                add_hashes_and_signatures(
                    ev, "matrix.org", hs.config.signing_key[0]
                )

                if "jki.re" in ev.user_id:
                    s = compute_event_signature(ev, "jki.re", hs.config.signing_key[1])
                    ev.signatures.update(s)

                #print "After: " + json.dumps(ev.get_pdu_json(), indent=4)

                try:
                    auth.check(ev, raises=True)

                    start = time.clock()*1000
                    yield store.persist_event(ev)
                    t_persist += time.clock()*1000 - start
                except Exception as ex:
                    print "Failed event %s: %s" % (ev.event_id, ex)
                    failures += 1

                i += 1
                if i % 100 == 0:
                    print "%d/%d" % (i, len(events))
                    print "sn: %d, st: %d, a: %d, p: %d" % (t_snapshot, t_state, t_auth, t_persist, )
                    t_snapshot = 0
                    t_state = 0
                    t_auth = 0
                    t_persist = 0


                # print ""

            if failures:
                print "Failures %s: %d" % (room_id, failures,)

    @defer.inlineCallbacks
    def on_start():
        try:
            yield process()
        finally:
            reactor.stop()

    reactor.callLater(0, on_start)

    hs.run()

if __name__ == "__main__":
    # File is also used above
    conn = sqlite3.connect("/home/erikj/temp/test/homeserver.db")
    run(conn)
