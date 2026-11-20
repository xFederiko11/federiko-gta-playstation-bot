"""Offline regression for receipt-only, non-destructive ledger reconciliation."""
from datetime import datetime,timezone
import copy,unittest
from buffer_ledger_reconcile_v1 import reconcile,ORIGIN
URL="https://xfederiko11.github.io/gta-6/salvare-auto/"
X="https://x.com/xFederiko11/status/2123741902625218841"
ID="6b0009d8d5f8acdd0d856bd9"
def ledger():
    return {"schema":"editorial-autopilot-v137","entries":{
      "a":{"status":"scheduled","buffer_id":ID,"url":URL,
           "thread":["How to save a car","Guide with links"],
           "reserved_utc":"2026-11-20T11:35:00Z","due_at":"2026-11-20T11:35:00Z"},
      "b":{"status":"scheduled","buffer_id":"otherpost1234567890","url":URL},
      "c":{"status":"rejected","buffer_id":ID,"url":URL}}}
def feed(**overrides):
    item={"buffer_id":ID,"article_url":URL,"x_url":X,
          "sent_at":"2026-11-20T11:35:01Z","verified_by":ORIGIN}
    return {"schema":"verified-buffer-x-permalinks-v1","posts":[{**item,**overrides}]}
class ReceiptReconcileTests(unittest.TestCase):
    def test_reconcile_exact_match_only(self):
        old=ledger()
        updated,count=reconcile(old,feed())
        self.assertEqual(count,1)
        a=updated["entries"]["a"]
        self.assertEqual(a["status"],"sent")
        self.assertEqual(a["completed_utc"],"2026-11-20T11:35:01Z")
        self.assertEqual(a["x_permalink"],X)
        self.assertTrue(a["buffer_receipt_verified"])
        self.assertFalse(a["thread_reply_verified"])
        self.assertEqual(a["thread"],old["entries"]["a"]["thread"])
        self.assertEqual(old["entries"]["a"]["status"],"scheduled")
        self.assertEqual(updated["entries"]["b"]["status"],"scheduled")
        self.assertEqual(updated["entries"]["c"]["status"],"rejected")
        self.assertEqual(reconcile(updated,feed())[1],0)
    def test_spoofing_or_mismatch_cannot_change_ledger(self):
        bad=(
          {"buffer_id":"otherpost1234567890"},
          {"article_url":"https://xfederiko11.github.io/gta-6/soldi-facili/"},
          {"x_url":"https://x.com/Other/status/2123741902625218841"},
          {"x_url":"https://x.com.evil.test/xFederiko11/status/2123741902625218841"},
          {"verified_by":"unverified"},
          {"sent_at":"2037-01-01T00:00:00Z"},
        )
        for override in bad:
            self.assertEqual(reconcile(ledger(),feed(**override))[1],0,str(override))
    def test_conflicting_duplicate_receipts_fail_closed(self):
        a=feed()
        a["posts"].append({**a["posts"][0],"x_url":"https://x.com/xFederiko11/status/2123741902625218842"})
        with self.assertRaises(ValueError):reconcile(ledger(),a)
    def test_no_action_when_invalid_schema(self):
        with self.assertRaises(ValueError):
            reconcile(ledger(),{"schema":"reddit-unverified","posts":[]})
if __name__=="__main__":unittest.main()
