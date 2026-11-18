"""No-network checks for GTA VI launch campaign and multi-photo Buffer payload."""
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock
from buffer_publisher import BufferClient, BufferMediaError
from gta6_special_campaign_v139 import POSTS, check_config, select, START, EXPIRY, probe_image

def reply(data):
    result = Mock(status_code=200, headers={})
    result.json.return_value = {"data": data}
    return result

class LaunchCampaignTests(unittest.TestCase):
    def test_content_sourced_and_gallery_theme_unique(self):
        check_config()
        self.assertEqual(len(POSTS), 4)
        self.assertEqual([p['kind'] for p in POSTS], ['article','gallery','gallery','gallery'])
        self.assertEqual(len({u for p in POSTS for u in p.get("images",[])}), 12)
        for post in POSTS:
            self.assertIn("#GTAVI", post["text"])
            if post["kind"] == "gallery":
                self.assertEqual(len(post["images"]),4)
                self.assertTrue(all("www.rockstargames.com/VI/_next/static/media/" in u for u in post["images"]))

    def test_no_early_delivery_duplicate_or_resend(self):
        ledger={"entries":{}}
        self.assertEqual(select(ledger,START-timedelta(seconds=1))[1],"outside_window")
        self.assertEqual(select(ledger,EXPIRY)[1],"outside_window")
        first, status = select(ledger,START+timedelta(hours=3))
        self.assertEqual((first["id"],status),("gta-plus-gtavi-20261118","eligible"))
        ledger["entries"][first["id"]]={"reserved_utc":(START+timedelta(hours=3)).isoformat(),"status":"uncertain"}
        self.assertEqual(select(ledger,START+timedelta(hours=3,minutes=10))[1],"minimum_spacing")
        next_post,_=select(ledger,datetime(2026,11,18,16,0,tzinfo=timezone.utc))
        self.assertEqual(next_post["id"],"rockstar-vice-city-4")

    def test_buffer_two_to_four_distinct_images_one_mutation(self):
        session=Mock()
        channel={"id":"channel-1","name":"myfan","service":"twitter",
                 "externalLink":"https://x.com/myfan", "isDisconnected":False,"isLocked":False}
        result={"createPost":{"post":{"id":"buffer-id-1","status":"sent","channelId":"channel-1"}}}
        session.post.side_effect=[reply({"channel":channel}),reply(result)]
        client=BufferClient("dummy","channel-1","myfan",session=session)
        imgs=POSTS[1]["images"]
        value=client.publish_gallery("📸 GTA VI | Foto ufficiali",imgs)
        self.assertEqual(value,"buffer-id-1")
        self.assertEqual(session.post.call_count,2)
        payload=session.post.call_args.kwargs["json"]["variables"]["input"]
        self.assertEqual(len(payload["assets"]),4)
        self.assertEqual([x["image"]["url"] for x in payload["assets"]],imgs)
        with self.assertRaises(BufferMediaError):
            client.publish_gallery("Ciao",[imgs[0],imgs[0]])
        self.assertEqual(session.post.call_count,2)

    def test_probe_image_network_errors_do_not_approve(self):
        http=Mock()
        http.get.side_effect=OSError("offline")
        self.assertFalse(probe_image(POSTS[1]["images"][0], session=http))

if __name__=="__main__":
    unittest.main()
