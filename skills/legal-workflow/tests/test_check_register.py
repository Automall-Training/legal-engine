"""Synthetic register invariants; these tests do not establish current law."""

import contextlib
import io
import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import check_register as L  # noqa: E402

ASSET = Path(__file__).resolve().parents[1] / "assets" / "source-register.json"


TASK = f"2026-01-01-synthetic@{datetime.now().astimezone().date().isoformat()}"


def register():
    now = datetime.now(timezone.utc).isoformat()
    return {"schema_version": 1, "task_id": TASK, "started_at": now, "checked_at": now,
            "analysis_date": "2026-01-01", "completion": "verified_scope",
            "sources": [{"id": "S1", "title": "SYNTHETIC ACT — NOT LAW", "number": "TEST", "jurisdiction": "TEST",
                         "authority_type": "synthetic", "legal_force": "test fixture only", "provision": "art. 1",
                         "version": "test v1", "version_from": "2025-01-01", "version_to": None,
                         "applies_from": "2025-01-01", "url": "https://example.invalid/synthetic-law",
                         "opened_at": now, "official_text": True, "status": "verified",
                         "applicability": "Synthetic temporal test only", "related_findings": ["F1"],
                         "checks": {k: {"done": True, "note": "Synthetic fixture, not a retrieval"} for k in L.CHECKS}}],
            "findings": [{"id": "F1", "kind": "mandatory", "basis_kind": "law", "material": True,
                          "status": "verified", "conclusion": "Synthetic test claim", "source_ids": ["S1"]}]}


class RegisterTests(unittest.TestCase):
    def check(self, r):
        return L.validate(r, TASK, datetime.now().astimezone())

    def test_complete_synthetic_record(self):
        result = self.check(register())
        self.assertEqual(result["errors"], [])
        self.assertFalse(result["legal_truth_checked"])

    def test_future_norm_cannot_support_current_mandatory_claim(self):
        r = register()
        r["sources"][0]["applies_from"] = "2027-01-01"
        self.assertTrue(self.check(r)["errors"])

    def test_future_notice_is_distinct(self):
        r = register()
        r["sources"][0].update(status="future", applies_from="2027-01-01")
        r["findings"][0]["temporal_role"] = "future_notice"
        self.assertEqual(self.check(r)["errors"], [])

    def test_future_status_already_applicable_rejected(self):
        r = register()
        r["sources"][0]["status"] = "future"
        self.assertTrue(any("already applies" in e for e in self.check(r)["errors"]))

    def test_expired_version_rejected(self):
        r = register()
        r["sources"][0]["version_to"] = "2025-12-31"
        self.assertTrue(self.check(r)["errors"])

    def test_unavailable_source_blocks_completed_audit(self):
        r = register()
        r["sources"][0].update(status="unavailable", unverified_impact="F1 unresolved")
        self.assertTrue(self.check(r)["errors"])

    def test_partial_work_allowed_and_disclosed(self):
        r = register()
        r["completion"] = "partial"
        r["sources"][0].update(status="unavailable", unverified_impact="Cannot verify norm")
        r["findings"][0].update(status="unverified", unverified_impact="Cannot conclude validity")
        result = self.check(r)
        self.assertEqual(result["errors"], [])
        self.assertTrue(result["unresolved"])

    def test_reused_task_rejected(self):
        r = register()
        r["task_id"] = "old-task"
        self.assertTrue(self.check(r)["errors"])

    def test_task_id_must_carry_the_check_date(self):
        r = register()
        r["task_id"] = "2026-01-01-synthetic@2026-01-01"
        errors = L.validate(r, r["task_id"], datetime.now().astimezone())["errors"]
        self.assertTrue(any("check date" in e for e in errors))

    def test_yesterday_check_rejected(self):
        r = register()
        old = "2020-01-01T10:00:00+00:00"
        r.update(started_at=old, checked_at=old)
        r["sources"][0]["opened_at"] = old
        self.assertTrue(any("not from today" in e for e in self.check(r)["errors"]))

    def test_timestamp_without_zone_is_schema_error(self):
        r = register()
        r["started_at"] = "2026-01-01T10:00:00"
        self.assertTrue(any("timezone" in e for e in self.check(r)["errors"]))

    def test_unchecked_article_history_rejected(self):
        r = register()
        r["sources"][0]["checks"]["renumbering"]["done"] = False
        self.assertTrue(self.check(r)["errors"])

    def test_practice_cannot_be_mandatory(self):
        r = register()
        r["findings"][0]["basis_kind"] = "practice"
        self.assertTrue(self.check(r)["errors"])

    def test_links_must_be_mutual(self):
        r = register()
        r["sources"][0]["related_findings"] = ["F9"]
        errors = self.check(r)["errors"]
        self.assertTrue(any("unknown finding F9" in e for e in errors))
        self.assertTrue(any("missing reverse source link" in e for e in errors))

    def test_other_schema_version_rejected(self):
        r = register()
        r["schema_version"] = 2
        self.assertTrue(any("schema_version" in e for e in self.check(r)["errors"]))

    def test_shipped_template_is_partial_until_filled(self):
        tpl = json.loads(ASSET.read_text(encoding="utf-8"))
        self.assertEqual(tpl["completion"], "partial")
        self.assertEqual(set(tpl["sources"][0]["checks"]), set(L.CHECKS))
        self.assertTrue(L.validate(tpl, tpl["task_id"], datetime.now(timezone.utc))["errors"])


class CliTests(unittest.TestCase):
    def run_cli(self, *argv):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = L.main(list(argv))
        return code, json.loads(out.getvalue())

    def test_exit_codes(self):
        with tempfile.TemporaryDirectory() as tmp:
            good = Path(tmp) / "source-register.json"
            good.write_text(json.dumps(register()), encoding="utf-8")
            self.assertEqual(self.run_cli(str(good), "--task-id", TASK)[0], 0)
            self.assertEqual(self.run_cli(str(good), "--task-id", "other")[0], 1)
            bad = Path(tmp) / "bad.json"
            bad.write_text("{not json", encoding="utf-8")
            code, out = self.run_cli(str(bad), "--task-id", "x")
            self.assertEqual(code, 2)
            self.assertIn("cannot read", out["error"])
            arr = Path(tmp) / "arr.json"
            arr.write_text("[]", encoding="utf-8")
            self.assertEqual(self.run_cli(str(arr), "--task-id", "x")[0], 2)


if __name__ == "__main__":
    unittest.main()
