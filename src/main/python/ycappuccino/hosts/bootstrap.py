""""
    boot start default host provided by the application
    TODO review if we need a default one
"""

from ycappuccino.api.proxy.api import YCappuccinoRemote
from ycappuccino.hosts.models.host import Host
from ycappuccino.api.core.api import IActivityLogger
from ycappuccino.api.storage.api import IManager, IBootStrap
from ycappuccino.core.decorator_app import Layer

import logging
from pelix.ipopo.decorators import (
    ComponentFactory,
    Requires,
    Validate,
    Invalidate,
    Property,
    Provides,
    Instantiate,
)


_logger = logging.getLogger(__name__)


@ComponentFactory("BootStrapClientPath-Factory")
@Provides(specifications=[YCappuccinoRemote.__name__, IBootStrap.__name__])
@Requires("_log", IActivityLogger.__name__, spec_filter="'(name=main)'")
@Requires("_manager_host", IManager.__name__, spec_filter="'(item_id=host)'")
@Property("_id", "id", "core")
@Instantiate("BootStrapClientPath")
@Layer(name="ycappuccino_host")
class BootStrapClientPath(IBootStrap):

    def __init__(self):
        super(BootStrapClientPath, self).__init__()

        self._manager_host = None
        self._log = None
        self._id = "core"

    def get_id(self):
        return self._id

    def bootstrap(self):

        w_subject = self.get_token_subject("bootstrap", "system")

        w_client_path_default = Host()
        w_client_path_default.id("default")
        w_client_path_default.path("/")
        w_client_path_default.subpath("client")
        w_client_path_default.priority(0)
        w_client_path_default.secure(False)

        self._manager_host.up_sert_model("default", w_client_path_default, w_subject)

        w_client_path_pyscript_core = Host()
        w_client_path_pyscript_core.id("client_pyscript_core")
        w_client_path_pyscript_core.path("/pyscriptcore")
        w_client_path_pyscript_core.subpath("endpoint_crud/client_pyscript_core")
        w_client_path_pyscript_core.priority(1)
        w_client_path_pyscript_core.type("pyscript")
        w_client_path_pyscript_core.core(True)
        w_client_path_pyscript_core.secure(False)

        self._manager_host.up_sert_model(
            "client_pyscript_core", w_client_path_pyscript_core, w_subject
        )

    @Validate
    def validate(self, context):
        self._log.info("BootStrapClientPath validating")
        try:
            self.bootstrap()
        except Exception as e:
            self._log.error("BootStrapClientPath Error {}".format(e))
            self._log.exception(e)

        self._log.info("BootStrapClientPath validated")

    @Invalidate
    def invalidate(self, context):
        self._log.info("BootStrapClientPath invalidating")
        try:
            pass
        except Exception as e:
            self._log.error("AccountBootStrap Error {}".format(e))
            self._log.exception(e)
        self._log.info("BootStrapClientPath invalidated")
