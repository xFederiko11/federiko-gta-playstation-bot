"""Offline checks: the smoke workflow must never schedule or publish."""

import unittest
import json
from unittest.mock import Mock

import buffer_draft_smoke as smoke
from buffer_publisher import (BufferClient, BufferAPIError, BufferMediaError, Delivery)
import online


def response(data):
    value = Mock(status_code=200, headers={})
    value.json.return_value = {"data": data}
    return value


class DraftOnlyTest(unittest.TestCase):
    def setUp(self):
        self.session = Mock()
        self.client = BufferClient("fake-test-key", "channel-1", "myfan", session=self.session)
        self.client.destination = {"id": "channel-1", "service": "twitter"}

    def test_draft_thread_payload_matches_proven_manual_explorer(self):
        self.session.post.return_value = response({"createPost": {"post": {
            "id": "draft-1", "status": "draft", "channelId": "channel-1"}}})
        result = self.client.create_draft_thread(["First", "Second"], media_url="https://www.rockstargames.com/VI/test.jpg")
        self.assertEqual(result, "draft-1")
        self.assertEqual(self.session.post.call_count, 1)
        variables = self.session.post.call_args.kwargs["json"]["variables"]
        payload = variables["input"]
        self.assertEqual(payload["mode"], "addToQueue")
        self.assertIs(payload["saveToDraft"], True)
        self.assertEqual(payload["assets"], [])
        self.assertEqual(payload["metadata"]["twitter"]["thread"][0]["text"], payload["text"])
        self.assertEqual(payload["metadata"]["twitter"]["thread"][0]["assets"][0]["image"]["url"],
                         "https://www.rockstargames.com/VI/test.jpg")
        self.assertEqual(payload["metadata"]["twitter"]["thread"][1]["assets"], [])

    def test_non_draft_status_is_failure_not_success(self):
        self.session.post.return_value = response({"createPost": {"post": {
            "id": "unexpected", "status": "buffer", "channelId": "channel-1"}}})
        with self.assertRaises(BufferAPIError) as error:
            self.client.create_draft_thread(["First", "Second"], media_url="https://example.org/a.jpg")
        self.assertTrue(error.exception.outcome_unknown)
        self.assertEqual(error.exception.post_id, "unexpected")

    def test_no_image_no_mutation(self):
        with self.assertRaises(BufferMediaError):
            self.client.create_draft_thread(["First", "Second"], media_url=None)
        self.session.post.assert_not_called()

    def test_no_auto_publish_and_only_manual_dispatch(self):
        for env in (
            {"GITHUB_EVENT_NAME": "schedule", "BUFFER_DRAFT_SMOKE_ONLY": "1", "AUTO_PUBLISH": "false"},
            {"GITHUB_EVENT_NAME": "workflow_dispatch", "BUFFER_DRAFT_SMOKE_ONLY": "0", "AUTO_PUBLISH": "false"},
            {"GITHUB_EVENT_NAME": "workflow_dispatch", "BUFFER_DRAFT_SMOKE_ONLY": "1", "AUTO_PUBLISH": "true"},
        ):
            client, check = Mock(), Mock()
            with self.subTest(env=env), self.assertRaises(RuntimeError):
                smoke.run(client=client, image_check=check, environ=env)
            client.create_draft_thread.assert_not_called()
            check.assert_not_called()

    def test_image_failure_prevents_buffer_request(self):
        client = Mock()
        with self.assertRaises(RuntimeError):
            smoke.run(client=client, image_check=lambda *args: False, environ={
                "GITHUB_EVENT_NAME": "workflow_dispatch", "BUFFER_DRAFT_SMOKE_ONLY": "1", "AUTO_PUBLISH": "false"})
        client.create_draft_thread.assert_not_called()

    def test_live_runner_threads_keep_official_image_in_first_post(self):
        db = online.open_db(":memory:")
        try:
            event = {
                "event_key": "test-official", "game": "GTA VI", "category": "PATCH",
                "title": "Test official update", "trust": "official", "platforms": ["PS5"],
                "source_url": "https://www.rockstargames.com/newswire/test", "region": "EU",
                "facts": [{"label": "Versione", "value": "1.0"}],
            }
            with db:
                db.execute("INSERT INTO publish_jobs(key,event_json,status,text,created_at) VALUES(?,?,?,?,?)",
                           ("test-official", json.dumps(event), "draft", "test", 100))
            client = Mock(destination={"id": "channel-1"})
            client.publish_thread.return_value = "buffer-draft-test-delivery"
            client.last_delivery = Delivery("buffer-draft-test-delivery", "sent")
            media_url = "https://www.rockstargames.com/VI/test.jpg"
            resolver = Mock(return_value=media_url)
            online.deliver(db, client, Mock(), "/tmp/cards", media_resolver=resolver,
                           news_center_threads=True, require_official_media=True)
            client.publish_thread.assert_called_once()
            thread = client.publish_thread.call_args.args[0]
            self.assertGreaterEqual(len(thread), 2)
            self.assertEqual(client.publish_thread.call_args.kwargs["media_url"], media_url)
            resolver.assert_called_once()
        finally:
            db.close()

    def test_live_runner_blocks_event_when_official_media_missing(self):
        from official_media import OfficialMediaUnavailable
        db = online.open_db(":memory:")
        try:
            event = {
                "event_key": "test-no-image", "game": "GTA VI", "title": "Test news",
                "trust": "official", "platforms": ["PS5"],
                "source_url": "https://www.rockstargames.com/newswire/test",
                "facts": [{"label": "Versione", "value": "1.0"}],
            }
            with db:
                db.execute("INSERT INTO publish_jobs(key,event_json,status,text,created_at) VALUES(?,?,?,?,?)",
                           ("test-no-image", json.dumps(event), "draft", "test", 100))
            client = Mock(destination={"id": "channel-1"})
            resolver = Mock(side_effect=OfficialMediaUnavailable("no_verified_official_image"))
            online.deliver(db, client, Mock(), "/tmp/cards", media_resolver=resolver,
                           news_center_threads=True, require_official_media=True)
            client.publish_thread.assert_not_called()
            client.publish.assert_not_called()
            self.assertEqual(db.execute("SELECT status FROM publish_jobs").fetchone()[0], "review")
        finally:
            db.close()

    def test_test_draft_only_calls_draft_method(self):
        client = Mock()
        client.create_draft_thread.return_value = "draft-12"
        result = smoke.run(client=client, image_check=lambda *args: True, environ={
            "GITHUB_EVENT_NAME": "workflow_dispatch", "BUFFER_DRAFT_SMOKE_ONLY": "1", "AUTO_PUBLISH": "false"})
        self.assertEqual(result, "draft-12")
        client.create_draft_thread.assert_called_once()
        client.publish.assert_not_called()
        client.publish_thread.assert_not_called()


if __name__ == "__main__":
    unittest.main()
