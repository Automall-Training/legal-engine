"""Regression tests for what the live run of step 10 (2026-11-05) found."""

from __future__ import annotations

import datetime as dt
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SKILL = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SKILL / "scripts"))
from watch import manual, runner  # noqa: E402
from watch.adapters import cellar  # noqa: E402

from watch.contract import NEW_IN_FORCE, PARSE_FAILED, UNCHANGED, Redaction, classify, text_sha256  # noqa: E402
from watch.fetchers import FetchResult  # noqa: E402


def _can_symlink() -> bool:
    """why: ordinary Windows (no admin, no Developer Mode) refuses symlinks; such tests are skipped there and
    directory links fall back to a junction, which any user may create."""
    with tempfile.TemporaryDirectory() as tmp:
        try:
            os.symlink(tmp, os.path.join(tmp, "probe"), target_is_directory=True)
        except (OSError, NotImplementedError):
            return False
    return True


CAN_SYMLINK = _can_symlink()


def link_dir(link: Path, target: Path) -> None:
    """A directory link: a symlink where allowed, otherwise a Windows junction."""
    if CAN_SYMLINK:
        link.symlink_to(target, target_is_directory=True)
    else:
        import _winapi  # Windows only: CPython's own junction call, no admin rights needed
        _winapi.CreateJunction(str(target), str(link))

BODY = "<html><head><title>Directive 2011/83/EU</title></head><body><p>Directive 2011/83/EU text</p></body></html>"


class CellarTextIsKept(unittest.TestCase):
    """EU acts read via Cellar had no snapshot: the text was fetched by Cellar's own getter and then dropped."""

    def test_paced_getter_keeps_delivered_pages_only(self):
        g = runner.PacedCellarGet(pause_range=(0, 0))
        with mock.patch("watch.adapters.cellar.urllib_get", side_effect=[(200, "u1", BODY), (404, "u2", "")]):
            g("u1", {})
            g("u2", {})
        self.assertEqual(list(g.pages), ["u1"])

    def test_official_text_matches_the_hash_of_the_reading(self):
        g = runner.PacedCellarGet(pause_range=(0, 0))
        g.pages["u1"] = BODY
        rec = runner.RecordingFetcher(None)
        text = runner.official_text("u1", rec, g)
        # the adapter hashes exactly this text, so the snapshot file name matches evidence.sha256
        self.assertEqual(text_sha256(text), text_sha256(cellar.page_text(BODY)[1]))
        self.assertIn("2011/83", text)
        self.assertEqual(g.pages, {})   # released after use
        self.assertIsNone(runner.official_text("u1", rec, g))

    def test_engine_page_comes_first_and_none_without_cellar(self):
        rec = runner.RecordingFetcher(None)
        rec.pages["u"] = FetchResult(url="u", final_url="u", status=200, text="page text", markdown=None)
        self.assertEqual(runner.official_text("u", rec, None), "page text")
        self.assertIsNone(runner.official_text("other", rec, None))


class DateWinsOverLabel(unittest.TestCase):
    """Codex review: a held `v1` of January and a read `v1` of October were taken as the same version."""

    def run_one(self, held, read):
        act = {"id": "ro.lege.1-2020", "current": held}
        st, *_ = classify(act=act, parsed=[Redaction(label=read[0], in_force_from=read[1])],
                          today=dt.date(2026, 11, 5), repealed=False)
        return st

    def test_same_label_newer_date_is_a_change(self):
        self.assertEqual(self.run_one({"label": "v1", "in_force_from": "2026-01-01"}, ("v1", "2026-10-01")),
                         NEW_IN_FORCE)

    def test_same_label_older_date_is_not_verified(self):
        self.assertEqual(self.run_one({"label": "v1", "in_force_from": "2026-10-01"}, ("v1", "2026-01-01")),
                         PARSE_FAILED)

    def test_label_decides_only_without_a_held_date(self):
        self.assertEqual(self.run_one({"label": "v1", "in_force_from": None}, ("v1", "2026-01-01")), UNCHANGED)


class CellarAmendments(unittest.TestCase):
    """Codex review: Cellar confirmed "unchanged" despite "not in force" or an amendment not yet consolidated."""

    TODAY = dt.date(2026, 11, 5)
    TEXT = "<html><title>R</title><body>" + "Regulation (EU) 2016/679 text. " * 200 + "</body></html>"

    def meta(self, **kw):
        m = {"in_force": True, "end": None, "entry": ["2016-05-24"], "date_document": "2016-04-27",
             "consolidations": {"2016-05-04": "02016R0679-20160504"}, "repealed_by": [], "amended_by": [],
             "corrections": [], "proposals": [], "urls": [], "found": True}
        m.update(kw)
        return m

    def check(self, meta, held_related):
        act = {"id": "eu.reg.2016-679", "sources": [{"kind": "eurlex", "celex": "32016R0679"}],
               "current": {"label": "consolidare 04.05.2016", "in_force_from": "2016-05-04"},
               "related": held_related}
        with mock.patch.object(cellar, "metadata", return_value=meta):
            return cellar.check_act(act, self.TODAY, get=lambda url, headers: (200, url, self.TEXT))

    def test_unchanged_records_the_list(self):
        r = self.check(self.meta(corrections=["32018R0679R(02)"]), None)
        self.assertEqual((r.status, r.related), (UNCHANGED, ["32018R0679R(02)"]))

    def test_new_corrigendum_is_not_verified(self):
        r = self.check(self.meta(corrections=["32018R0679R(02)", "32026R0679R(09)"]), ["32018R0679R(02)"])
        self.assertEqual(r.status, PARSE_FAILED)
        self.assertIn("32026R0679R(09)", r.error)

    def test_not_in_force_without_repeal_is_not_verified(self):
        r = self.check(self.meta(in_force=False), [])
        self.assertEqual(r.status, PARSE_FAILED)
        self.assertIn("not in force", r.error)

    def test_list_history_is_kept(self):
        """Codex round 2: a hand check or a non-Cellar reading erased the list, so a new item passed unseen."""
        state = {"acts": {"eu.reg.2016-679": {"related": ["a"]}}, "signals": {}}
        base = {"act_id": "eu.reg.2016-679", "checked": True, "status": "unchanged", "current": {}, "next": None}
        runner.update_state(state, {**base, "related": None, "evidence": {"via": "urllib"}}, "2026-11-05", None)
        self.assertEqual(state["acts"]["eu.reg.2016-679"]["related"], ["a"])        # no list read: kept
        runner.update_state(state, {**base, "evidence": {"via": "host"}}, "2026-11-05", None)
        self.assertEqual(state["acts"]["eu.reg.2016-679"]["related"], ["a"])        # nothing reviewed: kept
        runner.update_state(state, {**base, "related_reviewed": ["a", "b"], "evidence": {"via": "host"}},
                            "2026-11-05", None)
        self.assertEqual(state["acts"]["eu.reg.2016-679"]["related"], ["a", "b"])   # reviewed by hand: resolved
        runner.update_state(state, {**base, "related": ["a", "b", "c"], "evidence": {"via": "urllib"}},
                            "2026-11-05", None)
        self.assertEqual(state["acts"]["eu.reg.2016-679"]["related"], ["a", "b", "c"])


