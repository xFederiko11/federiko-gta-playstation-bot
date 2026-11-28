"""Release-triggered monitor runs use the existing serialized state writer only."""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch, Mock
import json
import os
import unittest
import online


class ReleaseMonitorTests(unittest.TestCase):
    def test_workflow_push_is_narrow_and_cannot_receive_buffer_credentials(self):
        raw = Path(".github/workflows/gta-monitor.yml").read_text()
        trigger = raw.split("on:\n", 1)[1].split("  schedule:", 1)[0]
        self.assertIn("branches: [main]", trigger)
        self.assertIn("'sources.py'", trigger)
        self.assertIn("'state_health.py'", trigger)
        self.assertNotIn("monitor-health.json", trigger)
        self.assertNotIn(".state/", trigger)
        self.assertIn("github.event_name == 'push' && 'collect'", raw)
        for secret in ("BUFFER_API_KEY", "BUFFER_CHANNEL_ID"):
            self.assertIn("github.event_name != 'push' && secrets." + secret + " || ''", raw)
        self.assertIn("gta-v142-publication-global", raw)
        self.assertIn("cancel-in-progress: false", raw)

    def test_collect_mode_polls_real_pipeline_without_buffer_or_optional_research(self):
        for enabled in ("true", "false"):
            with self.subTest(publishing_enabled=enabled), TemporaryDirectory() as tmp:
                root = Path(tmp)
                config = {"scope": "gta", "sources": [], "system_software": {"enabled": False}}
                (root / "history-seed.json").write_text("[]")
                env = {"RUN_MODE": "collect", "AUTO_PUBLISH": enabled,
                       "STATE_PASSWORD": "test-password-long-enough",
                       "DATABASE": str(root / "db.sqlite"),
                       "ENCRYPTED_STATE": str(root / "state.enc"),
                       "WEEKLY_RADAR_V12_ENABLED": "true",
                       "INTELLIGENCE_V12_ENABLED": "true", "EDITORIAL_V13_ENABLED": "true",
                       "EDITORIAL_V13_AUTOPUBLISH": "true"}
                with (patch.dict(os.environ, env, clear=True),
                      patch("sys.argv", ["online.py", "--once"]),
                      patch.object(online, "ROOT", root),
                      patch.object(online.sources, "load_config", return_value=config),
                      patch.object(online.sources, "poll", return_value=2) as poll,
                      patch.object(online, "collect_system_updates", return_value=0) as sony,
                      patch.object(online, "prepare_jobs", return_value=0) as prepare,
                      patch.object(online, "needs_first_publication_baseline", return_value=False),
                      patch.object(online, "suppress_unpublished", return_value=0) as suppress,
                      patch.object(online, "BufferClient", side_effect=AssertionError("Buffer forbidden")) as buffer,
                      patch.object(online, "deliver", side_effect=AssertionError("delivery forbidden")) as deliver,
                      patch.object(online, "render_card", side_effect=AssertionError("preview forbidden")),
                      patch("intelligence_v12.poll", side_effect=AssertionError("optional research forbidden")) as research,
                      patch("weekly_radar_v12.poll", side_effect=AssertionError("optional radar forbidden")) as radar,
                      patch("editorial_v13.research", side_effect=AssertionError("optional editorial forbidden")) as editorial):
                    online.main()
                    poll.assert_called_once()
                    sony.assert_called_once()
                    prepare.assert_called_once()
                    buffer.assert_not_called()
                    deliver.assert_not_called()
                    research.assert_not_called()
                    radar.assert_not_called()
                    editorial.assert_not_called()
                    self.assertEqual(suppress.call_count, int(enabled == "false"))
                self.assertTrue((root / "state.enc").exists())
                self.assertTrue((root / "monitor-health.json").exists())
