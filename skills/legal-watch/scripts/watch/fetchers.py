"""Fetch engines for the monitoring adapters.

Adapters never depend on an engine: they take any object with `get(url) -> FetchResult`. The engines:

- `urllib`     — the standard library, free; plain GET. Several official portals refuse it (anti-bot pages, dropped
                 connections); that becomes an honest failure, never "unchanged".
- `playwright` — a local browser through Playwright (free; installed with `WITH_PLAYWRIGHT=1 ./install.sh`,
                 on Windows `$env:WITH_PLAYWRIGHT=1; .\\install.ps1`).
- `command`    — a command the user configured themselves (for example a paid scraping service wrapped in their
                 own script). The engine runs it with the URL and reads the page from stdout; it never sees, asks
                 for or stores a key.
- `host`       — not a fetcher: the agent opens the page with its own web tools and records a version card
                 (`legal_watch.py record`).

`ChainFetcher` tries the engines in order and falls to the next on an error or an anti-bot page; the result
names the engine that produced it (`via`). Rules for every engine: GET only, public pages, no forms, logins or
clicks; an anti-bot or CAPTCHA page is reported as blocked and never bypassed.
"""
from __future__ import annotations

import datetime as _dt
import os
import random
import re
import shlex
import subprocess
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Protocol
from urllib.parse import urlparse

USER_AGENT = "Mozilla/5.0 (compatible; legal-engine-watch/1.0)"
PAUSE_RANGE_S = (5.0, 15.0)   # politeness between requests to the same portals
TIMEOUT_S = 45
SETTLE_MS = 3_000
ENGINES = ("urllib", "playwright", "command")

# Signs of an anti-bot check page. A match means blocked, without any interaction.
STRONG_MARKERS = (
    "just a moment", "doar un moment", "attention required", "cf-chl", "challenge-platform",
    "cf-browser-verification", "cf_chl_opt", "checking your browser", "efectuarea verificării de securitate",
    "verify you are human",
)
# CAPTCHA widgets also sit on ordinary pages (a newsletter form), so they count only on a near-empty page.
WIDGET_MARKERS = ("g-recaptcha", "h-captcha", "cf-turnstile")
WIDGET_PAGE_MAX_TEXT = 1500


class FetchConfigError(ValueError):
    """The engine settings are unusable (unknown engine, a command without `{url}`)."""


@dataclass
class FetchResult:
    url: str
    status: int | None            # HTTP status of the main document; None when there was no answer
    final_url: str | None = None
    title: str = ""
    html: str = ""
    text: str = ""                # visible text
    fetched_at: str = ""
    error: str | None = None      # network error or timeout
    blocked: bool = False         # anti-bot page or HTTP 403
    blocked_reason: str | None = None
    subresource_403: list[str] = field(default_factory=list)
    via: str = "urllib"
    markdown: str = ""            # when an engine returns markdown instead of HTML
    notes: list[str] = field(default_factory=list)


class Fetcher(Protocol):
    def get(self, url: str) -> FetchResult: ...


def now_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def detect_challenge(status: int | None, title: str, html: str, text: str | None = None) -> str | None:
    """The reason a page is an anti-bot page, or None."""
    low_title = (title or "").lower()
    low_html = (html or "")[:200_000].lower()
    for m in STRONG_MARKERS:
        if m in low_title or m in low_html:
            return f"challenge marker: {m!r}"
    if text is not None and len(text.strip()) < WIDGET_PAGE_MAX_TEXT:
        for m in WIDGET_MARKERS:
            if m in low_html:
                return f"captcha widget on near-empty page: {m!r}"
    if status in (403, 429, 503) and ("cloudflare" in low_html or "cf-ray" in low_html):
        return f"HTTP {status} from Cloudflare"
    if status == 403:
        return "HTTP 403"
    return None


def html_to_text(html: str) -> str:
    """A rough innerText: scripts and styles dropped, tags to line breaks, entities decoded."""
    import html as _html
    body = re.sub(r"(?is)<(script|style|noscript)\b.*?</\1>", " ", html or "")
    body = re.sub(r"(?s)<[^>]+>", "\n", body)
    body = _html.unescape(body)
    return re.sub(r"\n\s*\n+", "\n", body).strip()


