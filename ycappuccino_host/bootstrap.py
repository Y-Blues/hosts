#app="all"
from ycappuccino_host.models.host import Host
from ycappuccino_core.api import IActivityLogger,  YCappuccino
from ycappuccino_storage.api import IManager, IBootStrap
from ycappuccino_core.decorator_app import Layer

import logging
from pelix.ipopo.decorators import ComponentFactory, Requires, Validate, Invalidate, Property, Provides, Instantiate


_logger = logging.getLogger(__name__)


@ComponentFactory('AccountBootStrapClientPath-Factory')
@Provides(specifications=[IBootStrap.name, YCappuccino.name])
@Requires("_log", IActivityLogger.name, spec_filter="'(name=main)'")
@Requires("_manager_host", IManager.name, spec_filter="'(item_id=host)'")
@Property("_id", "id", "core")
@Instantiate("AccountBootStrapClientPath")
@Layer(name="ycappuccino_host")
class AccountBootStrapClientPath(IBootStrap):

    def __init__(self):
        super(IBootStrap, self).__init__();


        self._manager_host = None
        self._log =None
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
        w_client_path_pyscript_core.subpath("endpoints_storage/client_pyscript_core")
        w_client_path_pyscript_core.priority(1)
        w_client_path_pyscript_core.type("pyscript")
        w_client_path_pyscript_core.core(True)
        w_client_path_pyscript_core.secure(False)

        self._manager_host.up_sert_model("client_pyscript_core", w_client_path_pyscript_core, w_subject)

    @Validate
    def validate(self, context):
        self._log.info("AccountBootStrap validating")
        try:
            self.bootstrap()
        except Exception as e:
            self._log.error("AccountBootStrapClientPath Error {}".format(e))
            self._log.exception(e)

        self._log.info("AccountBootStrapClientPath validated")

    @Invalidate
    def invalidate(self, context):
        self._log.info("AccountBootStrapClientPath invalidating")
        try:
            pass
        except Exception as e:
            self._log.error("AccountBootStrap Error {}".format(e))
            self._log.exception(e)
        self._log.info("AccountBootStrapClientPath invalidated")
