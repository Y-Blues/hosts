"""
Host: a URL mount prefix served from one filesystem directory, with priority and
optional HTTP Basic Auth. See spec (2026-09-15-hosts-design.md) for the simplifications
versus the legacy model (single `directory`, no `type`/`core`/pyscript fields).

`cross_origin_isolated` (added for ycappuccino-client, see its README's "Risques d'execution
navigateur" (a)): when true, HostServlet adds Cross-Origin-Opener-Policy: same-origin and
Cross-Origin-Embedder-Policy: require-corp to every response served under this mount - required
for SharedArrayBuffer, itself required by a pthread-enabled Pyodide build. Defaults to false:
these headers can break loading cross-origin resources (e.g. a pyscript/Pyodide CDN) that do not
send compatible Cross-Origin-Resource-Policy/CORS headers, so it must be an explicit, informed
opt-in per mount, never the default. See README.md for the full tension.
"""

from ycappuccino.api.decorators import Item, Property
from ycappuccino.api.models import Model
from ycappuccino.core.decorator_app import App


@App(name="ycappuccino_hosts")
@Item(collection="hosts", name="host", plural="hosts")
class Host(Model):

    def __init__(self, a_dict: dict | None = None) -> None:
        super().__init__(a_dict)
        self._path = None
        self._directory = None
        self._priority = 0
        self._secure = False
        self._cross_origin_isolated = False

    @Property(name="path")
    def path(self, a_value: str) -> None:
        self._path = a_value

    @Property(name="directory")
    def directory(self, a_value: str) -> None:
        self._directory = a_value

    @Property(name="priority", type="integer")
    def priority(self, a_value: int) -> None:
        self._priority = a_value

    @Property(name="secure", type="boolean")
    def secure(self, a_value: bool) -> None:
        self._secure = a_value

    @Property(name="cross_origin_isolated", type="boolean")
    def cross_origin_isolated(self, a_value: bool) -> None:
        self._cross_origin_isolated = a_value
