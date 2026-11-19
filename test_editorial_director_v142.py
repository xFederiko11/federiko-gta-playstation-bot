"""Offline unit tests for shared ledger coordination and editorial quality."""
from datetime import datetime,timedelta,timezone
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from editorial_director_v142 import allowed,priority,read_reservations,MIN_GAP,MAX_AUTOMATED_DELIVERIES_24H,current_limits,BOOST_UNTIL,RECOVERY_START,RECOVERY_END,RECOVERY_MAX_AUTOMATED_DELIVERIES

NOW=datetime(2026,11,18,20,0,tzinfo=timezone.utc)
class EditorDirectorTests(unittest.TestCase):
    def test_reject_offtopic_parodies_and_gossip(self):
        self.assertLess(priority('Volvy parodia di GTA 6','Everyeye'),0)
        self.assertLess(priority('GTA 6 parody trailer','VGC'),0)
        self.assertLess(priority('GTA 6: fake release rumor','GameSpot'),0)
        self.assertGreater(priority('GTA VI Trophy Roadmap','PowerPyx'),
                           priority('GTA VI new trailer','GameSpot'))

    def test_cross_workflow_spacing(self):
        with tempfile.TemporaryDirectory() as p,patch.dict('os.environ',{'EDITORIAL_DIRECTOR_V142_ENABLED':'true'}):
            root=Path(p)
            (root/'special-campaign-v139.json').write_text(json.dumps({
                'entries':{'x':{'reserved_utc':(NOW-timedelta(minutes=8)).isoformat(),
                                'status':'sent'}}}),encoding='utf-8')
            self.assertEqual(allowed(NOW,root=root),(False,'global_spacing'))
            self.assertEqual(allowed(NOW+timedelta(minutes=30),root=root),(False,'global_spacing'))
            self.assertEqual(allowed(NOW+timedelta(hours=4),root=root),(True,'ready'))
            (root/'editorial-autopilot-v137.json').write_text(json.dumps({
                'entries':{'post':{'reserved_utc':(NOW+timedelta(hours=3,minutes=58)).isoformat(),
                                   'status':'reserved'}}}),encoding='utf-8')
            self.assertEqual(allowed(NOW+timedelta(hours=4),root=root),(False,'global_spacing'))
            self.assertEqual(len(read_reservations(root)),2)

    def test_balanced_eight_slot_budget_and_ninety_minute_spacing(self):
        self.assertEqual(MAX_AUTOMATED_DELIVERIES_24H,8)
        self.assertEqual(MIN_GAP,timedelta(minutes=90))
        with tempfile.TemporaryDirectory() as directory,patch.dict('os.environ',{'EDITORIAL_DIRECTOR_V142_ENABLED':'true'}):
            root=Path(directory)
            for filename,field,offsets,status in [
                ('editorial-autopilot-v137.json','entries',[23,22],'sent'),
                ('special-campaign-v139.json','entries',[17,16],'accepted_pending'),
                ('launch-watch-v134.json','posts',[11,10],'reserved'),
                ('monitor-publication-v142.json','entries',[5,4],'attempted'),
            ]:
                (root/filename).write_text(json.dumps({field:{
                    filename+'-'+str(offset):{
                        'reserved_utc':(NOW-timedelta(hours=offset)).isoformat(),
                        'status':status} for offset in offsets}}),encoding='utf-8')
            self.assertEqual(allowed(NOW,root=root),(False,'global_rolling_24h_budget'))
            # Age out two older reservations; the remaining six stay below cap.
            self.assertEqual(allowed(NOW+timedelta(hours=4),root=root),(True,'ready'))

    def test_automatic_taper_after_launch_without_manual_variables(self):
        self.assertEqual(current_limits(BOOST_UNTIL-timedelta(minutes=1)),(8,timedelta(minutes=90)))
        self.assertEqual(current_limits(BOOST_UNTIL),(6,timedelta(minutes=120)))
        self.assertEqual(current_limits(BOOST_UNTIL+timedelta(days=21)),(6,timedelta(minutes=120)))
        with tempfile.TemporaryDirectory() as p,patch.dict('os.environ',{'EDITORIAL_DIRECTOR_V142_ENABLED':'true'}):
            root=Path(p)
            clock=BOOST_UNTIL+timedelta(hours=6)
            stamps=[(clock-timedelta(hours=3+i*3)).isoformat() for i in range(6)]
            (root/'editorial-autopilot-v137.json').write_text(json.dumps({
                'entries':{str(i):{'reserved_utc':s,'status':'sent'} for i,s in enumerate(stamps)}
            }),encoding='utf-8')
            self.assertEqual(allowed(clock,root=root),(False,'global_rolling_24h_budget'))
            # Even when total posts are below six, steady mode requires 120 min.
            (root/'editorial-autopilot-v137.json').write_text(json.dumps({
                'entries':{'x':{'reserved_utc':(clock-timedelta(minutes=95)).isoformat(),'status':'sent'}}
            }),encoding='utf-8')
            self.assertEqual(allowed(clock,root=root),(False,'global_spacing'))

    def test_one_time_launch_recovery_from_preexisting_burst(self):
        self.assertEqual(RECOVERY_MAX_AUTOMATED_DELIVERIES,5)
        self.assertEqual(RECOVERY_END-RECOVERY_START,timedelta(hours=24))
        clock=RECOVERY_START+timedelta(hours=2)
        with tempfile.TemporaryDirectory() as p,patch.dict('os.environ',{'EDITORIAL_DIRECTOR_V142_ENABLED':'true'}):
            root=Path(p)
            old={str(i):{'reserved_utc':(RECOVERY_START-timedelta(hours=8,minutes=i)).isoformat(),
                        'status':'sent'} for i in range(28)}
            (root/'editorial-autopilot-v137.json').write_text(json.dumps({'entries':old}),encoding='utf-8')
            self.assertEqual(allowed(clock,root=root),(True,'ready'))
            recent={'n'+str(i):{'reserved_utc':(clock-timedelta(hours=1,minutes=31+i)).isoformat(),
                                'status':'reserved'} for i in range(5)}
            (root/'launch-watch-v134.json').write_text(json.dumps({'posts':recent}),encoding='utf-8')
            self.assertEqual(allowed(clock,root=root),(False,'recovery_tranche_budget'))
            # Outside recovery, old entries count again under the rolling policy.
            self.assertEqual(allowed(RECOVERY_END+timedelta(minutes=1),root=root),(True,'ready'))

    def test_recovery_still_keeps_minimum_spacing_from_old_and_new_reservations(self):
        clock=RECOVERY_START+timedelta(minutes=40)
        with tempfile.TemporaryDirectory() as p,patch.dict('os.environ',{'EDITORIAL_DIRECTOR_V142_ENABLED':'true'}):
            root=Path(p)
            (root/'editorial-autopilot-v137.json').write_text(json.dumps({'entries':{
                'old':{'reserved_utc':(RECOVERY_START-timedelta(minutes=20)).isoformat(),
                       'status':'sent'}
            }}),encoding='utf-8')
            self.assertEqual(allowed(clock,root=root),(False,'global_spacing'))
            self.assertEqual(allowed(clock+timedelta(minutes=40),root=root),(True,'ready'))

    def test_rejected_events_not_counted_and_future_entries_hold(self):
        with tempfile.TemporaryDirectory() as directory,patch.dict('os.environ',{'EDITORIAL_DIRECTOR_V142_ENABLED':'true'}):
            root=Path(directory)
            (root/'special-campaign-v139.json').write_text(json.dumps({
                'entries':{
                    'discarded':{'reserved_utc':(NOW-timedelta(minutes=1)).isoformat(),'status':'rejected'},
                    'future':{'reserved_utc':(NOW+timedelta(hours=1)).isoformat(),'status':'reserved'}
                }}),encoding='utf-8')
            self.assertEqual(allowed(NOW,root=root),(False,'global_spacing'))

    def test_director_can_be_safely_disabled(self):
        with tempfile.TemporaryDirectory() as p,patch.dict('os.environ',{'EDITORIAL_DIRECTOR_V142_ENABLED':'false'}):
            self.assertEqual(allowed(NOW,root=Path(p)),(True,'disabled'))

    def test_corrupted_ledger_fails_closed(self):
        with tempfile.TemporaryDirectory() as p,patch.dict('os.environ',{'EDITORIAL_DIRECTOR_V142_ENABLED':'true'}):
            (Path(p)/'special-campaign-v139.json').write_text('{not valid')
            with self.assertRaises(RuntimeError):
                allowed(NOW,root=Path(p))
if __name__=='__main__':
    unittest.main()