def _title(html: str) -> str:
    m = re.search(r"<title[^>]*>(.*?)</title>", html or "", re.S | re.I)
    return re.sub(r"\s+", " ", m.group(1)).strip() if m else ""


def page_result(url: str, html: str, *, status: int | None = 200, via: str, final_url: str | None = None,
                fetched_at: str | None = None, markdown: str = "") -> FetchResult:
    """A FetchResult from a page body; the anti-bot check is applied here for every engine."""
    text = html_to_text(html) if html else markdown
    title = _title(html)
    reason = detect_challenge(status, title, html, text)
    return FetchResult(url=url, status=status, final_url=final_url or url, title=title, html=html, text=text,
                       fetched_at=fetched_at or now_iso(), blocked=reason is not None, blocked_reason=reason,
                       via=via, markdown=markdown)


class _Paced:
    """A pause before every request but the first: official portals are public services, not a load test."""

    def __init__(self, pause_range=PAUSE_RANGE_S, sleep: Callable[[float], None] = time.sleep):
        self.pause_range, self.sleep, self._n = pause_range, sleep, 0

    def pause(self) -> None:
        if self._n > 0 and self.pause_range[1] > 0:
            self.sleep(random.uniform(*self.pause_range))
        self._n += 1


class UrllibFetcher(_Paced):
    def __init__(self, *, timeout: float = TIMEOUT_S, opener=urllib.request.urlopen, **kw):
        super().__init__(**kw)
        self.timeout, self.opener = timeout, opener

    def get(self, url: str) -> FetchResult:
        self.pause()
        fetched_at = now_iso()
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept-Language": "ro,en;q=0.8"})
        try:
            with self.opener(req, timeout=self.timeout) as r:
                body = r.read().decode(r.headers.get_content_charset() or "utf-8", "replace")
                return page_result(url, body, status=r.status, via="urllib", final_url=r.geturl(),
                                   fetched_at=fetched_at)
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "replace") if e.fp else ""
            res = page_result(url, body, status=e.code, via="urllib", fetched_at=fetched_at)
            if not res.blocked:
                res.error = f"HTTP {e.code}"
            return res
        except Exception as e:  # noqa: BLE001 — any network failure is "not verified" for the adapter
            return FetchResult(url=url, status=None, fetched_at=fetched_at, via="urllib",
                               error=f"{type(e).__name__}: {str(e).splitlines()[0][:300] if str(e) else ''}")


def quote_url(url: str, windows: bool | None = None) -> str:
    """One shell argument for the URL.
    why: the command runs through the system shell, `sh` on Mac/Linux, `cmd.exe` on Windows; cmd does not know
    single quotes, so there the URL goes in double quotes (a URL has no raw `"`; one is percent-encoded anyway)."""
    windows = os.name == "nt" if windows is None else windows
    return '"' + url.replace('"', "%22") + '"' if windows else shlex.quote(url)


class CommandFetcher(_Paced):
    """Runs the user's own command; `{url}` in it is replaced by the page URL (shell-quoted).

    The command prints the page (HTML or markdown) to stdout. Its credentials, if any, live in the user's own
    setup; this class passes only the URL.
    """

    def __init__(self, command: str, *, timeout: float = 120, run=subprocess.run, **kw):
        super().__init__(**kw)
        if "{url}" not in command:
            raise FetchConfigError("fetch command must contain {url}")
        self.command, self.timeout, self.run = command, timeout, run

    def get(self, url: str) -> FetchResult:
        self.pause()
        fetched_at = now_iso()
        cmd = self.command.replace("{url}", quote_url(url))
        try:
            # why: pages are read as UTF-8 on every system (Windows would decode with its ANSI code page)
            p = self.run(cmd, shell=True, capture_output=True, text=True, encoding="utf-8", errors="replace",
                         timeout=self.timeout)
        except Exception as e:  # noqa: BLE001
            return FetchResult(url=url, status=None, fetched_at=fetched_at, via="command",
                               error=f"command failed: {type(e).__name__}")
        if p.returncode != 0 or not p.stdout.strip():
            # stderr may echo the user's setup; only its length is kept, never its content.
            return FetchResult(url=url, status=None, fetched_at=fetched_at, via="command",
                               error=f"command exit {p.returncode}, {len(p.stdout)} bytes of output")
        out = p.stdout
        if "<html" in out[:2000].lower() or "<body" in out[:5000].lower():
            return page_result(url, out, via="command", fetched_at=fetched_at)
        return page_result(url, "", via="command", fetched_at=fetched_at, markdown=out)


