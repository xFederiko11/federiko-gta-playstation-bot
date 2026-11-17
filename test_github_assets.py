import base64
import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from github_assets import AssetHostError, GitHubAssetHost, PNG_HEADER


class AssetTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.file = Path(self.temp.name) / "card.png"
        self.content = PNG_HEADER + b"test card pixels"
        self.file.write_bytes(self.content)
        self.session = Mock()
        self.host = GitHubAssetHost("not-a-real-token", "example/gtabot", session=self.session)
        self.sha = hashlib.sha1(b"blob " + str(len(self.content)).encode() + b"\0" + self.content, usedforsecurity=False).hexdigest()

    def tearDown(self):
        self.temp.cleanup()

    def response(self, status, data):
        response = Mock(status_code=status)
        response.json.return_value = data
        return response

    def public_repository(self):
        return self.response(200, {"private": False, "visibility": "public", "full_name": "example/gtabot", "default_branch": "main"})

    def test_new_png_is_uploaded_once_with_immutable_url(self):
        self.session.get.side_effect = [self.public_repository(), self.response(404, {})]
        self.session.put.return_value = self.response(201, {"content": {}, "commit": {"sha": "a" * 40}})
        result = self.host.upload(self.file)
        self.assertIn("/" + "a" * 40 + "/cards/", result)
        self.assertTrue(result.endswith(hashlib.sha256(self.content).hexdigest() + ".png"))
        payload = self.session.put.call_args.kwargs["json"]
        self.assertEqual(base64.b64decode(payload["content"]), self.content)
        self.assertEqual(payload["branch"], "main")

    def test_existing_image_is_reused_and_repository_checked_once(self):
        existing = self.response(200, {"sha": self.sha, "download_url": "https://raw.githubusercontent.com/example/gtabot/main/cards/existing.png"})
        self.session.get.side_effect = [self.public_repository(), existing, existing]
        first = self.host.upload(self.file)
        second = self.host.upload(self.file)
        self.assertEqual(first, second)
        self.assertEqual(self.session.get.call_count, 3)
        self.session.put.assert_not_called()

    def test_private_repository_is_rejected_before_upload(self):
        self.session.get.return_value = self.response(200, {"private": True, "default_branch": "main"})
        with self.assertRaises(AssetHostError):
            self.host.upload(self.file)
        self.session.put.assert_not_called()

    def test_same_filename_with_different_content_is_not_overwritten(self):
        self.session.get.side_effect = [self.public_repository(), self.response(200, {"sha": "wrong"})]
        with self.assertRaises(AssetHostError):
            self.host.upload(self.file)
        self.session.put.assert_not_called()

    def test_non_png_and_unsafe_repository_are_rejected(self):
        self.file.write_text("not a PNG")
        with self.assertRaises(AssetHostError):
            self.host.upload(self.file)
        self.session.get.assert_not_called()
        with self.assertRaises(AssetHostError):
            GitHubAssetHost("token", "../bad/repo", session=self.session)

    def test_racing_upload_reuses_identical_remote_content(self):
        self.session.get.side_effect = [self.public_repository(), self.response(404, {}), self.response(200, {"sha": self.sha})]
        self.session.put.return_value = self.response(422, {})
        self.assertIn("raw.githubusercontent.com", self.host.upload(self.file))
        self.session.put.assert_called_once()


if __name__ == "__main__":
    unittest.main()
