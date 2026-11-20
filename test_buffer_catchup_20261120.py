"""Offline validation of real dated Buffer schedule, without publishing."""
import json
import unittest
from datetime import datetime,timedelta,timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
from buffer_catchup_20261120 import planned_threads,make_plan,schedule_one

DATA=json.loads(Path("catchup-20261120.json").read_text(encoding="utf-8"))
NOW=datetime(2026,11,20,8,45,tzinfo=timezone.utc)

class CatchupTest(unittest.TestCase):
    def test_ten_original_threads_in_window(self):
        rows=planned_threads(DATA)
        self.assertEqual(len(rows),10)
        self.assertEqual(len({r["key"] for r in rows}),10)
        self.assertTrue(all(len(r["thread"])==2 for r in rows))
        self.assertEqual([r["time"] for r in rows][0],"10:35")
        self.assertEqual([r["time"] for r in rows][-1],"19:35")
        self.assertTrue(all(r["thread"][1].count("https://")==1 for r in rows))

    def test_fill_only_future_spaced_no_duplicates(self):
        earlier=datetime(2026,11,20,8,42,tzinfo=timezone.utc)
        other=[dict(at=earlier,status="sent",units=2)]
        plan=make_plan(DATA,{"entries":{}},NOW,other)
        self.assertEqual(len(plan),10)
        self.assertEqual(plan[0]["due"].isoformat(),"2026-11-20T09:35:00+00:00")
        self.assertTrue(all((b["due"]-a["due"]).total_seconds()>=3000 for a,b in zip(plan,plan[1:])))
        self.assertTrue(all(r["due"]>NOW for r in plan))
        duplicate={"entries":{"a":{"url":plan[0]["link"],"status":"sent","reserved_utc":NOW.isoformat()}}}
        deduped=make_plan(DATA,duplicate,NOW,other)
        self.assertEqual(len(deduped),9)
        self.assertNotIn(plan[0]["id"],[r["id"] for r in deduped])

    def test_late_run_moves_slots_not_into_past(self):
        late=datetime(2026,11,20,15,45,tzinfo=timezone.utc)
        plan=make_plan(DATA,{"entries":{}},late,[])
        self.assertGreater(len(plan),0)
        self.assertLess(len(plan),10)
        self.assertTrue(all(r["due"]>=late+timedelta(minutes=20) for r in plan))
        self.assertTrue(all(r["due"].hour<20 for r in plan))
        self.assertEqual(make_plan(DATA,{"entries":{}},
           datetime(2026,11,20,20,5,tzinfo=timezone.utc),[]),[])

    def test_mutation_is_custom_scheduled_one_thread_without_retries(self):
        row=make_plan(DATA,{"entries":{}},NOW,[])[0]
        class Client:
            channel_id="x-channel"
            def _graphql(self,query,variables,mutation=False):
                self.data=variables["input"]
                self.asserted=mutation
                return {"createPost":{"post":{"id":"buffer-123","status":"scheduled",
                                               "channelId":"x-channel"}}}
            def _delivery(self,post):
                return SimpleNamespace(status=post["status"],post_id=post["id"])
        client=Client()
        self.assertEqual(schedule_one(client,row),"buffer-123")
        self.assertEqual(client.data["mode"],"customScheduled")
        self.assertEqual(client.data["schedulingType"],"automatic")
        self.assertEqual(len(client.data["metadata"]["twitter"]["thread"]),2)
        self.assertEqual(client.data["dueAt"],"2026-11-20T09:35:00Z")
        self.assertEqual(client.data["text"],client.data["metadata"]["twitter"]["thread"][0]["text"])

if __name__=="__main__":
    unittest.main()
