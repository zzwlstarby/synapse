import os

from twisted.web.static import File

import synapse
from synapse.api.urls import STATIC_PREFIX, WEB_CLIENT_PREFIX
from synapse.app._base import quit_with_error
from synapse.python_dependencies import CONDITIONAL_REQUIREMENTS


def build_static_resource_map(hs, resconfig):
    return {
        STATIC_PREFIX: File(
            os.path.join(os.path.dirname(synapse.__file__), "static")
        ),
    }


def build_webclient_resource_map(hs, resconfig):
    webclient_path = hs.get_config().web_client_location
    if not webclient_path:
        try:
            import syweb
        except ImportError:
            quit_with_error(
                "Could not find a webclient.\n\n"
                "Please either install the matrix-angular-sdk or configure\n"
                "the location of the source to serve via the configuration\n"
                "option `web_client_location`\n\n"
                "To install the `matrix-angular-sdk` via pip, run:\n\n"
                "    pip install '%(dep)s'\n"
                "\n"
                "You can also disable hosting of the webclient via the\n"
                "configuration option `web_client`\n"
                % {"dep": CONDITIONAL_REQUIREMENTS["web_client"].keys()[0]}
            )
        syweb_path = os.path.dirname(syweb.__file__)
        webclient_path = os.path.join(syweb_path, "webclient")
    # GZip is disabled here due to
    # https://twistedmatrix.com/trac/ticket/7678
    # (It can stay enabled for the API resources: they call
    # write() with the whole body and then finish() straight
    # after and so do not trigger the bug.
    # GzipFile was removed in commit 184ba09
    # res = GzipFile(webclient_path)  # TODO configurable?
    res = File(webclient_path)  # TODO configurable?

    return {
        WEB_CLIENT_PREFIX: res,
    }
