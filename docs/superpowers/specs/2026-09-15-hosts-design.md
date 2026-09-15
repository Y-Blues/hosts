# hosts natif : design

Date : 2026-09-15. Sous-projet de la reprise des dépôts YCappuccino, après `core`, `api`, `storage`, `endpoints_storage`, `http_server`, `endpoints_service` (et en parallèle de `permissions_app`, `scripts`, `scheduler`, `swagger`).

## Objectif

`hosts` sert du contenu statique (une SPA, plus tard le client pyscript) depuis un ou plusieurs répertoires du système de fichiers, montés sur un préfixe d'URL, avec priorité en cas de chevauchement et une protection HTTP Basic optionnelle par montage. C'est un `IHttpServlet` natif au-dessus d'un modèle `@Item` `Host`, exactement comme `ApiServlet` (`http_server`) est un `IHttpServlet` au-dessus des cas d'usage `endpoints_storage`.

Le legacy (`ycappuccino.hosts` avant reprise) mélangeait cette responsabilité avec une machinerie de génération dynamique de bundles iPOPO (`manage_python`, `_call_decorator_*`) pour un mode d'exécution de code Python côté client abandonné, et avec un mécanisme de remplacement de contenu (`IClobReplaceService`) lié au même abandon. Aucun des deux n'est repris : ce sous-projet ne fait que servir des fichiers statiques.

## Décisions

