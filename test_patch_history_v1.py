import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from patch_history_v1 import OFFICIAL_ARTICLE, parse_patch_records
import history

NOW="2026-11-25T20:00:00Z"
HTML="""<article><h1 data-testid="page-title">Grand Theft Auto VI Launch Updates (PS5 / XBOX Series X|S)</h1>
<p>Last Updated: November 25, 2026</p>
<h2>[November 25, 2026] - General</h2><ul><li>Fixed a synthetic test issue</li><li>Improved a synthetic test feature</li></ul>
<p>[November 23, 2026] - General</p><ul><li><p>Fixed a previous synthetic test issue</p></li></ul>
<h3>Still need help?</h3><ul><li>Contact support</li></ul></article>"""

class PatchHistoryTests(unittest.TestCase):
    def test_official_metadata_separates_dates_and_never_mirrors_notes(self):
        records=parse_patch_records(HTML,OFFICIAL_ARTICLE,NOW)
        self.assertEqual([r["occurred_at"] for r in records],["2026-11-23","2026-11-25"])
        self.assertEqual([r["metadata"]["entry_count"] for r in records],[1,2])
        self.assertNotIn("synthetic test issue",json.dumps(records))
        self.assertTrue(all(r["verification"]=="verified" and r["source_tier"]=="primary" for r in records))
        self.assertTrue(all(r.get("version") is None for r in records))

    def test_no_source_or_unknown_format_is_not_evidence(self):
        for raw,url in [(HTML,"https://example.com/patch"),(HTML.replace("Auto VI","Auto V"),OFFICIAL_ARTICLE),
                        (HTML.replace("November 25, 2026]","November 26, 2026]"),OFFICIAL_ARTICLE),
                        (HTML.replace("Improved a synthetic test feature","Unrecognized item"),OFFICIAL_ARTICLE),
                        ("<article>Access unavailable</article>",OFFICIAL_ARTICLE)]:
            self.assertEqual(parse_patch_records(raw,url,NOW),[])
        self.assertEqual(parse_patch_records(HTML,OFFICIAL_ARTICLE,"2026-11-25"),[])

    def test_persistent_identity_updates_revision_without_duplicate_day(self):
        db=sqlite3.connect(":memory:")
        first=parse_patch_records(HTML,OFFICIAL_ARTICLE,NOW)
        self.assertEqual(history.import_history(db,first),2)
        second=parse_patch_records(HTML.replace("Improved a synthetic test feature","Improved another synthetic test feature"),
                                   OFFICIAL_ARTICLE,"2026-11-25T21:00:00Z")
        self.assertEqual(history.import_history(db,second),0)
        with tempfile.TemporaryDirectory() as tmp:
            output=history.export_history(db,Path(tmp)/"history.json")
        self.assertEqual(len(output["records"]),2)
        recent=output["records"][-1]
        self.assertEqual(recent["metadata"]["content_sha256"],second[-1]["metadata"]["content_sha256"])
        self.assertNotEqual(recent["metadata"]["content_sha256"],first[-1]["metadata"]["content_sha256"])
        self.assertEqual(recent["first_observed_at"],NOW)
        self.assertEqual(recent["last_observed_at"],"2026-11-25T21:00:00Z")
        db.close()

if __name__=="__main__":
    unittest.main()
