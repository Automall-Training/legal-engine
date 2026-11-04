"""adapters/__init__: which adapter serves an act, and the shared markdown helpers. No network."""
import datetime as dt
import sys
import unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL / "scripts"))

from watch import adapters  # noqa: E402
from watch.adapters import common, eurlex, legis_md, wayback  # noqa: E402
from watch.contract import FETCH_FAILED  # noqa: E402
from watch.fetchers import FixtureFetcher, fixture_result  # noqa: E402


class AdapterFor(unittest.TestCase):
    def test_each_kind(self):
        self.assertEqual(adapters.adapter_for({"sources": [{"kind": "legis_md", "doc_id": "1"}]}),
                         ("legis_md", legis_md.check_act))
        self.assertEqual(adapters.adapter_for({"sources": [{"kind": "just_ro", "doc_id": "1"}]}),
                         ("just_ro", wayback.check_with_fallback))
        self.assertEqual(adapters.adapter_for({"sources": [{"kind": "eurlex", "celex": "32016R0679"}]}),
                         ("eurlex", eurlex.check_act))

    def test_preference_order(self):
        act = {"sources": [{"kind": "eurlex", "celex": "32016R0679"}, {"kind": "just_ro", "doc_id": "2"},
                           {"kind": "legis_md", "doc_id": "1"}]}
        self.assertEqual(adapters.adapter_for(act)[0], "legis_md")
        act["sources"] = act["sources"][:2]
        self.assertEqual(adapters.adapter_for(act)[0], "just_ro")

    def test_no_usable_source(self):
        self.assertEqual(adapters.adapter_for({"sources": [{"kind": "monitorul_md"}]}), (None, None))
        self.assertEqual(adapters.adapter_for({}), (None, None))
        self.assertEqual(adapters.adapter_for({"sources": ["junk"]}), (None, None))

    def test_every_adapter_has_the_common_signature(self):
        act = {"id": "x", "sources": []}
        for name, fn in adapters.ADAPTERS.items():
            with self.subTest(name=name):
                res = fn(act, FixtureFetcher({}), dt.date(2026, 11, 4))
                self.assertEqual(res.status, FETCH_FAILED)


class Markdown(unittest.TestCase):
    def test_md_to_text_strips_markdown(self):
        t = common.md_to_text("_MODIFICAT_\n\n_[LP1 din 01.01.25, MO1/01.01.25 art.1; în vigoare 01.02.25](https://x)_\n"
                              "| a | b |<br>c\n**Articolul 1.** x\n| --- | --- |\n# Head")
        self.assertIn("MODIFICAT", t)
        self.assertIn("LP1 din 01.01.25", t)
        self.assertNotIn("](", t)
        self.assertNotIn("**", t)
        self.assertIn("Articolul 1.", t)
        self.assertNotIn("---", t)
        self.assertIn("Head", t)

    def test_is_markdown_and_page_text(self):
        md = fixture_result("u", "", markdown="**a** [b](c)")
        self.assertTrue(common.is_markdown(md))
        self.assertEqual(common.page_text(md), "a b")
        html = fixture_result("u", "<html><body>hello</body></html>")
        self.assertFalse(common.is_markdown(html))
        self.assertEqual(common.page_text(html), "hello")

    def test_source_doc_id(self):
        act = {"sources": [{"kind": "legis_md"}, {"kind": "legis_md", "doc_id": 155185}]}
        self.assertEqual(common.source_doc_id(act, "legis_md"), "155185")
        self.assertIsNone(common.source_doc_id(act, "just_ro"))


if __name__ == "__main__":
    unittest.main()
