"""No-network regression for first-two-weeks actual two-post delivery health."""
import json
from datetime import datetime,timedelta,timezone
from pathlib import Path
import tempfile
import unittest
from publishing_health_v1 import launch_progress, delivery_freshness, report

NOW=datetime(2026,11,20,19,35,tzinfo=timezone.utc) # 20:35 Rome

class LaunchHealthTests(unittest.TestCase):
    def test_alert_only_near_close_and_only_for_actual_sent_double_threads(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            entries={str(i):{
                'reserved_utc':(NOW-timedelta(minutes=75+i)).isoformat(),
                'completed_utc':(NOW-timedelta(minutes=70+i)).isoformat(),
                'status':'sent','thread':['main','reply']} for i in range(9)}
            entries['single']={'reserved_utc':NOW.isoformat(),'status':'sent'}
            entries['pending']={'reserved_utc':NOW.isoformat(),'status':'accepted_pending','thread':['a','b']}
            path=root/'editorial-autopilot-v137.json'
            path.write_text(json.dumps({'entries':entries}),encoding='utf-8')
            result=launch_progress(NOW,root)
            self.assertEqual(result['sent_double_threads'],9)
            self.assertEqual(result['single_posts_in_editorial_ledger'],1)
            self.assertEqual(result['unconfirmed'],1)
            self.assertEqual(result['missing_to_minimum'],1)
            self.assertTrue(result['under_min_at_close'])
            early=launch_progress(NOW-timedelta(hours=2),root)
            self.assertFalse(early['under_min_at_close'])
            entries['ten']={'reserved_utc':NOW.isoformat(),'status':'sent','thread':['main','reply']}
            path.write_text(json.dumps({'entries':entries}),encoding='utf-8')
            self.assertFalse(launch_progress(NOW,root)['under_min_at_close'])
            self.assertEqual(launch_progress(NOW,root)['missing_to_minimum'],0)

    def test_receipt_24h_gap_warns_only_with_recent_unresolved_attempt(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            now=datetime(2026,11,23,16,0,tzinfo=timezone.utc)
            last=datetime(2026,11,20,19,35,tzinfo=timezone.utc)
            receipt=root/'receipts.json'
            receipt.write_text(json.dumps({
                "schema":"verified-buffer-x-permalinks-v1",
                "posts":[{
                    "buffer_id":"6afffbef738ce4635f9850a7",
                    "article_url":"https://xfederiko11.github.io/gta-6/trofei/",
                    "x_url":"https://x.com/xFederiko11/status/2123685579590139924",
                    "sent_at":last.isoformat(),
                    "verified_by":"Buffer sent Post.externalLink on verified @xFederiko11 channel"
                }]
            }),encoding="utf-8")
            ledger=root/'editorial-autopilot-v137.json'
            unresolved={
                "1":{"status":"uncertain",
                     "reserved_utc":(now-timedelta(hours=1)).isoformat(),
                     "thread":["main","reply"]},
                "2":{"status":"accepted_pending",
                     "reserved_utc":(now-timedelta(minutes=31)).isoformat(),
                     "thread":["main","reply"]}
            }
            ledger.write_text(json.dumps({"entries":unresolved}),encoding="utf-8")
            d=delivery_freshness(now,root,receipt)
            self.assertEqual(d["status"],"available")
            self.assertEqual(d["verified_first_posts"],1)
            self.assertTrue(d["over_24h"])
            self.assertTrue(d["alert"])
            self.assertEqual(d["unresolved_recent_attempts"],2)
            self.assertIn("non ritentare",d["note"])
            self.assertTrue(report(now,root,receipt)["attention_required"])
            # A stale receipt alone does not show a publication failure.
            ledger.write_text(json.dumps({"entries":{}}),encoding="utf-8")
            self.assertFalse(delivery_freshness(now,root,receipt)["alert"])
            # A recent attempt must have been unresolved long enough to
            # avoid a false positive while Buffer may still process it.
            ledger.write_text(json.dumps({"entries":{"1":{
                "status":"reserved",
                "reserved_utc":(now-timedelta(minutes=5)).isoformat()
            }}}),encoding="utf-8")
            self.assertFalse(delivery_freshness(now,root,receipt)["alert"])
            # Finished or previously failed item is not a pending delivery.
            ledger.write_text(json.dumps({"entries":{"1":{
                "status":"sent",
                "reserved_utc":(now-timedelta(hours=1)).isoformat()
            }}}),encoding="utf-8")
            self.assertFalse(delivery_freshness(now,root,receipt)["alert"])
            # Outside launch dates the same historical issue is not urgent.
            ledger.write_text(json.dumps({"entries":unresolved}),encoding="utf-8")
            self.assertFalse(delivery_freshness(datetime(2026,12,3,16,tzinfo=timezone.utc),root,receipt)["alert"])

    def test_bad_or_missing_receipt_never_masquerades_as_zero_posts(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            now=datetime(2026,11,23,16,0,tzinfo=timezone.utc)
            r=root/"receipts.json"
            missing=delivery_freshness(now,root,r)
            self.assertEqual(missing["status"],"unavailable")
            self.assertFalse(missing["alert"])
            r.write_text('{"schema":"not-a-trusted-receipt"}',encoding="utf-8")
            wrong=delivery_freshness(now,root,r)
            self.assertEqual(wrong["status"],"unavailable")
            self.assertFalse(wrong["alert"])
            with self.assertRaisesRegex(ValueError,"Aware clock"):
                delivery_freshness(datetime(2026,11,23,16),root,r)

    def test_outside_campaign_has_no_false_alarm(self):
        date=datetime(2026,12,3,19,0,tzinfo=timezone.utc)
        self.assertEqual(launch_progress(date),{'active':False})

if __name__=='__main__':unittest.main()
