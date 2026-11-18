"""Offline unit tests for shared ledger coordination and editorial quality."""
from datetime import datetime,timedelta,timezone
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from editorial_director_v142 import allowed,priority,read_reservations

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
            self.assertEqual(allowed(NOW+timedelta(minutes=30),root=root),(True,'ready'))
            (root/'editorial-autopilot-v137.json').write_text(json.dumps({
                'entries':{'post':{'reserved_utc':(NOW+timedelta(minutes=28)).isoformat(),
                                   'status':'reserved'}}}),encoding='utf-8')
            self.assertEqual(allowed(NOW+timedelta(minutes=30),root=root),(False,'global_spacing'))
            self.assertEqual(len(read_reservations(root)),2)

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
