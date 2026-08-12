"""ArchiveBoxClient backend for a pinned pre-0.8 instance with no REST API --
logs into the Django admin UI and parses HTML with BeautifulSoup4 instead.
Page shapes verified live against hecate's 0.7.4 instance (2026-08-11):

- GET {base_url}/public/ requires no auth, lists snapshots in
  table#table-bookmarks, one <tr> per snapshot with columns
  [Bookmarked, Snapshot, Files, Original URL]. The snapshot's timestamp-as-id
  is embedded in its links, e.g. /archive/1774158266.508078/index.html.
- GET {base_url}/add/ redirects (302) to /admin/login/ for an unauthenticated
  session -- a plain <form id="login-form"> with csrfmiddlewaretoken/
  username/password fields, standard Django admin login.
- GET {base_url}/add/, once authenticated, is a bare <form method="post"> (no
  action attr -- posts back to /add/ itself) confirmed live 2026-08-11:
  csrfmiddlewaretoken (hidden), url (<textarea>, required), parser (<select>,
  optional, default "auto"), tag (<input type="text">, optional, comma-
  separated), depth (<input type="radio"> "0"/"1", required, defaults "0"),
  archive_methods (<select multiple>, optional). add() below only sets url/
  tag/depth, matching the CLI's own default behavior for the rest.

Every method requires config.username/password (raises ArchiveBoxConfigError
if either is missing) -- there is no anonymous add path in ArchiveBox's admin."""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from .config import ArchiveBoxConfig, ArchiveBoxConfigError
from .models import Snapshot

LOGIN_PATH = "/admin/login/"
ADD_PATH = "/add/"
PUBLIC_INDEX_PATH = "/public/"


def _attr_str(value: object) -> str:
    """Narrow a bs4 tag attribute (str | AttributeValueList | None) to plain str --
    every attribute this module reads (csrf token, href) is a single string in
    practice, never bs4's multi-value list form (only used for things like
    class="a b c")."""
    if not isinstance(value, str):
        raise TypeError(f"expected a string attribute, got {type(value).__name__}: {value!r}")
    return value


class ScrapeBackend:
    def __init__(self, config: ArchiveBoxConfig, *, client: Optional[httpx.Client] = None) -> None:
        if not config.username or not config.password:
            raise ArchiveBoxConfigError("ScrapeBackend requires ARCHIVEBOX_USERNAME and ARCHIVEBOX_PASSWORD")
        self._config = config
        self._client = client or config.new_http_client(follow_redirects=True)
        self._logged_in = False

    def _login(self) -> None:
        if self._logged_in:
            return
        login_page = self._client.get(LOGIN_PATH)
        login_page.raise_for_status()
        soup = BeautifulSoup(login_page.text, "lxml")
        form = soup.find("form", id="login-form")
        if form is None:
            raise RuntimeError(f"login form not found at {LOGIN_PATH} -- ArchiveBox admin login page shape changed")
        csrf_input = form.find("input", attrs={"name": "csrfmiddlewaretoken"})
        if csrf_input is None:
            raise RuntimeError("csrfmiddlewaretoken input not found on login form")
        resp = self._client.post(
            LOGIN_PATH,
            data={
                "csrfmiddlewaretoken": csrf_input["value"],
                "username": self._config.username,
                "password": self._config.password,
                "next": "/admin/",
            },
            headers={"Referer": urljoin(self._config.base_url, LOGIN_PATH)},
        )
        resp.raise_for_status()
        if "login" in str(resp.url).lower():
            raise RuntimeError("ArchiveBox admin login failed -- check ARCHIVEBOX_USERNAME/ARCHIVEBOX_PASSWORD")
        self._logged_in = True

    def add(self, url: str, *, tags: Optional[list[str]] = None, depth: int = 0) -> Snapshot:
        self._login()
        add_page = self._client.get(ADD_PATH)
        add_page.raise_for_status()
        soup = BeautifulSoup(add_page.text, "lxml")
        form = soup.find("form")
        if form is None:
            raise RuntimeError(
                f"no <form> found at {ADD_PATH} -- this backend's add-form guess needs updating "
                "against the real authenticated page (see module docstring)"
            )
        csrf_input = form.find("input", attrs={"name": "csrfmiddlewaretoken"})
        # url needs a trailing newline (it's a "one per line" textarea) and archive_methods
        # must be omitted entirely, not sent empty -- Django's multi-select field rejects an
        # empty string with "Select a valid choice.  is not one of the available choices.",
        # confirmed live 2026-08-11 against hecate's 0.7.4 instance.
        payload: dict[str, str] = {"url": f"{url}\n", "parser": "auto", "depth": str(depth)}
        if tags:
            payload["tag"] = ",".join(tags)
        if csrf_input is not None:
            payload["csrfmiddlewaretoken"] = _attr_str(csrf_input["value"])
        # Adding blocks until archiving finishes server-side -- give it much longer than the
        # client's default timeout rather than the request being killed mid-archive.
        resp = self._client.post(
            ADD_PATH,
            data=payload,
            headers={"Referer": urljoin(self._config.base_url, ADD_PATH)},
            timeout=180.0,
        )
        resp.raise_for_status()
        error_node = BeautifulSoup(resp.text, "lxml").find(class_=lambda c: c and "error" in c.lower())
        if error_node is not None:
            raise RuntimeError(f"ArchiveBox rejected add({url!r}): {error_node.get_text(strip=True)}")
        matches = [s for s in self.list(search=url) if s.url == url]
        if matches:
            return max(matches, key=lambda s: s.created_at or datetime.min)
        return Snapshot(id=url, url=url, status="queued", tags=tags or [])

    def list(
        self,
        *,
        search: Optional[str] = None,
        tag: Optional[str] = None,
        limit: int = 200,
    ) -> list[Snapshot]:
        resp = self._client.get(PUBLIC_INDEX_PATH)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")
        table = soup.find("table", id="table-bookmarks")
        if table is None:
            return []
        snapshots: list[Snapshot] = []
        for row in table.find_all("tr"):
            if row.find("th") is not None:
                continue  # header row
            cells = row.find_all("td")
            if len(cells) < 4:
                continue
            title_link = cells[1].find("a", href=True)
            url_link = cells[3].find("a", href=True)
            if title_link is None or url_link is None:
                continue
            title_href = _attr_str(title_link["href"])
            snapshot_id = title_href.strip("/").split("/")[-2] if "/" in title_href else ""
            title_span = cells[1].find("span", attrs={"data-title-for": True})
            title = title_span.get_text(strip=True) if title_span else None
            page_url = url_link.get_text(strip=True)
            if search and search.lower() not in page_url.lower() and (not title or search.lower() not in title.lower()):
                continue
            date_cell = cells[0]
            created_at = None
            sort_attr = date_cell.get("data-sort")
            if sort_attr:
                try:
                    created_at = datetime.fromtimestamp(float(_attr_str(sort_attr)))
                except (ValueError, OSError, TypeError):
                    created_at = None
            snapshots.append(
                Snapshot(
                    id=snapshot_id,
                    url=page_url,
                    status="succeeded",
                    title=title,
                    created_at=created_at,
                )
            )
            if len(snapshots) >= limit:
                break
        return snapshots

    def get(self, snapshot_id: str) -> Optional[Snapshot]:
        for snapshot in self.list(limit=500):
            if snapshot.id == snapshot_id:
                return snapshot
        return None