class BrowserBusy(RuntimeError):
    """Another monitoring run holds the browser profile."""


def try_lock(fh) -> bool:
    """Take an exclusive lock on an open file without waiting; False when another process holds it.
    why: fcntl exists only on Mac/Linux and msvcrt only on Windows; both locks die with the process, so a crashed
    run never leaves the browser profile locked."""
    if os.name == "nt":
        import msvcrt
        fh.seek(0)
        try:
            msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)   # the first byte stands for the whole file
        except OSError:
            return False
        return True
    import fcntl
    try:
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        return False
    return True


def unlock(fh) -> None:
    if os.name == "nt":
        import msvcrt
        fh.seek(0)
        msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
    else:
        import fcntl
        fcntl.flock(fh.fileno(), fcntl.LOCK_UN)


class PlaywrightFetcher(_Paced):
    """A context manager: one persistent browser profile per run (kept in the user's profile, never here)."""

    def __init__(self, profile_dir: Path, *, headless: bool = True, channel: str | None = None,
                 nav_timeout_ms: int = TIMEOUT_S * 1000, **kw):
        super().__init__(**kw)
        self.profile_dir, self.headless, self.channel = Path(profile_dir), headless, channel
        self.nav_timeout_ms = nav_timeout_ms
        self._pw = self._ctx = self._lock = None

    def __enter__(self):
        from playwright.sync_api import sync_playwright  # imported here: tests and urllib runs need no Playwright

        self.profile_dir.mkdir(parents=True, exist_ok=True)
        self._lock = open(self.profile_dir.parent / (self.profile_dir.name + ".lock"), "a+", encoding="utf-8")
        if not try_lock(self._lock):
            self._lock.close()
            self._lock = None
            raise BrowserBusy(f"browser profile {self.profile_dir} is used by another run; run them one by one")
        self._pw = sync_playwright().start()
        opts = {"user_data_dir": str(self.profile_dir), "headless": self.headless, "accept_downloads": False,
                "locale": "ro-RO"}
        if self.channel:
            opts["channel"] = self.channel
        self._ctx = self._pw.chromium.launch_persistent_context(**opts)
        self._ctx.set_default_navigation_timeout(self.nav_timeout_ms)
        return self

    def __exit__(self, *exc):
        try:
            if self._ctx is not None:
                self._ctx.close()
        finally:
            if self._pw is not None:
                self._pw.stop()
            if self._lock is not None:
                unlock(self._lock)
                self._lock.close()
        return False

    def get(self, url: str) -> FetchResult:
        self.pause()
        fetched_at = now_iso()
        page = self._ctx.new_page()
        host = re.sub(r"^https?://([^/]+).*$", r"\1", url)
        sub403: list[str] = []
        page.on("response", lambda resp: sub403.append(resp.url)
                if resp.status == 403 and host in resp.url and resp.url != url else None)
        try:
            resp = page.goto(url, wait_until="domcontentloaded", timeout=self.nav_timeout_ms)
            page.wait_for_timeout(SETTLE_MS)
            status = resp.status if resp is not None else None
            html, title = page.content(), page.title()
            try:
                text = page.inner_text("body", timeout=10_000)
            except Exception:  # noqa: BLE001
                text = ""
            reason = detect_challenge(status, title, html, text)
            return FetchResult(url=url, status=status, final_url=page.url, title=title, html=html, text=text,
                               fetched_at=fetched_at, blocked=reason is not None, blocked_reason=reason,
                               subresource_403=sub403, via="playwright")
        except Exception as e:  # noqa: BLE001
            return FetchResult(url=url, status=None, fetched_at=fetched_at, via="playwright",
                               error=f"{type(e).__name__}: {str(e).splitlines()[0][:300] if str(e) else ''}",
                               subresource_403=sub403)
        finally:
            page.close()


