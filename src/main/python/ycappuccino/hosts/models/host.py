"""
Host: a URL mount prefix served from one filesystem directory, with priority and
optional HTTP Basic Auth. See spec (2026-09-15-hosts-design.md) for the simplifications
versus the legacy model (single `directory`, no `type`/`core`/pyscript fields).
"""

from ycappuccino.api.decorators import Item, Property
from ycappuccino.api.models import Model
from ycappuccino.core.decorator_app import App


@App(name="ycappuccino_hosts")
@Item(collection="hosts", name="host", plural="hosts")
class Host(Model):

    def __init__(self, a_dict=None):
        super().__init__(a_dict)
        self._path = None
        self._directory = None
        self._priority = 0
        self._secure = False

    @Property(name="path")
    def path(self, a_value):
        self._path = a_value

    @Property(name="directory")
    def directory(self, a_value):
        self._directory = a_value

    @Property(name="priority", type="integer")
    def priority(self, a_value):
        self._priority = a_value

    @Property(name="secure", type="boolean")
    def secure(self, a_value):
        self._secure = a_value
