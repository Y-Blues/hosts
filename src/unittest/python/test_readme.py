import os
import shutil
import tempfile
import unittest
from unittest import mock

from ycappuccino.api.http import HttpRequest
from ycappuccino.hosts.servlet import HostServlet


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


class TestHostServlet(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        self.directory = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.directory, True)
        with open(os.path.join(self.directory, "index.html"), "w") as file:
            file.write("<html>home</html>")

    async def test_serves_the_index(self):
        manager = FakeManager(
            [{"_id": "default", "path": "/", "directory": self.directory, "priority": 0, "secure": False}]
        )
        servlet = HostServlet(manager, mock.Mock(), mock.Mock())
        await servlet.start()

        request = HttpRequest(method="GET", path="/", prefix="/", sub_path="/", query={}, headers={})
        response = await servlet.handle(request)

        self.assertEqual(response.status, 200)
        self.assertIn(b"home", response.body)


if __name__ == "__main__":
    unittest.main()
