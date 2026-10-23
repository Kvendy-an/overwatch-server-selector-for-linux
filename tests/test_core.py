import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from owselector import core


def feed():
    return {"servers": {"overwatch": [
        {"token": "ams1", "title": "Netherlands", "block": "64.224.26.0/23"},
        {"token": "gmec2", "title": "Saudi Arabia", "block": "34.166.0.0/16,2600:1900:5400::/44"},
    ]}}


class FeedTests(unittest.TestCase):
    def test_bundled_feed_parses(self):
        servers = core.parse_feed(core.read_feed(core.BUNDLE))
        self.assertGreaterEqual(len(servers), 2)
        self.assertIn("gmec2", {s.token for s in servers})

    def test_rejects_malformed_and_private_ranges(self):
        for value in ["0.0.0.0/0", "10.0.0.0/8", "127.0.0.1", "::/0", "fd00::/64",
                      "34.166.0.0/16 }; flush ruleset", "34.166.1.0/16", ""]:
            with self.subTest(value=value):
                data = feed()
                data["servers"]["overwatch"][0]["block"] = value
                with self.assertRaises(ValueError):
                    core.parse_feed(data)

    def test_rejects_duplicate_tokens(self):
        data = feed()
        data["servers"]["overwatch"][1]["token"] = "ams1"
        with self.assertRaises(ValueError):
            core.parse_feed(data)

    def test_rejects_invalid_records(self):
        for data in [{}, {"servers": {"overwatch": []}}, {"servers": {"overwatch": [None, {}]}}]:
            with self.assertRaises(ValueError):
                core.parse_feed(data)

    def test_rejects_non_text_fields_and_controls(self):
        for key, value in [("token", "abc; flush"), ("title", "name\n"), ("block", []), ("title", None)]:
            data = feed()
            data["servers"]["overwatch"][0][key] = value
            with self.assertRaises(ValueError):
                core.parse_feed(data)

    def test_fetch_rejects_oversize_response(self):
        class Response:
            def __enter__(self): return self
            def __exit__(self, *_): pass
            def geturl(self): return core.FEED_URL
            def read(self, limit): return b"x" * limit
        with patch.object(core, "urlopen", return_value=Response()):
            with self.assertRaisesRegex(ValueError, "too large"):
                core.fetch_feed()

    def test_atomic_save_keeps_previous_file_on_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "data.json"
            core.atomic_json(path, {"old": True})
            with patch.object(core.os, "replace", side_effect=OSError("disk failure")):
                with self.assertRaises(OSError):
                    core.atomic_json(path, {"new": True})
            self.assertEqual(json.loads(path.read_text()), {"old": True})
            self.assertEqual(len(list(Path(directory).iterdir())), 1)


class RulesTests(unittest.TestCase):
    def setUp(self):
        self.servers = core.parse_feed(feed())

    def test_dual_stack_scoped_to_uid(self):
        text = core.render_rules(self.servers, ["gmec2"], 1000)
        self.assertIn("meta skuid 1000 ip daddr @blocked_v4", text)
        self.assertIn("meta skuid 1000 ip6 daddr @blocked_v6", text)
        self.assertNotIn("64.224.26.0/23", text)
        self.assertNotIn("flush ruleset", text)
        self.assertNotIn("hook input", text)

    def test_unknown_ids_and_all_servers_rejected(self):
        for tokens in [["unknown"], ["ams1", "gmec2"], ["gmec2", "gmec2"], [1], "gmec2"]:
            with self.assertRaises(ValueError):
                core.render_rules(self.servers, tokens, 1000)

    def test_root_and_invalid_uids_rejected(self):
        for uid in [0, -1, 999, True, "1000", 2**32]:
            with self.assertRaises(ValueError):
                core.render_rules(self.servers, ["gmec2"], uid)

    def test_unblock_only_deletes_our_table(self):
        self.assertEqual(core.render_rules((), [], 1000, True), "delete table inet ow_server_selector\n")
        self.assertEqual(core.render_rules((), [], 1000, False), "")

    def test_atomic_replacement_deletes_before_create(self):
        text = core.render_rules(self.servers, ["ams1"], 1000, True)
        self.assertTrue(text.startswith("delete table inet ow_server_selector\ntable inet ow_server_selector {"))

    def test_overlapping_ranges_collapsed(self):
        data = feed()
        data["servers"]["overwatch"][0]["block"] = "64.224.26.0/23,64.224.26.0/24"
        text = core.render_rules(core.parse_feed(data), ["ams1"], 1000)
        self.assertIn("64.224.26.0/23", text)
        self.assertNotIn("64.224.26.0/24", text)


if __name__ == "__main__":
    unittest.main()
