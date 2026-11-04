"""Source adapters: one official source each, all returning `contract.AdapterResult` for one act.

Every adapter is `fn(act, fetcher, today) -> AdapterResult`; the fetcher is any object with
`get(url) -> FetchResult` (see `fetchers.py`), so the adapters never depend on a fetch engine.

- legis_md — `legis_md.check_act`: the Moldovan State Register of Legal Acts;
- just_ro  — `wayback.check_with_fallback`: the Romanian legislative portal, with the Wayback copy as an
             unverified fallback (`stale_fallback`) when the portal cannot be read;
- eurlex   — `eurlex.check_act`: EUR-Lex, with Cellar as a fallback when EUR-Lex is blocked or down.

`monitorul_md.scan` is not in this table: it reads the Moldovan Official Gazette for signals and gives a
`SourceScan`, not a status of an act.
"""
from __future__ import annotations

from typing import Callable

from . import eurlex, legis_md, wayback

ADAPTERS: dict[str, Callable] = {
    "legis_md": legis_md.check_act,
    "just_ro": wayback.check_with_fallback,
    "eurlex": eurlex.check_act,
}
# When an act lists several sources, the national register of its own jurisdiction is preferred.
PREFERENCE = ("legis_md", "just_ro", "eurlex")


def adapter_for(act: dict) -> tuple[str | None, Callable | None]:
    """(name, fn) of the adapter for the act's first usable source in PREFERENCE order, or (None, None)."""
    kinds = {s.get("kind") for s in act.get("sources") or [] if isinstance(s, dict)}
    for name in PREFERENCE:
        if name in kinds:
            return name, ADAPTERS[name]
    return None, None
