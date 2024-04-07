"""
    simple host service that is link to all host models instnaciate. it allow to retrieve in a component
    it provide a basic authentication if the file are secured.

"""

from ycappuccino_api.core.api import IActivityLogger, IConfiguration
from ycappuccino_api.host.api import IHost

import logging, os
from pelix.ipopo.decorators import (
    ComponentFactory,
    Requires,
    Validate,
    Invalidate,
    Property,
    Provides,
)

from src.main.python.proxy import YCappuccinoRemote
from src.main.python.decorator_app import Layer

import inspect
import base64


_logger = logging.getLogger(__name__)


@ComponentFactory("Host-Factory")
@Provides(specifications=[YCappuccinoRemote.__name__, IHost.__name__])
@Requires("_log", IActivityLogger.__name__, spec_filter="'(name=main)'")
@Requires("_config", IConfiguration.__name__)
@Property("_id", "id", "default")
@Property("_type", "type", "default")
@Property("_subpath", "subpath", "client")
@Property("_secure", "secure", False)
@Property("_core", "core", False)
@Property("_priority", "priority", 0)
@Layer(name="ycappuccino_host")
class Host(IHost):

    def __init__(self):
        super(IHost, self).__init__()
        self.path_core = inspect.getmodule(self).__file__.replace(
            "ycappuccino_host{0}services{0}host.py".format(os.path.sep), ""
        )
        self.path_app = inspect.getmodule(self).__file__.replace(
            "hosts{0}ycappuccino_host{0}services{0}host.py".format(os.path.sep), ""
        )
        self._log = None
        self._secure = None
        self._user = None
        self._pass = None
        self._id = None
        self._type = None
        self._priority = None
        self._subpath = None
        self._config = None
        self._core = None

    def get_path(self):
        w_path = [self.path_app + self._subpath, self.path_core + self._subpath]

        return w_path

    def get_priority(self):
        return self._priority

    def get_type(self):
        return self._type

    def is_core(self):
        return self._core

    def get_subpath(self):
        return self._subpath

    def get_ui_path(self):
        return self._id

    def is_auth(self):
        return self._secure

    def get_id(self):
        return self._id

    def load_configuration(self):
        if self._secure:
            self._user = self._config.get(self._id + ".login", "client_pyscript_core")
            self._pass = self._config.get(self._id + ".password", "1234")

    def check_auth(self, a_authorization):
        if a_authorization is not None and "Basic " in a_authorization:
            w_decode = base64.standard_b64decode(
                a_authorization.replace("Basic ", "")
            ).decode("ascii")
            if ":" in w_decode:
                w_user = w_decode.split(":")[0]
                w_pass = w_decode.split(":")[1]
                if w_user == self._user and w_pass == self._pass:
                    return True

        return False

    @Validate
    def validate(self, context):
        self._log.info("Host validating")
        self.load_configuration()

        self._log.info("Host validated")

    @Invalidate
    def invalidate(self, context):
        self._log.info("Host invalidating")

        self._log.info("Host invalidated")
