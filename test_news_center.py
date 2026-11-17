import unittest
from unittest.mock import Mock

from buffer_publisher import BufferClient, BufferPending
from news_center import thread_for_event, news_center_preview
from presentation import _post_weight


def playstation_event():
    return {
        "event_key": "sony-system:PS5:26.07-14.23.00", "game": "PlayStation",
        "category": "SISTEMA", "trust": "official", "platforms": ["PS5"],
        "title": "Aggiornamento di sistema disponibile", "version": "26.07-14.23.00",
        "facts": [
            {"label": "Versione ufficiale", "value": "26.07-14.23.00"},
            {"label": "Novita' indicate da Sony", "value": "Correzioni di sicurezza del software di sistema."},
            {"label": "Data di rilascio", "value": None},
        ],
        "source_url": "https://www.playstation.com/it-it/support/hardware/ps5/system-software-info/",
    }


class NewsCenterTests(unittest.TestCase):
    def test_official_system_update_becomes_bounded_thread(self):
        parts = thread_for_event(playstation_event())
        self.assertEqual(len(parts), 3)
        self.assertTrue(all(_post_weight(p) <= 280 for p in parts))
        self.assertIn("26.07-14.23.00", " ".join(parts))
        self.assertIn("Fonte", parts[-1].replace("FONTE", "Fonte"))
        self.assertNotIn("17 novembre", " ".join(parts))
        self.assertNotIn("FPS", " ".join(parts))

    def test_community_uncertain_spoiler_or_unsupported_not_threaded(self):
        event = playstation_event()
        self.assertIsNone(thread_for_event({**event, "trust": "community"}))
        self.assertIsNone(thread_for_event({**event, "spoiler": True}))
        self.assertIsNone(thread_for_event({**event, "game": "GTA Online"}))
        self.assertIsNone(thread_for_event({**event, "facts": []}))

    def test_unverified_release_date_not_invented(self):
        event = playstation_event()
        event["observed_at"] = "2026-11-17T19:00:00Z"
        parts = thread_for_event(event)
        self.assertNotIn("19:00", " ".join(parts))
        self.assertNotIn("uscito oggi", " ".join(parts))

    def test_preview_falls_back_to_existing_single_post(self):
        event = playstation_event()
        event["game"] = "GTA Online"
        self.assertEqual(len(news_center_preview(event)), 1)


class BufferThreadTests(unittest.TestCase):
    def setUp(self):
        self.session = Mock()
        self.client = BufferClient("fake-test-key", "channel-1", "myfan", session=self.session)
        self.client.destination = {"id": "channel-1", "service": "twitter"}

    @staticmethod
    def reply(status="sent"):
        response = Mock(status_code=200, headers={})
        response.json.return_value = {"data": {"createPost": {"post": {
            "id": "buffer-thread-1", "status": status, "channelId": "channel-1",
        }}}}
        return response

    def test_one_api_mutation_contains_all_parts_in_order(self):
        parts = ["1/2 GTA VI NEWS CENTER", "2/2 Fonte ufficiale"]
        self.session.post.return_value = self.reply()
        self.assertEqual(self.client.publish_thread(parts), "buffer-thread-1")
        self.session.post.assert_called_once()
        payload = self.session.post.call_args.kwargs["json"]["variables"]["input"]
        self.assertEqual(payload["text"], parts[0])
        self.assertEqual([x["text"] for x in payload["metadata"]["twitter"]["thread"]], parts)
        self.assertEqual(payload["assets"], [])
        self.assertEqual(payload["mode"], "shareNow")

    def test_invalid_threads_never_use_network(self):
        for parts in [["solo"], ["uno", ""], ["a", "b" * 281], []]:
            with self.subTest(parts=parts):
                with self.assertRaises(ValueError):
                    self.client.publish_thread(parts)
        self.session.post.assert_not_called()

    def test_pending_thread_not_resubmitted(self):
        self.session.post.return_value = self.reply("sending")
        with self.assertRaises(BufferPending) as cm:
            self.client.publish_thread(["Uno", "Due"])
        self.assertEqual(cm.exception.post_id, "buffer-thread-1")
        self.session.post.assert_called_once()

if __name__ == "__main__":
    unittest.main()

class ThreadDeliveryTests(unittest.TestCase):
    def test_online_delivers_thread_once_and_does_not_upload_image(self):
        import tempfile
        import json
        import time
        import online
        with tempfile.TemporaryDirectory() as td:
            db = online.open_db(td + "/db.sqlite")
            event = playstation_event()
            db.execute("INSERT INTO publish_jobs(key,event_json,status,text,created_at) VALUES (?,?,?,?,?)",
                       ("thread-key", json.dumps(event), "draft", "single message", time.time()))
            db.commit()
            client = Mock(destination={"id": "channel-1"})
            client.publish_thread.return_value = "buffer-thread-1"
            client.last_delivery.external_url = "https://x.com/myfan/status/123"
            uploader = Mock()
            renderer = Mock()
            online.deliver(db, client, uploader, td, render=renderer, news_center_threads=True)
            self.assertEqual(db.execute("SELECT status FROM publish_jobs").fetchone()[0], "posted")
            client.publish_thread.assert_called_once()
            client.publish.assert_not_called()
            uploader.assert_not_called()
            renderer.assert_not_called()
            db.close()