| Sujet | Décision |
|---|---|
| Style | Composant natif, aucun décorateur |
| Modèle | Un seul `Host` (`path`, `directory`, `priority`, `secure`), remplace le legacy `path`/`subpath`/`path_core`/`path_app` par un unique `directory` explicite. Champs `type`/`core`/pyscript retirés : c'était uniquement l'accroche du mode d'exécution abandonné ; un futur client pyscript sera un répertoire de fichiers statiques comme un autre |
| Résolution de `directory` | Résolu en chemin absolu (`os.path.abspath`, donc relatif au répertoire courant si pas déjà absolu — cohérent avec « le répertoire courant compte » du README de `core`) **au moment où le servlet charge les `Host` à son `start()`**, pas à l'écriture du modèle : un modèle stocké garde le texte tel quel (utile pour l'inspecter/le modifier tel quel via `/api/crud/hosts`), la résolution est un détail d'exécution du servlet, pas de la persistance |
| Un servlet, plusieurs montages | `IHttpServlet.path` est une propriété unique (un servlet = un préfixe fixe), donc **un seul servlet natif, monté sur `path="/"` par défaut**, qui lit dynamiquement la liste des `Host` et distribue en interne selon leur `path` respectif — exactement comme `ApiServlet` distribue en interne selon `sub_path` sous son propre préfixe fixe `/api`. Pas besoin de toucher `core`/`api` : le contrat actuel (`handle(request) -> HttpResponse`, une seule `path` par servlet) suffit très bien, il n'impose pas « un servlet = un seul répertoire » |
| Chargement des `Host` | Chargés **une seule fois à `start()`** (`IManager.get_many("host", subject=None)`), triés par priorité décroissante et mis en cache en mémoire (avec `directory` résolu, voir ci-dessus). Pas de rechargement à chaud : même simplification assumée que `scheduler` (« chargées une seule fois à start(), arme le planificateur ») — une modification par `/api/crud/hosts` prend effet au **prochain redémarrage**. Un rechargement à chaud demanderait un `ITrigger` sur `host`, hors périmètre |
| Sélection du `Host` | Priorité décroissante, **premier montage dont le préfixe correspond gagne**, sans repli sur un montage de priorité inférieure si le fichier est absent dans le premier (contrairement au legacy qui essayait `path_app` puis `path_core` puis, pour `pyscript`, un chemin core dédié — supprimé avec les champs `type`/`core`) : un seul `directory` explicite par `Host`, donc un seul essai |
| Correspondance de préfixe | `path="/"` correspond à tout. Sinon, correspond si le chemin de la requête est exactement `path` ou commence par `path + "/"` (`/pyscriptcore` ne doit pas correspondre à `/pyscriptcoreextra`) |
| Résolution du fichier | `chemin_relatif = chemin_requête[len(path):]`, joint à `directory`. Un chemin relatif vide ou terminé par `/`, ou qui désigne un répertoire réel, sert `index.html` de ce répertoire. Pas de page de listage de répertoire générée (le legacy n'en générait pas non plus — il ajoutait juste `index.html`) : une simplification assumée, pas une régression |
| Traversée de chemin | Le chemin résolu (`os.path.realpath`) doit rester sous `directory` (`os.path.realpath` de `directory`), sinon `404` — protection absente du legacy, ajoutée ici car servir des fichiers arbitraires du disque sur une requête `../../etc/passwd` est une vulnérabilité classique, pas une fonctionnalité à reproduire |
| Lecture de fichier | Toujours en binaire (`rb`), un seul chemin de code pour texte/binaire : `HttpResponse.body` est `bytes` dans tous les cas, donc la distinction legacy `manage_clob`/`manage_blob`/`manage_python` (qui existait pour le hack de live-templating) n'a plus de raison d'être |
| Type mime | `mimetypes.guess_type(chemin)[0]`, `application/octet-stream` si inconnu |
| Cache HTTP | `ETag` = `'"' + str(mtime du fichier) + '"'` (mtime, comme le legacy, mais avec guillemets pour être un ETag HTTP valide) ; requête avec `If-None-Match` égal → `304` sans corps |
| Basic Auth | Par `Host` (`secure=True`). Identifiants dans `IConfiguration` sous les clés **`<id du document Host>.login` / `<id du document Host>.password`** — pas `<mount>.login` : le chemin de montage peut contenir des `/` (`/pyscriptcore`), invalide comme fragment de clé de configuration plate, alors que l'id du document (`hosts.up_sert("host", "pyscriptcore", ...)`) est déjà un identifiant simple choisi par l'application, exactement l'usage que `_id` avait dans le `Host` legacy (`self._id + ".login"`) |
| Absence d'identifiants configurés | Un `Host` `secure=True` sans `<id>.login`/`<id>.password` configurés **refuse toujours l'authentification** (pas de couple par défaut utilisable) plutôt que de retomber sur un couple par défaut connu (le legacy avait `client_pyscript_core` / `1234` en dur) : un défaut connu et documenté est une porte dérobée, pas une fonctionnalité |
| Échec d'authentification | `401` avec en-tête `WWW-Authenticate: Basic realm="<id>"`, jamais `404` (le legacy renvoyait `404` sur un échec d'auth, ce qui masque la distinction entre « fichier absent » et « non autorisé » — une amélioration volontaire, testée) |
| Bootstrap par défaut | **Pas fourni par la bibliothèque** : une vraie application crée ses propres documents `Host` via `/api/crud/hosts` (gratuit dès que le modèle est enregistré) ou via un petit composant de démarrage dans son propre code — exactement comme `scheduler` ne fournit pas de tâche par défaut. `example/` montre ce dernier style (un composant `HostBootstrap` minimal), pas une fonctionnalité de la librairie |
| Erreurs | `404` : aucun `Host` ne correspond, ou fichier absent dans le `Host` qui correspond (pas de repli). `401` : `Host` sécurisé, authentification absente ou invalide. `500` : exception inattendue (I/O, etc.), journalisée, jamais de détail interne dans le corps — cohérent avec `ApiServlet` |

## 1. Modèle (`models/host.py`)

```python
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

    @Property(name="priority")
    def priority(self, a_value):
        self._priority = a_value

    @Property(name="secure")
    def secure(self, a_value):
        self._secure = a_value
```

Pas de `secure_read`/`secure_write` sur l'`@Item` lui-même : la configuration des montages n'est pas plus sensible qu'une autre configuration d'application (contrairement à `ScheduledTask` dans `scheduler`, qui contrôle des déclenchements) ; elle reste néanmoins un `@Item` normal, donc gouvernable par n'importe quel `IAuthorization` que l'application ajouterait elle-même.

## 2. `HostServlet` (`servlet.py`) — composant natif

```python
class HostServlet(IHttpServlet):

    def __init__(
        self,
        manager: IManager,
        configuration: Optional[IConfiguration],
        logger: YCappuccinoType(IActivityLogger, "(name=main)"),
        path: str = "/",
    ):
        self._manager = manager
        self._configuration = configuration
        self._logger = logger
        self._path = path
        self._hosts: list[dict] = []          # chargé à start(), voir Décisions

    async def start(self):
        """charge les documents host (subject=None), résout `directory` en absolu,
        trie par priorité décroissante"""

    async def stop(self):
        pass

    async def handle(self, request: HttpRequest) -> HttpResponse:
        """trouve le premier Host dont le path correspond, vérifie l'auth si secure,
        résout le fichier, sert 200/304/401/404"""
```

