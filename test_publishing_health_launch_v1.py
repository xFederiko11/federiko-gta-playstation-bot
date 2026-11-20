"""No-network regression for first-two-weeks actual two-post delivery health."""
import json
from datetime import datetime,timedelta,timezone
from pathlib import Path
import tempfile
import unittest
from publishing_health_v1 import launch_progress

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

    def test_outside_campaign_has_no_false_alarm(self):
        date=datetime(2026,12,3,19,0,tzinfo=timezone.utc)
        self.assertEqual(launch_progress(date),{'active':False})

if __name__=='__main__':unittest.main()
