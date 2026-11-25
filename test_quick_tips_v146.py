"""No-network tests: Italian action-first X threads with official images and source reply."""
import unittest
from datetime import datetime,timedelta,timezone
from unittest.mock import Mock, patch
from buffer_publisher import BufferClient
from editorial_seo_v135 import x_weight
from quick_tips_v146 import TIPS, validate, reply, candidate

NOW=datetime(2026,11,18,18,0,tzinfo=timezone.utc)

# The test runs every 15 minutes, including after the 21:00 Rome cutoff.
# Freeze time for the *test*, not the bot's real, protective launch gate.
class LaunchHoursClock(datetime):
    @classmethod
    def now(cls, tz=None):
        fixed = datetime(2026, 11, 20, 14, 0, tzinfo=timezone.utc)
        return fixed if tz is None else fixed.astimezone(tz)

class AfterHoursClock(datetime):
    @classmethod
    def now(cls, tz=None):
        fixed = datetime(2026, 11, 20, 20, 15, tzinfo=timezone.utc)
        return fixed if tz is None else fixed.astimezone(tz)


def answer(payload):
    response=Mock(status_code=200, headers={})
    response.json.return_value={"data":payload}
    return response

class QuickTipsV146Tests(unittest.TestCase):
    def test_all_six_curated_tips_have_valid_separate_source_reply(self):
        self.assertTrue(validate())
        self.assertEqual(len(TIPS),6)
        self.assertEqual(len({t['id'] for t in TIPS}),6)
        self.assertEqual(len({t['media_url'] for t in TIPS}),6)
        for tip in TIPS:
            self.assertLessEqual(x_weight(tip['main']),235)
            self.assertLessEqual(x_weight(reply(tip)),280)
            self.assertNotIn('https://',tip['main'])
            self.assertIn(tip['source_url'],reply(tip))
            self.assertTrue(tip['main'].startswith(('🚗','🦩','🎯','⚠️','🚕')))
            self.assertTrue(tip['main'].endswith(('#GTAVI #GTA6','#GTAVI #Platino')))
            self.assertIn('\n\n',tip['main'])
            self.assertIn('📸 Foto illustrativa: Rockstar Games.',reply(tip))

    def test_one_buffer_mutation_with_image_only_on_parent_and_source_in_reply(self):
        session=Mock()
        channel={"id":"channel-1","name":"myfan","service":"twitter",
                 "externalLink":"https://x.com/myfan",
                 "isDisconnected":False,"isLocked":False,"isQueuePaused":False}
        message={"createPost":{"post":{"id":"test-id-1","status":"sent","channelId":"channel-1"}}}
        session.post.side_effect=[answer({"channel":channel}),answer(message)]
        client=BufferClient("fake-key","channel-1","myfan",session=session)
        tip=TIPS[0]
        result=client.publish_thread([tip['main'],reply(tip)],media_url=tip['media_url'])
        self.assertEqual(result,"test-id-1")
        self.assertEqual(session.post.call_count,2)  # 1 destination check, 1 create
        graph=session.post.call_args.kwargs['json']
        input_args=graph['variables']['input']
        self.assertEqual(input_args['mode'],'shareNow')
        self.assertEqual(input_args['text'],tip['main'])
        self.assertEqual(input_args['assets'],[])
        posts=input_args['metadata']['twitter']['thread']
        self.assertEqual(len(posts),2)
        self.assertEqual(posts[0]['text'],tip['main'])
        self.assertEqual(posts[1]['text'],reply(tip))
        self.assertEqual(posts[0]['assets'],[{"image":{"url":tip['media_url']}}])
        self.assertEqual(posts[1]['assets'],[])
        self.assertIn(tip['source_url'],posts[1]['text'])

    def test_no_retry_or_duplicate_in_same_ledger(self):
        state={"entries":{}}
        first=candidate(state,NOW)
        self.assertIsNotNone(first)
        self.assertEqual(len(first["thread"]),2)
        state['entries'][first['key']]={"source":"PowerPyx Tips",
            "status":"accepted_pending","reserved_utc":NOW.isoformat()}
        self.assertIsNone(candidate(state,NOW+timedelta(minutes=8)))
        second=candidate(state,NOW+timedelta(minutes=111))
        self.assertIsNotNone(second)
        self.assertNotEqual(second["key"],first["key"])

    def test_tip_daily_limit(self):
        state={"entries":{}}
        today=datetime(2026,11,19,8,0,tzinfo=timezone.utc)
        first=candidate(state,today)
        state['entries'][first['key']]={"source":"PowerPyx Tips","status":"sent",
                                       "reserved_utc":today.isoformat()}
        later=today+timedelta(hours=4)
        second=candidate(state,later)
        state['entries'][second['key']]={"source":"PowerPyx Tips","status":"sent",
                                       "reserved_utc":later.isoformat()}
        self.assertIsNone(candidate(state,later+timedelta(hours=4)))

    def test_editorial_reserve_and_deliver_one_thread_without_double_publish(self):
        import os
        import tempfile
        from pathlib import Path
        import editorial_autopilot_v137 as bot
        with tempfile.TemporaryDirectory() as td, \
             patch.object(bot,"STATE",Path(td)/"state.json"), \
             patch.object(bot,"datetime",LaunchHoursClock), \
             patch.object(bot,"read_feeds",return_value=([],[])), \
             patch.object(bot,"load_sources",return_value=[]), \
             patch.object(bot,"powerpyx_spotlight",return_value=None), \
             patch.object(bot,"director_allowed",return_value=(True,"ready")), \
             patch("growth_conversion_v1.candidate",return_value=None), \
             patch("portal_links_v148.guide_if_live",return_value=None), \
             patch("social_media_gate_v2.probe_image",return_value=True), \
             patch.dict(os.environ,{"GITHUB_RUN_ID":"test-run-125"}):
            bot.reserve()
            entries=bot.load_state()["entries"]
            self.assertEqual(len(entries),1)
            event=next(iter(entries.values()))
            self.assertEqual(event["source"],"PowerPyx Tips")
            self.assertEqual(len(event["thread"]),2)
            fake=Mock()
            fake.publish_thread.return_value="buffer-test-tip"
            with patch("buffer_publisher.BufferClient",return_value=fake):
                bot.deliver()
                bot.deliver()
            fake.publish_thread.assert_called_once_with(event["thread"],media_url=event["media_url"])
            fake.publish.assert_not_called()
            self.assertEqual(next(iter(bot.load_state()["entries"].values()))["status"],"sent")

    def test_missing_official_image_fails_closed_without_reservation(self):
        import os
        import tempfile
        from pathlib import Path
        import editorial_autopilot_v137 as bot
        with tempfile.TemporaryDirectory() as td, \
             patch.object(bot,"STATE",Path(td)/"state.json"), \
             patch.object(bot,"datetime",LaunchHoursClock), \
             patch.object(bot,"read_feeds",return_value=([],[])), \
             patch.object(bot,"load_sources",return_value=[]), \
             patch.object(bot,"powerpyx_spotlight",return_value=None), \
             patch.object(bot,"director_allowed",return_value=(True,"ready")), \
             patch("growth_conversion_v1.candidate",return_value=None), \
             patch("site_evergreen_posts_v1.candidate",return_value=None), \
             patch("portal_links_v148.guide_if_live",return_value=None), \
             patch("social_media_gate_v2.probe_image",return_value=False), \
             patch("trophy_posts_v142.candidate",return_value=None), \
             patch.dict(os.environ,{"GITHUB_RUN_ID":"test-run-126"}):
            bot.reserve()
            self.assertFalse(bot.STATE.exists())

    def test_production_safety_gate_still_holds_after_2100_rome(self):
        import os
        import tempfile
        from pathlib import Path
        import editorial_autopilot_v137 as bot
        with tempfile.TemporaryDirectory() as td, \
             patch.object(bot, "STATE", Path(td)/"state.json"), \
             patch.object(bot, "datetime", AfterHoursClock), \
             patch.object(bot, "read_feeds", return_value=([],[])), \
             patch.object(bot, "load_sources", return_value=[]), \
             patch.object(bot, "director_allowed", return_value=(True,"ready")) as director, \
             patch.dict(os.environ, {"GITHUB_RUN_ID":"test-run-afterhours"}):
            bot.reserve()
            self.assertFalse(bot.STATE.exists())
            director.assert_not_called()

    def test_quick_tip_uses_its_actual_published_guide_cover_for_probe(self):
        import editorial_autopilot_v137 as bot
        from social_media_gate_v2 import cover_for
        page="https://xfederiko11.github.io/gta-6/guide-e-tutorial/scansionare-veicoli/"
        hotlink=TIPS[0]["media_url"]
        self.assertNotEqual(hotlink,cover_for(page))
        with patch("social_media_gate_v2.probe_image",return_value=True) as checked:
            self.assertTrue(bot.quick_tip_media_available({"url":page,"media_url":hotlink}))
            checked.assert_called_once_with(cover_for(page))
        with patch("social_media_gate_v2.probe_image",return_value=False) as checked:
            self.assertFalse(bot.quick_tip_media_available({"url":page,"media_url":hotlink}))
            checked.assert_called_once_with(cover_for(page))

    def test_external_quick_tip_still_requires_actual_official_image(self):
        import editorial_autopilot_v137 as bot
        tip={"url":TIPS[0]["source_url"],"media_url":TIPS[0]["media_url"]}
        with patch("social_media_gate_v2.probe_image",return_value=True) as checked:
            self.assertTrue(bot.quick_tip_media_available(tip))
            checked.assert_called_once_with(tip["media_url"])
        with patch("social_media_gate_v2.probe_image",return_value=False):
            self.assertFalse(bot.quick_tip_media_available(tip))

    def test_reauthorization_gates_resume_without_repeating_old_rejected_tip(self):
        from unittest.mock import patch
        import os
        from hashlib import sha256
        blocked={"source":"PowerPyx Tips", "status":"rejected",
                 "tip_id":"waink-vehicles-ps5",
                 "reserved_utc":"2026-11-18T13:00:00+00:00"}
        old_id=sha256(("tips-v146:"+"waink-vehicles-ps5").encode()).hexdigest()[:24]
        state={"entries":{old_id:blocked}}
        date=datetime(2026,11,19,10,0,tzinfo=timezone.utc)
        with patch.dict(os.environ,{"TIPS_REAUTH_CONFIRMED_V149":"false"}):
            self.assertIsNone(candidate(state,date))
        with patch.dict(os.environ,{"TIPS_REAUTH_CONFIRMED_V149":"true"}):
            nxt=candidate(state,date)
            self.assertIsNotNone(nxt)
            self.assertNotEqual(nxt["tip_id"],"waink-vehicles-ps5")
            self.assertEqual(nxt["tip_id"],"study animals")
        state["entries"][nxt["key"]]={"source":"PowerPyx Tips",
                                      "status":"rejected",
                                      "tip_id":nxt["tip_id"],
                                      "reserved_utc":date.isoformat()}
        with patch.dict(os.environ,{"TIPS_REAUTH_CONFIRMED_V149":"true"}):
            self.assertIsNone(candidate(state,date+timedelta(hours=4)))
        self.assertEqual(state["entries"][old_id],blocked)

    def test_global_journal_not_modified_by_candidate(self):
        state={"entries":{}}
        candidate(state,NOW)
        self.assertEqual(state,{"entries":{}})

if __name__=="__main__":
    unittest.main()