Points clés :

- **`_find_host(request_path)`** : itère `self._hosts` (déjà triés par priorité décroissante à `start()`), renvoie le premier dont `path` correspond (voir Décisions), ou `None`.
- **`_check_auth(host, headers)`** : si `host["secure"]` est faux, toujours autorisé. Sinon décode l'en-tête `authorization` (`Basic <base64(user:pass)>`) et compare à `configuration.get(f"{host['id']}.login", None)` / `.password`. Sans `IConfiguration` publiée (cas test unitaire simple), un `Host` `secure=True` refuse toujours — documenté, cohérent avec « pas de défaut connu ».
- **`_resolve_file(host, request_path)`** : calcule le chemin relatif, le joint à `host["directory"]`, retombe sur `index.html` si nécessaire, vérifie que le résultat reste sous `directory` (protection traversée), renvoie `None` si absent ou hors périmètre.
- **Toute la logique ci-dessus est testable directement** en construisant `HostServlet` avec un faux `IManager` (`get_many` renvoie des faux modèles avec `.get_storage_model()`), en appelant `await servlet.start()` puis `await servlet.handle(request)`, sur un vrai répertoire temporaire de fichiers — sans framework, comme le préconise le README de `core` et comme le fait `http_server`.

## 3. Authentification : détail

```python
import base64

def _decode_basic(header: str) -> tuple[str, str] | None:
    if not header or not header.startswith("Basic "):
        return None
    try:
        decoded = base64.standard_b64decode(header.removeprefix("Basic ")).decode("utf-8")
    except Exception:
        return None
    user, _, password = decoded.partition(":")
    return (user, password) if ":" in decoded else None
```

`IConfiguration` est **optionnelle** (`Optional[IConfiguration]`, reconnu nativement par `core` sans `YCappuccinoType`) : dans un test unitaire sans framework, on peut construire `HostServlet` avec `configuration=None` ; un `Host` `secure=True` refusera alors systématiquement (voir Décisions), ce qui est le comportement sûr par défaut, testé explicitement.

## 4. CRUD

`Host` étant un `@Item` enregistré, `http_server` expose automatiquement `/api/crud/hosts` (lecture, création, modification, suppression), sans code supplémentaire ici — comme `scheduled-tasks` dans `scheduler`.

## 5. Packaging et exemple

```
hosts/
  pyproject.toml
  README.md
  example/
    conf/application.yml
    client/index.html          # contenu statique servi par défaut
    client/style.css
    demo/__init__.py
    demo/bootstrap.py          # HostBootstrap : crée le Host par défaut
  src/main/python/ycappuccino/hosts/
    __init__.py
    servlet.py                 # HostServlet
    models/
      __init__.py
      host.py                  # Host
  src/unittest/python/
    hosts_fixtures.py
    test_host_model.py
    test_servlet_dispatch.py   # unitaire, faux IManager, vrai répertoire temporaire
    test_hosts_framework.py    # intégration réelle : framework + HTTP réel
    test_readme.py
```

- **`pyproject.toml`** (uv, `uv_build`) : projet `ycappuccino-hosts`, module `ycappuccino.hosts`, racine `src/main/python`. Dépendances : `ycappuccino-api`, `ycappuccino-core`, `ycappuccino-storage`, toutes en source de chemin local éditable. Aucune dépendance externe (`mimetypes`, `base64`, `os.path` sont stdlib).
- **Supprimés** : `build.py`, `setup.py`, `src/main/python/ycappuccino/hosts/bundles/` (bundle iPOPO legacy, `index_endpoint.py`), `src/main/python/ycappuccino/hosts/services/` (`host.py`, `host_factory.py`, `replace_service.py`, `replace_service_pyscript_index.py` — remplacés par `servlet.py` et le chargement direct dans `HostServlet.start()`), `src/main/python/ycappuccino/hosts/bootstrap.py` (remplacé par le composant d'exemple `demo/bootstrap.py`, la bibliothèque elle-même n'en fournit pas — voir Décisions), `src/main/python/ycappuccino/hosts/conf/` (déclarait une couche `ycappuccino_host` sans utilité : aucun composant natif ne porte de `__ycappuccino_layer__` ici).
- **Exemple** : couche mémoire de `storage`, un répertoire `client/` avec un `index.html` et une feuille de style, un `Host` par défaut (`path="/"`, `directory="client"`, `priority=0`, `secure=False`) créé par `HostBootstrap` (`up_sert_model`, comme `TaskBootstrap` dans `scheduler`).
- **README** : mise en place, modèle, exemple, section auth, section « Tester avec hosts », « Développer hosts ».