class CardAmendmentsCount(unittest.TestCase):
    """Codex review: a card naming an amendment in force, with the old consolidation, was recorded "unchanged"."""

    def card(self, changes):
        return {"act": {"id": "ro.lege.1-2020"}, "result": "outdated", "checked_at": "2026-11-05T10:00:00+02:00",
                "latest_in_force": {"label": "v1", "version_from": "2026-01-01"}, "next_versions": [],
                "changes": changes, "repealed": {"by": None, "from": None}, "points": {}}

    def test_amendment_in_force_is_a_new_version(self):
        act = {"id": "ro.lege.1-2020", "current": {"label": "v1", "in_force_from": "2026-01-01"}}
        ch = [{"act": "Legea nr. 9/2026", "published": "2026-09-01", "status": "in_force", "applies_from": "2026-10-01"}]
        r = manual.card_to_result(act, self.card(ch), dt.date(2026, 11, 5), text="text")
        self.assertEqual((r.status, r.current.in_force_from), (NEW_IN_FORCE, "2026-10-01"))

    def test_adopted_amendment_is_a_next_version(self):
        act = {"id": "ro.lege.1-2020", "current": {"label": "v1", "in_force_from": "2026-01-01"}}
        ch = [{"act": "Legea nr. 9/2026", "published": "2026-10-01", "status": "published_not_in_force",
               "applies_from": "2027-01-01"}]
        r = manual.card_to_result(act, self.card(ch), dt.date(2026, 11, 5), text="text")
        self.assertEqual((r.status, r.next.in_force_from), ("new_future", "2027-01-01"))

    def test_draft_changes_nothing(self):
        act = {"id": "ro.lege.1-2020", "current": {"label": "v1", "in_force_from": "2026-01-01"}}
        ch = [{"act": "PL-x 1/2026", "published": "2026-10-01", "status": "draft"}]
        r = manual.card_to_result(act, self.card(ch), dt.date(2026, 11, 5), text="text")
        self.assertEqual(r.status, UNCHANGED)


class DocxClausesInOrder(unittest.TestCase):
    """Codex review: table cells were read after the body and as one string, so clauses got the wrong laws."""

    def test_tables_in_order_and_cell_paragraphs_apart(self):
        import tempfile

        import docx
        from watch import clauses
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "c.docx"
            d = docx.Document()
            d.add_paragraph("4.1. Părțile convin.")
            cell = d.add_table(rows=1, cols=2).cell(0, 0)
            cell.text = "5.2. Prețul se plătește conform Legii nr. 227/2015."
            cell.add_paragraph("5.3. Datele se prelucrează conform Legii nr. 190/2018.")
            d.add_paragraph("6.1. Litigiile se soluționează amiabil.")
            d.save(path)
            text = clauses.contract_text(path)
            self.assertEqual([x[:4] for x in text if x], ["4.1.", "5.2.", "5.3.", "6.1."])
            found = clauses.scan(path, "RO")
            got = {c["clause"]: [a["id"] for a in c["acts"]] for c in found["clauses"]}
            self.assertEqual(got.get("5.2"), ["ro.lege.227-2015"])
            self.assertEqual(got.get("5.3"), ["ro.lege.190-2018"])


class ProfileNeverInsideEngine(unittest.TestCase):
    """Codex review: `--profile` into the checkout, or a link in the profile into it, was accepted."""

    def test_explicit_profile_inside_engine_is_refused(self):
        import legal_watch as cli
        from watch import library as lib
        with self.assertRaises(lib.WatchError):
            cli.resolve_profile(str(lib.ENGINE_ROOT / "legal-profile"))

    def test_link_inside_profile_into_engine_is_refused(self):
        import tempfile
        from watch import library as lib
        with tempfile.TemporaryDirectory() as tmp:
            link_dir(Path(tmp) / "laws", lib.ENGINE_ROOT / "skills")
            with self.assertRaises(lib.WatchError):
                lib.write_atomic(Path(tmp) / "laws" / "state.json", "{}")
            self.assertFalse((lib.ENGINE_ROOT / "skills" / "state.json").exists())


if __name__ == "__main__":
    unittest.main()
