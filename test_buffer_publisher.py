import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

import requests

from buffer_publisher import (BufferClient, BufferAPIError, BufferPending,
                              BufferDeliveryFailed, BufferConfigurationError, BufferMediaError)


def response(data=None, status=200, headers=None):
    value = Mock(status_code=status, headers=headers or {})
    value.json.return_value = {"data": data} if data is not None else {}
    return value


def channel(**extra):
    return {"id": "channel-1", "name": "myfan", "service": "twitter",
            "isDisconnected": False, "isLocked": False, "isQueuePaused": False,
            "externalLink": "https://x.com/myfan", **extra}


def delivered(status="sent"):
    return {"createPost": {"post": {"id": "buffer-post-1", "status": status,
            "channelId": "channel-1", "externalLink": "https://x.com/myfan/status/123"}}}


class BufferPublisherTests(unittest.TestCase):
    def setUp(self):
        self.session = Mock()
        # Legacy protocol tests exercise Buffer responses; a separate test verifies
        # the production default refusing text-only X submissions.
        self.client = BufferClient("test-key-not-real", "channel-1", "myfan",
                                   session=self.session, require_media=False)

    def test_destination_is_checked_before_first_write_and_cached(self):
        self.session.post.side_effect = [response({"channel": channel()}), response(delivered()), response(delivered())]
        self.assertEqual(self.client.publish("First"), "buffer-post-1")
        self.client.publish("Second")
        self.assertEqual(self.session.post.call_count, 3)
        mutation = self.session.post.call_args_list[1].kwargs["json"]
        self.assertEqual(mutation["variables"]["input"]["mode"], "shareNow")
        self.assertEqual(mutation["variables"]["input"]["schedulingType"], "automatic")

    def test_wrong_destination_or_service_prevents_creation(self):
        for value in [channel(externalLink="https://x.com/other"), channel(service="instagram"), channel(isDisconnected=True), channel(isLocked=True)]:
            with self.subTest(value=value):
                self.session.reset_mock()
                self.session.post.return_value = response({"channel": value})
                with self.assertRaises(BufferConfigurationError):
                    self.client.publish("Do not create")
                self.assertEqual(self.session.post.call_count, 1)

    def test_display_name_may_differ_when_profile_url_confirms_handle(self):
        self.session.post.return_value = response({"channel": channel(name="My GTA Fan Updates", externalLink="https://x.com/MyFan/")})
        self.assertEqual(self.client.verify_destination()["name"], "My GTA Fan Updates")

    def test_legacy_twitter_profile_url_confirms_handle(self):
        self.session.post.return_value = response({"channel": channel(name="Display name", externalLink="https://twitter.com/MYFAN?lang=it")})
        self.client.verify_destination()

    def test_name_fallback_only_without_link_and_with_handle_shape(self):
        self.session.post.return_value = response({"channel": channel(name="@myfan", externalLink=None)})
        self.client.verify_destination()
        self.session.post.return_value = response({"channel": channel(name="My Fan Updates", externalLink=None)})
        with self.assertRaises(BufferConfigurationError):
            self.client.verify_destination()

    def test_profile_link_mismatch_is_not_hidden_by_matching_name(self):
        for link in ("https://x.com/other", "https://x.com.evil.example/myfan", "https://x.com/i/user/123"):
            with self.subTest(link=link):
                self.session.post.return_value = response({"channel": channel(name="myfan", externalLink=link)})
                with self.assertRaises(BufferConfigurationError):
                    self.client.verify_destination()

    def test_pending_is_not_reported_as_sent_and_does_not_retry(self):
        self.session.post.side_effect = [response({"channel": channel()}), response(delivered("sending"))]
        with self.assertRaises(BufferPending) as result:
            self.client.publish("Hello")
        self.assertEqual(result.exception.post_id, "buffer-post-1")
        self.assertEqual(result.exception.delivery_state, "sending")
        self.assertFalse(result.exception.outcome_unknown)
        self.assertEqual(self.session.post.call_count, 2)

    def test_delivery_read_reuses_post_id_without_create(self):
        self.session.post.return_value = response({"post": delivered()["createPost"]["post"]})
        result = self.client.delivery_status("buffer-post-1")
        self.assertEqual(result.status, "sent")
        self.assertEqual(result.external_url, "https://x.com/myfan/status/123")
        payload = self.session.post.call_args.kwargs["json"]
        self.assertNotIn("createPost", payload["query"])
        self.assertEqual(payload["variables"]["id"], "buffer-post-1")

    def test_known_delivery_failure_retains_buffer_id(self):
        self.session.post.side_effect = [response({"channel": channel()}), response(delivered("error"))]
        with self.assertRaises(BufferDeliveryFailed) as result:
            self.client.publish("Hello")
        self.assertEqual(result.exception.post_id, "buffer-post-1")

    def test_timeout_during_write_is_uncertain_without_retry(self):
        self.session.post.side_effect = [response({"channel": channel()}), requests.Timeout()]
        with self.assertRaises(BufferAPIError) as result:
            self.client.publish("Hello")
        self.assertTrue(result.exception.outcome_unknown)
        self.assertEqual(self.session.post.call_count, 2)

    def test_http_429_respects_exhausted_policy(self):
        self.client.destination = channel()
        self.session.post.return_value = response(status=429, headers={
            "RateLimit": '"150-in-15min";r=0;t=240,"1000-in-30days";r=900;t=2600000'})
        with self.assertRaises(BufferAPIError) as result:
            self.client.publish("Hello")
        self.assertEqual(result.exception.retry_after, 240)
        self.assertFalse(result.exception.outcome_unknown)

    def test_server_error_is_uncertain(self):
        self.client.destination = channel()
        self.session.post.return_value = response(status=503)
        with self.assertRaises(BufferAPIError) as result:
            self.client.publish("Hello")
        self.assertTrue(result.exception.outcome_unknown)

    def test_typed_mutation_error_is_rejected_and_does_not_expose_remote_message(self):
        self.client.destination = channel()
        self.session.post.return_value = response({"createPost": {"message": "remote private test-key-not-real"}})
        with self.assertRaises(BufferAPIError) as result:
            self.client.publish("Hello")
        self.assertFalse(result.exception.outcome_unknown)
        self.assertNotIn("test-key-not-real", str(result.exception))

    def test_partial_graphql_response_is_uncertain(self):
        self.client.destination = channel()
        value = response(delivered())
        value.json.return_value["errors"] = [{"message": "partial"}]
        self.session.post.return_value = value
        with self.assertRaises(BufferAPIError) as result:
            self.client.publish("Hello")
        self.assertTrue(result.exception.outcome_unknown)

    def test_production_default_rejects_text_only_post_and_thread_before_network(self):
        client = BufferClient("test-key-not-real", "channel-1", "myfan",
                              session=self.session)
        with self.assertRaises(BufferMediaError):
            client.publish("GTA VI: dettagli importanti")
        with self.assertRaises(BufferMediaError):
            client.publish_thread(["GTA VI: punto uno", "Fonte: Rockstar Games"])
        self.session.post.assert_not_called()

    def test_production_default_sends_photo_in_buffer_payload(self):
        client = BufferClient("test-key-not-real", "channel-1", "myfan",
                              session=self.session)
        self.session.post.side_effect = [response({"channel": channel()}), response(delivered())]
        client.publish("GTA VI Italia", media_url="https://cdn.example.org/gta-vi-photo.jpg")
        payload = self.session.post.call_args.kwargs["json"]["variables"]["input"]
        self.assertEqual(payload["assets"], [
            {"image": {"url": "https://cdn.example.org/gta-vi-photo.jpg"}}])

    def test_public_image_url_is_passed_as_asset(self):
        self.session.post.side_effect = [response({"channel": channel()}), response(delivered())]
        self.client.publish("Card", "https://cdn.example.org/card.png")
        assets = self.session.post.call_args.kwargs["json"]["variables"]["input"]["assets"]
        self.assertEqual(assets, [{"image": {"url": "https://cdn.example.org/card.png"}}])

    def test_local_media_without_hosting_does_not_create_post(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "card.png"
            path.write_bytes(b"not-a-real-image")
            with self.assertRaises(BufferMediaError):
                self.client.publish("Card", path)
        self.session.post.assert_not_called()

    def test_local_media_can_use_explicit_uploader(self):
        self.session.post.side_effect = [response({"channel": channel()}), response(delivered())]
        uploader = Mock(return_value="https://cdn.example.org/hosted.png")
        self.client.media_uploader = uploader
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "card.png"
            path.write_bytes(b"not-a-real-image")
            self.client.publish("Card", path)
            uploader.assert_called_once_with(path)

    def test_unknown_response_never_claims_success(self):
        self.client.destination = channel()
        self.session.post.return_value = response({"createPost": {}})
        with self.assertRaises(BufferAPIError) as result:
            self.client.publish("Hello")
        self.assertTrue(result.exception.outcome_unknown)

    def test_setup_lists_real_channels_without_a_selected_channel(self):
        client = BufferClient("test-only", channel_id="", session=self.session)
        self.session.post.side_effect = [
            response({"account": {"organizations": [{"id": "org-real-id", "name": "Personal"}]}}),
            response({"channels": [channel()]}),
        ]
        values = client.list_channels()
        self.assertEqual(values[0]["id"], "channel-1")
        self.assertEqual(values[0]["organization_id"], "org-real-id")
        self.assertEqual(self.session.post.call_count, 2)
        with self.assertRaises(BufferConfigurationError):
            client.verify_destination()

    def test_explicit_media_url_and_request_guard(self):
        guard = Mock()
        self.client.request_guard = guard
        self.session.post.side_effect = [response({"channel": channel()}), response(delivered())]
        self.client.publish("Card", media_url="https://raw.githubusercontent.com/account/repo/main/card.png")
        self.assertEqual(guard.call_count, 2)
        assets = self.session.post.call_args.kwargs["json"]["variables"]["input"]["assets"]
        self.assertIn("raw.githubusercontent.com", assets[0]["image"]["url"])

    def test_blocked_request_guard_does_not_send(self):
        self.client.request_guard = Mock(side_effect=RuntimeError("quota locale esaurita"))
        with self.assertRaises(RuntimeError):
            self.client.publish("Hello")
        self.session.post.assert_not_called()

    def test_both_local_and_remote_media_are_rejected_without_network(self):
        with self.assertRaises(BufferMediaError):
            self.client.publish("Hello", media_path="card.png", media_url="https://example.org/card.png")
        self.session.post.assert_not_called()

    def test_image_thread_requires_reserved_character_budget_before_network(self):
        a="🚗 GTA VI | "+("A"*245)
        with self.assertRaises(ValueError):
            self.client.publish_thread([a,"📖 Fonte: PowerPyx"],media_url="https://cdn.example.org/photo.jpg")
        self.session.post.assert_not_called()


if __name__ == "__main__":
    unittest.main()
