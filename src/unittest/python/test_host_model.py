import shutil
import unittest

from hosts_fixtures import create_manager

from ycappuccino.hosts.models.host import Host


class TestHost(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        self.manager, directory = create_manager()
        self.addCleanup(shutil.rmtree, directory, True)

    async def test_round_trip_through_the_manager(self):
        host = Host()
        host.id("default")
        host.path("/")
        host.directory("client")
        host.priority(5)
        host.secure(True)

        await self.manager.up_sert_model(host)
        stored = (await self.manager.get_one("host", "default")).get_storage_model()

        self.assertEqual(stored["path"], "/")
        self.assertEqual(stored["directory"], "client")
        self.assertEqual(stored["priority"], 5)
        self.assertIs(stored["secure"], True)

    async def test_defaults(self):
        host = Host()

        self.assertEqual(host.get_storage_model().get("priority", 0), 0)
        self.assertIs(host.get_storage_model().get("secure", False), False)


if __name__ == "__main__":
    unittest.main()
