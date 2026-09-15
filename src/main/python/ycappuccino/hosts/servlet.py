"""
HostServlet: a single IHttpServlet, mounted on one fixed prefix (default "/"), that
dispatches internally to the known Host documents (path, directory, priority, secure)
and serves static files from the filesystem, exactly the way ApiServlet dispatches
internally to endpoints_storage use cases under its own fixed "/api" prefix.

See spec (2026-09-15-hosts-design.md) for the design decisions:
- Host documents are loaded once at start() (no hot reload).
- The first Host (by descending priority) whose `path` matches wins; no fallback to a
  lower-priority Host when the file is absent.
- Basic Auth credentials are read from IConfiguration under "<host id>.login" /
  "<host id>.password"; a secure Host with nothing configured always refuses (401),
  never falls back to a known default. IConfiguration is a mandatory dependency here
  (core always provides it) rather than Optional[IConfiguration]: an optional
  dependency satisfied elsewhere in the same multi-path "ycappuccino.*" namespace
  package was observed to resolve non-deterministically (sometimes None) depending on
  scan timing; a mandatory dependency makes core wait for it, like `manager`/`logger`.
- A failed/missing auth answers 401 (with WWW-Authenticate), never 404.
- A Host with cross_origin_isolated=True (see models/host.py) gets
  Cross-Origin-Opener-Policy: same-origin and Cross-Origin-Embedder-Policy: require-corp added
  to EVERY response served under its mount, success or error alike (200/304/401/404/500): this
  is a page-level isolation mode, not tied to any one status code. Off by default, and only
  added when a Host actually matched the request - see ycappuccino-client's README.md for why
  this exists (a pthread-enabled Pyodide build needs it) and the real tension it creates with
  third-party CDN resources.
"""

import base64
import mimetypes
import os
from typing import Optional

from ycappuccino.api.core import IActivityLogger, IConfiguration
from ycappuccino.api.core_base import YCappuccinoType
from ycappuccino.api.http import HttpRequest, HttpResponse, IHttpServlet
from ycappuccino.api.storage import IManager

_ITEM_ID = "host"


class HostServlet(IHttpServlet):

    def __init__(
        self,
        manager: IManager,
        configuration: IConfiguration,
        logger: YCappuccinoType(IActivityLogger, "(name=main)"),
        path: str = "/",
    ):
        self._manager = manager
        self._configuration = configuration
        self._logger = logger
        self._path = path
        self._hosts: list = []

    async def start(self):
        models = await self._manager.get_many(_ITEM_ID, subject=None)
        hosts = []
        for model in models:
            document = model.get_storage_model()
            hosts.append({
                "id": document["_id"],
                "path": document["path"],
                "directory": os.path.abspath(document["directory"]),
                "priority": document.get("priority") or 0,
                "secure": bool(document.get("secure")),
                "cross_origin_isolated": bool(document.get("cross_origin_isolated")),
            })
        hosts.sort(key=lambda host: host["priority"], reverse=True)
        self._hosts = hosts

    async def stop(self):
        pass

    async def handle(self, request: HttpRequest) -> HttpResponse:
        host = self._find_host(request.path)
        if host is None:
            return _not_found()

        response = await self._serve(host, request)
        if host["cross_origin_isolated"]:
            response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
            response.headers.setdefault("Cross-Origin-Embedder-Policy", "require-corp")
        return response

    async def _serve(self, host: dict, request: HttpRequest) -> HttpResponse:
        if host["secure"]:
            authorized = self._check_auth(host, request.headers)
            if not authorized:
                return _unauthorized(host["id"])

        try:
            file_path = self._resolve_file(host, request.path)
            if file_path is None:
                return _not_found()

            etag = _etag(file_path)
            if_none_match = _header(request.headers, "if-none-match")
            if if_none_match == etag:
                return HttpResponse(status=304, headers={"ETag": etag})

            with open(file_path, "rb") as file:
                body = file.read()
            content_type = mimetypes.guess_type(file_path)[0] or "application/octet-stream"
            return HttpResponse(status=200, body=body, content_type=content_type, headers={"ETag": etag})
        except Exception:
            self._logger.exception("hosts: failed to serve %s", request.path)
            return HttpResponse(status=500, body=b"", content_type="text/plain")

    def _find_host(self, request_path: str) -> Optional[dict]:
        for host in self._hosts:
            if _matches(request_path, host["path"]):
                return host
        return None

    def _check_auth(self, host: dict, headers: dict) -> bool:
        if self._configuration is None:
            return False
        expected_login = self._configuration.get(f"{host['id']}.login", None)
        expected_password = self._configuration.get(f"{host['id']}.password", None)
        if expected_login is None or expected_password is None:
            return False
        credentials = _decode_basic(_header(headers, "authorization"))
        if credentials is None:
            return False
        login, password = credentials
        return login == expected_login and password == expected_password

    def _resolve_file(self, host: dict, request_path: str) -> Optional[str]:
        mount = host["path"]
        directory = host["directory"]
        relative = request_path if mount == "/" else request_path[len(mount):]
        relative = relative.lstrip("/")

        candidate = os.path.join(directory, relative) if relative else directory
        if request_path.endswith("/") or os.path.isdir(candidate):
            candidate = os.path.join(candidate, "index.html")

        real_directory = os.path.realpath(directory)
        real_candidate = os.path.realpath(candidate)
        if real_candidate != real_directory and not real_candidate.startswith(real_directory + os.sep):
            return None
        if not os.path.isfile(real_candidate):
            return None
        return real_candidate


def _header(headers: dict, name: str) -> Optional[str]:
    """case-insensitive header lookup: a real HTTP server preserves the client's header
    case (e.g. "Authorization"), unlike the lowercase dicts used in unit test doubles"""
    for key, value in headers.items():
        if key.lower() == name:
            return value
    return None


def _matches(request_path: str, mount: str) -> bool:
    if mount == "/":
        return True
    return request_path == mount or request_path.startswith(mount + "/")


def _decode_basic(header: Optional[str]):
    if not header or not header.startswith("Basic "):
        return None
    try:
        decoded = base64.standard_b64decode(header[len("Basic "):]).decode("utf-8")
    except Exception:
        return None
    if ":" not in decoded:
        return None
    login, _, password = decoded.partition(":")
    return login, password


def _etag(file_path: str) -> str:
    return f'"{os.path.getmtime(file_path)}"'


def _not_found() -> HttpResponse:
    return HttpResponse(status=404, body=b"", content_type="text/plain")


def _unauthorized(host_id: str) -> HttpResponse:
    return HttpResponse(
        status=401, body=b"", content_type="text/plain",
        headers={"WWW-Authenticate": f'Basic realm="{host_id}"'},
    )
