"""
HostBootstrap: creates the default Host document served by HostServlet, the way a real
application would (the hosts library itself provides no default Host, see the design spec).
"""

import os

from ycappuccino.api.core_base import YCappuccinoComponent
from ycappuccino.api.storage import IManager
from ycappuccino.hosts.models.host import Host


class HostBootstrap(YCappuccinoComponent):

    def __init__(self, manager: IManager):
        self._manager = manager

    async def start(self):
        default_host = Host()
        default_host.id("default")
        default_host.path("/")
        default_host.directory(os.path.join(os.path.dirname(__file__), "..", "client"))
        default_host.priority(0)
        default_host.secure(False)
        await self._manager.up_sert_model(default_host, subject=None)

    async def stop(self):
        pass
