import base64
import os
import shutil
import tempfile
import unittest
from unittest import mock

from ycappuccino.api.http import HttpRequest
from ycappuccino.hosts.servlet import HostServlet


def _request(path, headers=None):
    return HttpRequest(
        method="GET", path=path, prefix="/", sub_path=path, query={},
        headers=headers or {},
    )


class FakeModel:
    def __init__(self, document):
        self._document = document

    def get_storage_model(self):
        return self._document


class FakeManager:
    def __init__(self, documents):
        self._documents = documents

    async def get_many(self, item_id, params=None, subject=None):
        return [FakeModel(document) for document in self._documents]

    async def start(self):
        pass

    async def stop(self):
        pass


class FakeConfiguration:
    def __init__(self, values):
        self._values = values

    def get(self, key, default):
        return self._values.get(key, default)


class TestHostServletDispatch(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        self.directory = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.directory, True)
        os.makedirs(os.path.join(self.directory, "sub"), exist_ok=True)
        with open(os.path.join(self.directory, "index.html"), "w") as file:
            file.write("<html>home</html>")
        with open(os.path.join(self.directory, "style.css"), "w") as file:
            file.write("body {}")
        with open(os.path.join(self.directory, "sub", "index.html"), "w") as file:
            file.write("<html>sub</html>")

    def _servlet(self, hosts, configuration=None):
        manager = FakeManager(hosts)
        return HostServlet(manager, configuration, mock.Mock())

    async def test_serves_a_text_file_with_its_mimetype(self):
        servlet = self._servlet(
            [{"_id": "default", "path": "/", "directory": self.directory, "priority": 0, "secure": False}]
        )
        await servlet.start()

        response = await servlet.handle(_request("/style.css"))

        self.assertEqual(response.status, 200)
        self.assertEqual(response.body, b"body {}")
        self.assertEqual(response.content_type, "text/css")

    async def test_root_path_serves_index_html(self):
        servlet = self._servlet(
            [{"_id": "default", "path": "/", "directory": self.directory, "priority": 0, "secure": False}]
        )
        await servlet.start()

        response = await servlet.handle(_request("/"))

        self.assertEqual(response.status, 200)
        self.assertIn(b"home", response.body)

    async def test_directory_like_path_serves_its_index_html(self):
        servlet = self._servlet(
            [{"_id": "default", "path": "/", "directory": self.directory, "priority": 0, "secure": False}]
        )
        await servlet.start()

        response = await servlet.handle(_request("/sub/"))

        self.assertEqual(response.status, 200)
        self.assertIn(b"sub", response.body)

    async def test_no_matching_host_is_404(self):
        servlet = self._servlet(
            [{"_id": "app", "path": "/app", "directory": self.directory, "priority": 0, "secure": False}]
        )
        await servlet.start()

        response = await servlet.handle(_request("/other/file.txt"))

        self.assertEqual(response.status, 404)

    async def test_prefix_does_not_match_partially(self):
        servlet = self._servlet(
            [{"_id": "app", "path": "/pyscriptcore", "directory": self.directory, "priority": 0, "secure": False}]
        )
        await servlet.start()

        response = await servlet.handle(_request("/pyscriptcoreextra/style.css"))

        self.assertEqual(response.status, 404)

    async def test_missing_file_is_404(self):
        servlet = self._servlet(
            [{"_id": "default", "path": "/", "directory": self.directory, "priority": 0, "secure": False}]
        )
        await servlet.start()

        response = await servlet.handle(_request("/missing.txt"))

        self.assertEqual(response.status, 404)

    async def test_path_traversal_is_rejected(self):
        servlet = self._servlet(
            [{"_id": "default", "path": "/", "directory": self.directory, "priority": 0, "secure": False}]
        )
        await servlet.start()

        response = await servlet.handle(_request("/../../etc/passwd"))

        self.assertEqual(response.status, 404)

    async def test_higher_priority_host_wins_on_overlap(self):
        servlet = self._servlet([
            {"_id": "root", "path": "/", "directory": self.directory, "priority": 0, "secure": False},
            {
                "_id": "sub", "path": "/sub", "directory": os.path.join(self.directory, "sub"),
                "priority": 1, "secure": False,
            },
        ])
        await servlet.start()

        response = await servlet.handle(_request("/sub/"))

        self.assertEqual(response.status, 200)
        self.assertIn(b"sub", response.body)

    async def test_etag_round_trip_returns_304(self):
        servlet = self._servlet(
            [{"_id": "default", "path": "/", "directory": self.directory, "priority": 0, "secure": False}]
        )
        await servlet.start()

        first = await servlet.handle(_request("/style.css"))
        etag = first.headers["ETag"]

        second = await servlet.handle(_request("/style.css", headers={"if-none-match": etag}))

        self.assertEqual(second.status, 304)

    async def test_secure_host_without_credentials_is_401(self):
        servlet = self._servlet(
            [{"_id": "admin", "path": "/", "directory": self.directory, "priority": 0, "secure": True}],
            configuration=FakeConfiguration({"admin.login": "alice", "admin.password": "secret"}),
        )
        await servlet.start()

        response = await servlet.handle(_request("/style.css"))

        self.assertEqual(response.status, 401)
        self.assertIn("Basic", response.headers["WWW-Authenticate"])

    async def test_secure_host_with_wrong_credentials_is_401(self):
        servlet = self._servlet(
            [{"_id": "admin", "path": "/", "directory": self.directory, "priority": 0, "secure": True}],
            configuration=FakeConfiguration({"admin.login": "alice", "admin.password": "secret"}),
        )
        await servlet.start()

        header = "Basic " + base64.standard_b64encode(b"alice:wrong").decode()
        response = await servlet.handle(_request("/style.css", headers={"authorization": header}))

        self.assertEqual(response.status, 401)

    async def test_secure_host_with_correct_credentials_is_200(self):
        servlet = self._servlet(
            [{"_id": "admin", "path": "/", "directory": self.directory, "priority": 0, "secure": True}],
            configuration=FakeConfiguration({"admin.login": "alice", "admin.password": "secret"}),
        )
        await servlet.start()

        header = "Basic " + base64.standard_b64encode(b"alice:secret").decode()
        response = await servlet.handle(_request("/style.css", headers={"authorization": header}))

        self.assertEqual(response.status, 200)

    async def test_secure_host_without_configuration_is_always_401(self):
        servlet = self._servlet(
            [{"_id": "admin", "path": "/", "directory": self.directory, "priority": 0, "secure": True}],
            configuration=None,
        )
        await servlet.start()

        header = "Basic " + base64.standard_b64encode(b"anyone:anything").decode()
        response = await servlet.handle(_request("/style.css", headers={"authorization": header}))

        self.assertEqual(response.status, 401)


if __name__ == "__main__":
    unittest.main()
