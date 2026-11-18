"""No-network tests: Italian action-first X threads with official images and source reply."""
import unittest
from datetime import datetime,timedelta,timezone
from unittest.mock import Mock, patch
from buffer_publisher import BufferClient
from editorial_seo_v135 import x_weight
from quick_tips_v146 import TIPS, validate, reply, candidate

NOW=datetime(2026,11,18,18,0,tzinfo=timezone.utc)

def answer(payload):
    response=Mock(status_code=200, headers={})
    response.json.return_value={"data":payload}
    return response

class QuickTipsV146Tests(unittest.TestCase):
    def test_all_five_curated_tips_have_valid_separate_source_reply(self):
        self.assertTrue(validate())
        self.assertEqual(len(TIPS),5)
        self.assertEqual(len({t['id'] for t in TIPS}),5)
        self.assertEqual(len({t['media_url'] for t in TIPS}),5)
        for tip in TIPS:
            self.assertLessEqual(x_weight(tip['main']),280)
            self.assertLessEqual(x_weight(reply(tip)),280)
            self.assertNotIn('https://',tip['main'])
            self.assertIn(tip['source_url'],reply(tip))
            self.assertTrue(tip['main'].startswith(('🚗','🦩','🎯','⚠️')))
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
        first=candidate(state,NOW)
        state['entries'][first['key']]={"source":"PowerPyx Tips","status":"sent",
                                       "reserved_utc":NOW.isoformat()}
        later=NOW+timedelta(hours=4)
        second=candidate(state,later)
        state['entries'][second['key']]={"source":"PowerPyx Tips","status":"sent",
                                       "reserved_utc":later.isoformat()}
        self.assertIsNone(candidate(state,later+timedelta(hours=4)))

    def test_global_journal_not_modified_by_candidate(self):
        state={"entries":{}}
        candidate(state,NOW)
        self.assertEqual(state,{"entries":{}})

if __name__=="__main__":
    unittest.main()