## 6. Tests

| Fichier | Contenu |
|---|---|
| `test_host_model.py` | round-trip du modèle `Host` à travers un vrai `Manager`/`MemoryStorage` (comme `test_scheduled_task.py` dans `scheduler`) |
| `test_servlet_dispatch.py` | faux `IManager` (`get_many` renvoie des faux modèles), vrai répertoire temporaire : fichier texte servi avec le bon mimetype et corps, fichier binaire, `index.html` implicite (chemin vide et chemin en `/`), priorité (deux `Host` qui se chevauchent, le plus prioritaire gagne), préfixe qui ne doit pas correspondre partiellement (`/pyscriptcore` vs `/pyscriptcoreextra`), 404 sans `Host` correspondant, 404 fichier absent, traversée de chemin refusée (`../`), `ETag`/`If-None-Match` → `304`, `Host` sécurisé sans en-tête → `401` avec `WWW-Authenticate`, avec de mauvais identifiants → `401`, avec les bons → `200`, `Host` sécurisé sans `IConfiguration` → toujours `401` |
| `test_hosts_framework.py` | démarrage du framework réel (`TemporaryApplication`/`Framework`), `HostServlet` publié, vraie requête HTTP (`urllib.request`) sur un fichier statique réel, un `404`, un `Host` sécurisé (401 puis 200 avec les bons identifiants via `IConfiguration`/`config.properties`), un `304` via `If-None-Match`. Port dans `18150-18159` |
| `test_readme.py` | les exemples du README (déclaration du modèle, `HostServlet` construit directement) restent exécutables |

## 7. Hors périmètre

- **Rechargement à chaud** des `Host` modifiés par CRUD : nécessiterait un `ITrigger` sur `host` ; chargés une fois au démarrage (voir Décisions).
- **Repli en cascade** entre plusieurs `Host` de priorités différentes pour une même requête (essayer le suivant si le fichier est absent dans le premier) : le legacy le faisait (`path_app` puis `path_core`) à cause de son modèle à deux racines implicites ; avec un `directory` explicite par `Host`, ce n'est plus nécessaire — un `Host` qui ne trouve pas le fichier répond `404` sans essayer un autre montage.
- **Génération d'une page de listage de répertoire** : jamais fournie, ni ici ni dans le legacy.
- **Compression (gzip), Range requests, cache-control autre que `ETag`** : pas demandé, ajouterait de la complexité sans besoin exprimé.
- **`IClobReplaceService`, exécution de Python côté client, génération dynamique de bundles iPOPO** (`manage_python`, `_call_decorator_*`) : le mode d'exécution qu'ils supportaient est abandonné, voir Objectif.
- **Bootstrap par défaut fourni par la bibliothèque** : voir Décisions, à la charge de l'application.

## 8. Risques

- **`directory` résolu une seule fois, au démarrage, relatif au répertoire courant à ce moment-là** : si l'application change de répertoire courant après le démarrage (rare, pas fait par `core`), les chemins déjà résolus restent corrects (absolus), mais un `Host` créé par CRUD après le démarrage n'est pas pris en compte avant le redémarrage (voir Hors périmètre).
- **Pas de défaut d'identifiants pour un `Host` sécurisé** : un déploiement qui active `secure=True` sans configurer `<id>.login`/`.password` se retrouve avec un montage totalement inaccessible (401 permanent), pas un montage accessible avec un mot de passe par défaut connu de tous — un choix de sécurité assumé, à documenter clairement dans le README pour ne pas surprendre.
- **Basic Auth en clair** : comme le legacy, aucune protection contre l'interception réseau (pas de TLS géré ici) ; à déployer derrière un reverse proxy TLS en production, hors périmètre de ce dépôt.
