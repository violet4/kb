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
  tag/depth, matching the CLI's own default behavior for the rest. Re-POSTing
  an already-saved URL here is a no-op (ArchiveBox dedups against the
  existing Snapshot row, confirmed live 2026-08-14) -- it does NOT retry a
  snapshot whose archive methods already failed; use pull()/method_results()
  below for that.
- GET {base_url}/archive/<timestamp>/index.json (once authenticated) has a
  "history" dict, one key per archive method (singlefile, wget, dom, pdf,
  screenshot, ...), each a list of every attempt's
  {status, output, start_ts, end_ts} -- confirmed live 2026-08-14 this is the
  only reachable way to see a snapshot's real per-method pass/fail, since a
  push_status of SUCCESS on our own ArchivedLink row only means ArchiveBox
  accepted the add job, never that any individual method actually captured
  content (see kb Note #105/#131). A missing output file (e.g.
  /archive/<ts>/singlefile.html 404ing with "does not exist in snapshot dir
  yet") is misleadingly worded -- if index.json's history for that method
  says status: "failed", it's a permanent recorded failure, not a race.
- The snapshot changelist (/admin/core/snapshot/, needs Django's
  core.view_snapshot permission on the account -- see kb Note #131) exposes
  a bulk "action" dropdown POSTed back to the same URL as
  {action, _selected_action: <row uuid>, select_across: "0", index: "0"}
  alongside the page's own csrfmiddlewaretoken. Two relevant actions,
  confirmed live 2026-08-14 against a real stuck snapshot:
    - "update_snapshots" (labelled "Pull" in the UI) -- re-runs only the
      archive methods that don't already have a successful result, leaving
      already-succeeded methods' files untouched. This is what pull() below
      uses. No confirmation dialog in the admin UI, so nothing destructive.
    - "overwrite_snapshots" (labelled "Reset" in the UI) -- deletes ALL
      previously saved files for the snapshot and re-archives everything
      from scratch; the admin UI gates this behind a JS confirm() dialog
      ("This will delete all previously saved files..."). Not implemented
      here since it's a destructive action a caller should opt into
      explicitly, not something retry-style code should reach for by
      default.
  The bulk-action POST can take longer than a typical proxy timeout for a
  slow-to-archive URL (a 504 was seen live even though the job kept running
  and completed server-side) -- pull() uses a long timeout but a 504 doesn't
  necessarily mean the pull failed; check method_results() after to see the
  real per-method outcome regardless of what the POST itself returned.

Every method requires config.username/password (raises ArchiveBoxConfigError
if either is missing) -- there is no anonymous add path in ArchiveBox's admin."""

from __future__ import annotations

import builtins
from datetime import datetime
from typing import Optional
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from .config import ArchiveBoxConfig, ArchiveBoxConfigError
from .models import ArchiveMethodResult, Snapshot

LOGIN_PATH = "/admin/login/"
ADD_PATH = "/add/"
PUBLIC_INDEX_PATH = "/public/"
SNAPSHOT_CHANGELIST_PATH = "/admin/core/snapshot/"
PULL_ACTION = "update_snapshots"


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

    def add(self, url: str, *, tags: Optional[builtins.list[str]] = None, depth: int = 0) -> Snapshot:
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
    ) -> builtins.list[Snapshot]:
        resp = self._client.get(PUBLIC_INDEX_PATH)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")
        table = soup.find("table", id="table-bookmarks")
        if table is None:
            return []
        snapshots: builtins.list[Snapshot] = []
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

    def method_results(self, snapshot_id: str) -> builtins.list[ArchiveMethodResult]:
        """snapshot_id is the ArchiveBox timestamp (e.g. "1786742943.719284"), same id used
        everywhere else in this backend -- reads /archive/<timestamp>/index.json directly, no
        admin permission needed (this path is public, matching /public/ and /archive/.../*)."""
        resp = self._client.get(f"/archive/{snapshot_id}/index.json")
        resp.raise_for_status()
        history = resp.json().get("history", {})
        results: builtins.list[ArchiveMethodResult] = []
        for method, attempts in history.items():
            if not attempts:
                continue
            latest = max(attempts, key=lambda a: a.get("end_ts") or a.get("start_ts") or "")
            end_ts = None
            raw_end = latest.get("end_ts")
            if raw_end:
                try:
                    end_ts = datetime.fromisoformat(raw_end)
                except ValueError:
                    end_ts = None
            results.append(
                ArchiveMethodResult(
                    method=method,
                    succeeded=latest.get("status") == "succeeded",
                    output=latest.get("output"),
                    end_ts=end_ts,
                )
            )
        return results

    def _find_changelist_row_uuid(self, snapshot_id: str) -> Optional[str]:
        """Resolve an ArchiveBox timestamp to the admin changelist's own row identifier (a
        UUID, unrelated to the timestamp) by searching for it -- needed because the bulk
        action form's _selected_action field takes this UUID, not the timestamp we otherwise
        use as this backend's snapshot id everywhere else."""
        self._login()
        resp = self._client.get(SNAPSHOT_CHANGELIST_PATH, params={"q": snapshot_id}, timeout=60.0)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")
        checkbox = soup.find("input", attrs={"name": "_selected_action"})
        return _attr_str(checkbox["value"]) if checkbox is not None else None

    def pull(self, snapshot_id: str) -> None:
        """Re-run only the archive methods that don't already have a successful result for
        this snapshot (the admin's "Pull" bulk action, update_snapshots) -- does not touch
        files from methods that already succeeded, and does not create a new Snapshot row.
        Raises RuntimeError if the snapshot can't be found on the changelist (e.g. missing
        Django core.view_snapshot permission -- see kb Note #131 -- or a bad snapshot_id).
        A slow-to-archive URL can make this request take a long time or even 504 at the proxy
        while the job keeps running server-side regardless -- call method_results() afterward
        to see the real outcome rather than trusting this call's own return."""
        self._login()
        row_uuid = self._find_changelist_row_uuid(snapshot_id)
        if row_uuid is None:
            raise RuntimeError(
                f"pull({snapshot_id!r}): snapshot not found on {SNAPSHOT_CHANGELIST_PATH} -- "
                "check the id is correct and this account has Django's core.view_snapshot permission"
            )
        resp = self._client.get(SNAPSHOT_CHANGELIST_PATH, params={"q": snapshot_id}, timeout=60.0)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")
        form = soup.find("form", id="changelist-form")
        if form is None:
            raise RuntimeError(f"pull({snapshot_id!r}): no changelist-form found on {SNAPSHOT_CHANGELIST_PATH}")
        csrf_input = form.find("input", attrs={"name": "csrfmiddlewaretoken"})
        payload = {
            "csrfmiddlewaretoken": _attr_str(csrf_input["value"]) if csrf_input is not None else "",
            "action": PULL_ACTION,
            "_selected_action": row_uuid,
            "select_across": "0",
            "index": "0",
        }
        try:
            self._client.post(
                SNAPSHOT_CHANGELIST_PATH,
                params={"q": snapshot_id},
                data=payload,
                headers={"Referer": urljoin(self._config.base_url, SNAPSHOT_CHANGELIST_PATH)},
                timeout=180.0,
            )
        except httpx.HTTPError:
            # A 504 or timeout here doesn't mean the pull failed -- ArchiveBox runs the job
            # server-side independent of whether the proxy stayed connected long enough to
            # relay a response. The caller's method_results() check is the real signal.
            pass
