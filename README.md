# ycappuccino-hosts

Sert du contenu statique natif : un modèle `Host` (préfixe de montage, répertoire, priorité, sécurisation) et un composant `HostServlet`, `IHttpServlet` unique monté sur `/`, qui distribue en interne selon les `Host` connus et sert les fichiers (mimetype, `ETag`/`If-None-Match`, `index.html`, Basic Auth optionnelle).

Conception : [docs/superpowers/specs/2026-09-15-hosts-design.md](docs/superpowers/specs/2026-09-15-hosts-design.md).

Prérequis : lire les README de [core](../core/README.md) (section « Servlets HTTP ») et de [storage](../storage/README.md).

## Mise en place

```bash
uv add --editable ../hosts
```

`conf/application.yml` :

```yaml
bundle_prefix:
  - ycappuccino.storage
  - myapp
  - ycappuccino.hosts
layers:
  ycappuccino_storage_memory:
    active: true
config:
  http_server:
    active: true
    port: 8080
```

**Important** : lister le paquet qui crée les documents `Host` (ci-dessus `myapp`) **avant** `ycappuccino.hosts` dans `bundle_prefix` : les composants d'un paquet sont validés avant ceux du paquet suivant (voir « Un seul servlet, plusieurs montages » ci-dessous), ce qui garantit que `HostServlet` trouve déjà les `Host` écrits par un composant de démarrage de `myapp` au moment de son propre `start()`.

## Modèle

```python
from ycappuccino.hosts.models.host import Host

host = Host()
host.id("default")
host.path("/")               # préfixe de montage
host.directory("client")     # répertoire (absolu, ou relatif au répertoire courant)
host.priority(0)              # entier, plus grand gagne en cas de chevauchement
host.secure(False)
await manager.up_sert_model(host)
```

`Host` est un `@Item` normal : `http_server` expose `/api/crud/hosts` sans code supplémentaire.

## Un seul servlet, plusieurs montages

`IHttpServlet.path` est une propriété unique (un servlet = un préfixe fixe). `HostServlet` est monté sur `path="/"` et distribue en interne selon le `path` de chaque `Host` connu — exactement comme `ApiServlet` (`http_server`) distribue en interne sous son propre préfixe fixe `/api`. Les `Host` sont chargés **une seule fois**, au `start()` de `HostServlet` (pas de rechargement à chaud : une modification par `/api/crud/hosts` prend effet au prochain redémarrage). Priorité décroissante, premier montage dont le préfixe correspond gagne, sans repli sur un montage de priorité inférieure si le fichier est absent.

## Authentification

Un `Host` `secure=True` exige une authentification HTTP Basic. Les identifiants viennent d'`IConfiguration`, sous les clés **`<id du document Host>.login`** / **`<id du document Host>.password`** (pas le chemin de montage, qui peut contenir des `/`) :

```
# conf/config.properties
admin.login = alice
admin.password = secret
```

Sans ces clés configurées, le montage `secure=True` refuse **toujours** l'authentification (`401`), il n'y a pas de couple par défaut connu. Un échec ou une absence d'authentification répond `401` avec l'en-tête `WWW-Authenticate: Basic realm="<id>"`, jamais `404`.

## Exemple

```python
from ycappuccino.api.core_base import YCappuccinoComponent
from ycappuccino.api.storage import IManager
from ycappuccino.hosts.models.host import Host


class HostBootstrap(YCappuccinoComponent):
    def __init__(self, manager: IManager):
        self._manager = manager

    async def stop(self):
        pass

    async def start(self):
        default_host = Host()
        default_host.id("default")
        default_host.path("/")
        default_host.directory("client")
        default_host.priority(0)
        default_host.secure(False)
        await self._manager.up_sert_model(default_host, subject=None)
```

## Tester avec hosts

`HostServlet` s'instancie directement, sans framework, avec un faux `IManager` et un vrai répertoire temporaire :

```python
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
```

## Développer hosts

```bash
uv sync
uv run python -m unittest discover -s src/unittest/python
```

L'exemple `example/` se lance avec `cd example && uv run --project .. ycappuccino`.