class ChainFetcher:
    """Engines in order; the next one is tried when a page failed or was an anti-bot page.

    `demote`: site → engines to try last there (from the error log: they kept failing on that site, so waiting
    for them first on every act only costs time). A demoted engine still runs when nothing before it worked.
    Every engine tried is kept in `attempts` for the error log.
    """

    def __init__(self, fetchers: list[Fetcher], *, names: list[str] | None = None,
                 demote: dict[str, set[str]] | None = None):
        if not fetchers:
            raise FetchConfigError("no fetch engine configured")
        self.fetchers = fetchers
        self.names = names or [getattr(f, "via", f"engine{i}") for i, f in enumerate(fetchers)]
        self.demote = demote or {}
        self.attempts: list[dict] = []

    def _order(self, host: str | None) -> tuple[list[tuple[str, Fetcher]], list[str]]:
        pairs = list(zip(self.names, self.fetchers))
        late = self.demote.get(host or "", set())
        if not late or len(pairs) < 2:
            return pairs, []
        first = [p for p in pairs if p[0] not in late]
        return first + [p for p in pairs if p[0] in late], [n for n, _ in pairs if n in late]

    def get(self, url: str) -> FetchResult:
        host = urlparse(url).hostname
        pairs, moved = self._order(host)
        tried: list[str] = []
        res = None
        for name, f in pairs:
            res = f.get(url)
            ok = not res.error and not res.blocked and res.status is not None and res.status < 400
            self.attempts.append({"host": host, "via": res.via or name, "ok": ok, "http_status": res.status,
                                  "error": None if ok else (res.error or res.blocked_reason or f"HTTP {res.status}")})
            if ok:
                break
            tried.append(f"{res.via}: {res.error or res.blocked_reason or f'HTTP {res.status}'}")
        if tried and res is not None:
            res.notes = [f"engine failed, next tried: {t}" for t in tried if not t.startswith(res.via + ":")] \
                + list(res.notes)
        if moved and res is not None:
            res.notes = [f"tried last on {host}: {', '.join(moved)} (refused there in recent runs, see the error log)"] \
                + list(res.notes)
        return res


class HostOnly:
    """The `host` engine alone: scripts fetch nothing, every act waits for a check by hand."""

    def get(self, url: str) -> FetchResult:
        return FetchResult(url=url, status=None, fetched_at=now_iso(), via="host",
                           error="engine 'host' only: no automatic reading; check by hand and record a version card")


class FixtureFetcher:
    """Tests and offline runs: url → FetchResult; an unknown URL is a fetch error."""

    def __init__(self, mapping: dict[str, FetchResult]):
        self.mapping = mapping
        self.calls: list[str] = []

    def get(self, url: str) -> FetchResult:
        self.calls.append(url)
        if url not in self.mapping:
            return FetchResult(url=url, status=None, fetched_at="2026-11-04T07:00:00Z", via="fixture",
                               error="FixtureFetcher: no fixture for url")
        return self.mapping[url]


def fixture_result(url: str, html: str, *, status: int = 200, title: str | None = None, text: str | None = None,
                   via: str = "fixture", markdown: str = "") -> FetchResult:
    """A FetchResult from saved HTML (or markdown), as an engine would return it."""
    res = page_result(url, html, status=status, via=via, fetched_at="2026-11-04T07:00:00Z", markdown=markdown)
    if title is not None:
        res.title = title
    if text is not None:
        res.text = text
    reason = detect_challenge(status, res.title, html, res.text)
    res.blocked, res.blocked_reason = reason is not None, reason
    return res


def build_chain(engines: list[str], *, command: str | None = None, browser_dir: Path | None = None,
                stack=None, pause_range=PAUSE_RANGE_S, demote: dict[str, set[str]] | None = None) -> ChainFetcher:
    """Engines named in the watchlist → a ChainFetcher. `stack` is an ExitStack that owns the browser."""
    out: list[Fetcher] = []
    for name in engines:
        if name == "urllib":
            out.append(UrllibFetcher(pause_range=pause_range))
        elif name == "command":
            if not command:
                raise FetchConfigError("engine 'command' needs settings.fetch_command")
            out.append(CommandFetcher(command, pause_range=pause_range))
        elif name == "playwright":
            if stack is None or browser_dir is None:
                raise FetchConfigError("engine 'playwright' needs a browser profile folder")
            out.append(stack.enter_context(PlaywrightFetcher(browser_dir, pause_range=pause_range)))
        else:
            raise FetchConfigError(f"unknown engine {name!r}; allowed: {', '.join(ENGINES)}")
    return ChainFetcher(out, names=list(engines), demote=demote)
