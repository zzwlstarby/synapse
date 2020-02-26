with import <nixpkgs> {};

python37.withPackages (ps: with ps; [ phonenumbers canonicaljson pymacaroons psycopg2 psutil parameterized pillow lxml pysaml2 bleach service-identity six frozendict pip idna pyasn1-modules netaddr jsonschema pynacl pyyaml pyopenssl mock bcrypt jinja2 msgpack attrs twisted pyasn1 treq sortedcontainers daemonize unpaddedbase64 ])
