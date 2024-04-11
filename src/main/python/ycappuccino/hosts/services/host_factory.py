"""
    host factory service that allow to create a host service regarding the host component stored.
"""

from ycappuccino_api.core.api import IActivityLogger
from src.main.python.proxy import YCappuccinoRemote
from ycappuccino_api.storage.api import IManager, IBootStrap
from ycappuccino_api.host.api import IHostFactory

import logging
from pelix.ipopo.decorators import (
    ComponentFactory,
    Requires,
    Validate,
    Invalidate,
    Provides,
    Instantiate,
    BindField,
    UnbindField,
)
from pelix.ipopo.constants import use_ipopo
from src.main.python.decorator_app import Layer

_logger = logging.getLogger(__name__)


@ComponentFactory("HostFactory-Factory")
@Provides(specifications=[YCappuccinoRemote.__name__, IHostFactory.__name__])
@Requires("_log", IActivityLogger.__name__, spec_filter="'(name=main)'")
@Requires("_manager_host", IManager.__name__, spec_filter="'(item_id=host)'")
@Requires(
    "_bootstraps", specification=IBootStrap.__name__, aggregate=True, optional=True
)
@Instantiate("HostFactory")
@Layer(name="ycappuccino_host")
class ClientPathFactory(IHostFactory):

    def __init__(self):
        super(IHostFactory, self).__init__()
        self._bootstraps = None
        self._manager_host = None
        self._map_boostrap = {}
        self._map_host = {}
        self._context = None
        self._log = None

    @BindField("_bootstraps")
    def bind_bootstrap(self, a_field, a_service, a_service_reference):
        if a_service is not None:
            self._map_boostrap[a_service.get_id()] = a_service
        self.create_hosts()

    @UnbindField("_bootstraps")
    def un_bind_bootstrap(self, a_field, a_service, a_service_reference):
        if a_service.get_id() in self._map_boostrap:
            del self._map_boostrap[a_service.get_id()]

    def create_host(self, a_model, a_bundle_context):

        if a_model._id not in self._map_host.keys():
            with use_ipopo(a_bundle_context) as ipopo:
                # use the iPOPO core service with the "ipopo" variable
                if "_subpath" in a_model.__dict__.keys():
                    ipopo.instantiate(
                        "Host-Factory",
                        "Host-{}".format(a_model._id),
                        {
                            "id": a_model._path,
                            "subpath": a_model._subpath,
                            "priority": a_model._priority,
                            "type": a_model.get_type(),
                            "core": a_model.is_core(),
                            "secure": a_model._secure,
                        },
                    )
                else:
                    ipopo.instantiate(
                        "Host-Factory",
                        "Host-{}".format(a_model._id),
                        {
                            "id": a_model._path,
                            "subpath": "",
                            "priority": a_model._priority,
                            "type": a_model.get_type(),
                            "core": a_model.is_core(),
                            "secure": a_model._secure,
                        },
                    )
                self._map_host[a_model._id] = True

    def create_hosts(self):
        if self._context is not None:
            w_models = self._manager_host.get_many("host", None)
            for w_model in w_models:
                self.create_host(w_model, self._context)

    @Validate
    def validate(self, context):
        self._log.info("HostFactory validating")
        self._context = context
        self.create_hosts()
        self._log.info("HostFactory validated")

    @Invalidate
    def invalidate(self, context):
        self._log.info("HostFactory invalidating")

        self._log.info("HostFactory invalidated")
