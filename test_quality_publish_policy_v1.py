"""2026-11-23 launch retirement and owner-approved X quality/frequency policy."""
from datetime import datetime,timedelta,timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import json
import unittest

from quality_publish_policy_v1 import (
    verified_urgent,ordinary_hours,report,
    ORDINARY_LIMIT_MESSAGES_24H,URGENT_LIMIT_24H)
from launch_cadence_v1 import active as old_launch_active
from editorial_director_v142 import allowed,read_reservations,note_monitor_attempt

UTC=timezone.utc

def stamp(hour,minute=0,day=23):
    return datetime(2026,11,day,hour,minute,tzinfo=UTC)

class QualityFirstPolicyTests(unittest.TestCase):
    def test_times_and_reporting(self):
        self.assertEqual(ORDINARY_LIMIT_MESSAGES_24H,6)
        self.assertEqual(URGENT_LIMIT_24H,2)
        self.assertFalse(old_launch_active(stamp(8)))
        self.assertFalse(ordinary_hours(stamp(5,59)))
        self.assertTrue(ordinary_hours(stamp(6)))
        self.assertTrue(ordinary_hours(stamp(21,59)))
        self.assertFalse(ordinary_hours(stamp(22)))
        p=report(stamp(14))
        self.assertEqual(p["ordinary_window"],"07:00-23:00")
        self.assertEqual(p["ordinary_goal_messages"],[5,6])
        self.assertIs(p["filler_posts"],False)
        self.assertIs(p["automatic_external_replies"],False)

    def test_urgent_source_and_topic_both_required(self):
        base={"trust":"official",
              "source_url":"https://www.rockstargames.com/newswire/article/abc/",
              "title":"GTA VI hotfix for reported crash"}
        self.assertTrue(verified_urgent(base))
        self.assertFalse(verified_urgent({**base,"trust":"community"}))
        self.assertFalse(verified_urgent({**base,"source_url":"https://rockstargames.com.fake.example/patch"}))
        self.assertFalse(verified_urgent({**base,"title":"GTA VI wallpaper gallery available"}))
        self.assertFalse(verified_urgent({**base,"source_url":"http://www.rockstargames.com/newswire/patch"}))

    def test_ordinary_messages_not_buffer_records_and_spacing(self):
        now=stamp(13)
        with TemporaryDirectory() as temp,patch.dict("os.environ",{"EDITORIAL_DIRECTOR_V142_ENABLED":"true"}):
            directory=Path(temp)
            self.assertEqual(allowed(stamp(5,59),root=directory),(False,"outside_ordinary_07_23_rome"))
            self.assertEqual(allowed(now,root=directory),(True,"quality_ordinary_ready"))
            entries={}
            for k,hr in enumerate((7,9,11)):
                entries[str(k)]={"reserved_utc":stamp(hr).isoformat(),
                                 "thread":["Main post","Useful cited reply"],"status":"sent"}
            (directory/"editorial-autopilot-v137.json").write_text(json.dumps({"entries":entries}))
            self.assertEqual(sum(x["units"] for x in read_reservations(directory)),6)
            self.assertEqual(allowed(now,root=directory),(False,"ordinary_six_message_cap"))
            entries.pop("2")
            (directory/"editorial-autopilot-v137.json").write_text(json.dumps({"entries":entries}))
            self.assertEqual(allowed(stamp(10,20),root=directory),(False,"ordinary_minimum_gap"))
            self.assertEqual(allowed(now,root=directory,units=3),(False,"ordinary_six_message_cap"))
            self.assertEqual(allowed(now,root=directory,units=2),(True,"quality_ordinary_ready"))

    def test_official_breaking_extra_but_limited_and_not_spam_bypass(self):
        event={"trust":"official",
               "source_url":"https://support.rockstargames.com/articles/new-hotfix",
               "title":"GTA VI patch hotfix"}
        with TemporaryDirectory() as temp,patch.dict("os.environ",{"EDITORIAL_DIRECTOR_V142_ENABLED":"true"}):
            root=Path(temp)
            self.assertEqual(allowed(stamp(5),root=root,kind="official_breaking"),(True,"verified_official_breaking"))
            note_monitor_attempt(event,stamp(5),root=root,kind="official_breaking")
            self.assertEqual(allowed(stamp(5,10),root=root,kind="official_breaking"),
                             (False,"verified_breaking_minimum_gap"))
            self.assertEqual(allowed(stamp(5,40),root=root,kind="official_breaking"),
                             (True,"verified_official_breaking"))
            with patch.dict("os.environ",{"GITHUB_RUN_ID":"different"}):
                note_monitor_attempt(event,stamp(5,40),root=root,kind="official_breaking")
            self.assertEqual(allowed(stamp(6,40),root=root,kind="official_breaking"),
                             (False,"verified_breaking_safety_cap"))
            self.assertEqual(allowed(stamp(13),root=root),(True,"quality_ordinary_ready"))
            with self.assertRaisesRegex(ValueError,"Unverified event"):
                note_monitor_attempt({**event,"trust":"community"},stamp(7),root=root,
                                     kind="official_breaking")
            with self.assertRaisesRegex(ValueError,"Invalid X message"):
                note_monitor_attempt(event,stamp(7),root=root,units=0)

    def test_ordinary_gap_blocks_quiet_hour_updates(self):
        with TemporaryDirectory() as tmp,patch.dict("os.environ",{"EDITORIAL_DIRECTOR_V142_ENABLED":"true"}):
            root=Path(tmp)
            (root/"editorial-autopilot-v137.json").write_text(json.dumps({"entries":{
                "one":{"reserved_utc":stamp(14).isoformat(),"status":"uncertain"}
            }}))
            self.assertEqual(allowed(stamp(15),root=root),(False,"ordinary_minimum_gap"))
            self.assertEqual(allowed(stamp(16),root=root),(True,"quality_ordinary_ready"))
            self.assertEqual(allowed(stamp(22),root=root),(False,"outside_ordinary_07_23_rome"))

if __name__=="__main__":
    unittest.main()
