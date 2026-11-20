"""Launch cadence regression: local timezone, exact dates, messages and dedupe."""
import unittest
from datetime import datetime,timedelta,timezone
from launch_cadence_v1 import (active,in_hours,launch_eligible,local,count_local_day,
    message_units,campaign_status,START,LAST,TARGET_MIN,TARGET,TARGET_MAX,THREAD_LENGTH,MIN_PACING)

def utc(day,hour,minute=0):
    return datetime(2026,11,day,hour,minute,tzinfo=timezone.utc)

class LaunchCadenceTests(unittest.TestCase):
    def test_first_14_days_timezone(self):
        self.assertEqual(START.isoformat(),'2026-11-19')
        self.assertEqual(LAST.isoformat(),'2026-12-02')
        self.assertEqual((LAST-START).days+1,14)
        self.assertTrue(launch_eligible(utc(19,7,0)))       # 08:00 Rome
        self.assertFalse(launch_eligible(utc(19,6,59)))
        self.assertTrue(launch_eligible(utc(19,19,59)))     # 20:59 Rome
        self.assertFalse(launch_eligible(utc(19,20,0)))   # 21:00 Rome
        self.assertFalse(launch_eligible(utc(18,12,0)))
        self.assertFalse(launch_eligible(datetime(2026,12,2,21,0,tzinfo=timezone.utc)))
        self.assertFalse(launch_eligible(datetime(2026,12,3,8,0,tzinfo=timezone.utc)))
        with self.assertRaises(ValueError):active(datetime(2026,11,20,9,0))

    def test_daily_target_and_message_limit(self):
        self.assertEqual((TARGET_MIN,TARGET,TARGET_MAX),(10,12,16))
        self.assertEqual(THREAD_LENGTH,2)
        self.assertEqual(MIN_PACING,timedelta(minutes=45))
        report=campaign_status(utc(20,9),sent_threads=4)
        self.assertEqual(report['missing_to_minimum'],6)
        self.assertEqual(report['window'],'08:00-21:00')
        self.assertEqual(report['mode'],'quality_gated_no_filler')
        self.assertEqual(message_units({'thread':['a','b']}),2)
        self.assertEqual(message_units({'text':'a'}),1)

    def test_counts_only_same_local_day_and_preserves_uncertain(self):
        now=utc(20,10,0)
        state={
            'previous':{'reserved_utc':utc(19,18).isoformat(),'status':'sent'},
            'today':{'reserved_utc':utc(19,23,30).isoformat(),'status':'sent'},
            'uncertain':{'reserved_utc':utc(20,9).isoformat(),'status':'uncertain'},
            'rejected':{'reserved_utc':utc(20,9).isoformat(),'status':'rejected'},
        }
        self.assertEqual(count_local_day(state,now),2)

if __name__=='__main__':
    unittest.main()
