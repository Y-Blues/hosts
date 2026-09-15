import base64
import unittest
import urllib.error
import urllib.request

from ycappuccino.core.framework import Framework
from ycappuccino.core.testing import TemporaryApplication, wait_until

PORT = 18150

APPLICATION = {
    "conf/application.yml": """
        name: hoststest
        bundle_prefix:
          - ycappuccino.storage
          - PACKAGE
          - ycappuccino.hosts
        layers:
          ycappuccino_storage_memory:
            active: true
        config:
          http_server:
            active: true
            port: {port}
            ip: localhost
          shell:
            console: false
    """.replace("{port}", str(PORT)),
    # PACKAGE (HostBootstrap) is scanned, and its components validated, before ycappuccino.hosts,
    # per Framework.load_bundles: bundles are installed and their components validated
    # synchronously, package by package, in bundle_prefix order. This guarantees the Host
    # documents already exist before HostServlet's own start() loads them (no hot reload,
    # see the design spec).
    "conf/config.properties": "admin.login = alice\nadmin.password = secret\n",
    "PACKAGE/__init__.py": "",
    "PACKAGE/bootstrap.py": """
        import os

        from ycappuccino.api.core_base import YCappuccinoComponent
        from ycappuccino.api.storage import IManager
        from ycappuccino.hosts.models.host import Host


        class HostBootstrap(YCappuccinoComponent):
            def __init__(self, manager: IManager):
                self._manager = manager

            async def stop(self):
                pass

            async def start(self):
                client_directory = os.path.join(os.path.dirname(__file__), "client")

                default_host = Host()
                default_host.id("default")
                default_host.path("/")
                default_host.directory(client_directory)
                default_host.priority(0)
                default_host.secure(False)
                await self._manager.up_sert_model(default_host, subject=None)

                admin_host = Host()
                admin_host.id("admin")
                admin_host.path("/admin")
                admin_host.directory(client_directory)
                admin_host.priority(1)
                admin_host.secure(True)
                await self._manager.up_sert_model(admin_host, subject=None)
    """,
    "PACKAGE/client/index.html": "<html>hello</html>",
}


class TestHostsInFramework(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.app = TemporaryApplication(APPLICATION).open()
        cls.addClassCleanup(cls.app.close)
        cls.framework = Framework()
        cls.framework.init(cls.app.yml_path)
        cls.addClassCleanup(cls.framework.stop)
        wait_until(lambda: cls.framework.context.get_service_reference("HostServlet"))

    @classmethod
    def _get(cls, path, headers=None):
        # response.headers (an email.message.Message) is kept as-is, not converted to a plain
        # dict: HTTP header names are case-insensitive and the real server may send "etag"
        # while ["ETag"] is looked up below; Message supports that natively, a plain dict wouldn't.
        request = urllib.request.Request(f"http://localhost:{PORT}{path}", headers=headers or {})
        try:
            with urllib.request.urlopen(request, timeout=5) as response:
                return response.status, response.read(), response.headers
        except urllib.error.HTTPError as error:
            with error:
                return error.code, error.read(), error.headers

    def test_static_file_is_served(self):
        status, body, _ = self._get("/")

        self.assertEqual(status, 200)
        self.assertIn(b"hello", body)

    def test_unknown_path_is_404(self):
        status, _, _ = self._get("/nope.txt")

        self.assertEqual(status, 404)

    def test_secure_host_requires_basic_auth(self):
        status, _, _ = self._get("/admin/")
        self.assertEqual(status, 401)

        header = "Basic " + base64.standard_b64encode(b"alice:secret").decode()
        status, body, _ = self._get("/admin/", headers={"Authorization": header})
        self.assertEqual(status, 200)

    def test_etag_returns_304(self):
        _, _, headers = self._get("/")
        etag = headers["ETag"]

        status, _, _ = self._get("/", headers={"If-None-Match": etag})

        self.assertEqual(status, 304)


if __name__ == "__main__":
    unittest.main()
