"""
TODO review and move it
component that allow load pyscript and the framewor in client side.

"""

from ycappuccino.api.core import IActivityLogger, IService
from ycappuccino.api.decorators import get_bundle_model_ordered
from ycappuccino.api.hosts import IClobReplaceService

import logging
from pelix.ipopo.decorators import (
    ComponentFactory,
    Requires,
    Provides,
    BindField,
    UnbindField,
    Instantiate,
)

import glob

from ycappuccino.api.proxy import YCappuccinoRemote
from ycappuccino.core.decorator_app import Layer

_logger = logging.getLogger(__name__)


@ComponentFactory("PyScriptIndexReplaceService-Factory")
@Requires("_log", IActivityLogger.__name__, spec_filter="'(name=main)'")
@Requires("_services", specification=IService.__name__, aggregate=True, optional=True)
@Provides(specifications=[YCappuccinoRemote.__name__, IClobReplaceService.__name__])
@Instantiate("PyScriptIndexReplaceService")
@Layer(name="ycappuccino_host")
class PyScriptIndexReplaceService(IClobReplaceService):

    def __init__(self):
        super(IClobReplaceService, self).__init__()
        self._services = None
        self._map_services = {}
        self._log = None

    @staticmethod
    def extension():
        return ".html"

    def replace_content(self, a_in, a_path, a_client_path):
        """return out string with applyance of replacement"""
        w_out = a_in
        list_python_bundles = []
        list_python_files = []
        for w_client_path in a_client_path.get_path():
            w_list = glob.glob(w_client_path + "/**/*.py", recursive=True)

            for w_file in w_list:
                if "__init__" not in w_file:
                    w_in_index_path = w_file.replace(w_client_path, ".")
                    list_python_files.append(w_in_index_path)
                    list_python_bundles.append(
                        w_in_index_path.replace("/", ".")[2:].replace(".py", "")
                    )

        w_bundle_models_loaded = get_bundle_model_ordered()

        for w_bundle_model_loaded in w_bundle_models_loaded:
            list_python_files.append(w_bundle_model_loaded.replace(".", "/") + ".py")
            list_python_bundles.append(w_bundle_model_loaded)

        w_joint_list_python = '","'.join(list_python_files)
        w_joint_list_python_bundles = '","'.join(list_python_bundles)
        if w_joint_list_python != "":
            w_out = w_out.replace("${list_python_files}", w_joint_list_python)
        else:
            w_out = w_out.replace(',"${list_python_files}"', "")

        if w_joint_list_python_bundles != "":
            w_out = w_out.replace("${list_python_bundles}", w_joint_list_python_bundles)
        else:
            w_out = w_out.replace("${list_python_bundles}", "")

        return w_out

    @BindField("_services")
    def bind_services(self, field, a_service, a_service_reference):
        w_service = a_service.get_name()
        self._map_services[w_service] = a_service

    @UnbindField("_services")
    def unbind_services(self, field, a_service, a_service_reference):
        w_service = a_service.get_name()
        self._map_services[w_service] = None
