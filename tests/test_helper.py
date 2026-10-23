import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from owselector import helper
from owselector.core import atomic_json
from test_core import feed


class HelperTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.state = Path(self.directory.name) / "state.json"
        self.cache = Path(self.directory.name) / "servers.json"
        for name, value in [("STATE", self.state), ("CACHE", self.cache)]:
            p = patch.object(helper, name, value)
            p.start()
            self.addCleanup(p.stop)
        atomic_json(self.cache, feed())
        atomic_json(self.state, {"blocked": ["gmec2"], "uid": 1000, "auto_update": True})

    def test_failed_check_never_commits(self):
        fail = subprocess.CompletedProcess([], 1, "", "syntax error")
        with patch.object(helper, "table_exists", return_value=True), patch.object(helper, "run_nft", return_value=fail) as nft:
            with self.assertRaisesRegex(RuntimeError, "syntax error"):
                helper.apply_rules(helper.parse_feed(feed()), ["gmec2"], 1000)
            self.assertEqual(nft.call_count, 1)
            self.assertIn("--check", nft.call_args.args[0])

    def test_check_and_commit_identical_transaction(self):
        ok = subprocess.CompletedProcess([], 0, "", "")
        with patch.object(helper, "table_exists", return_value=True), patch.object(helper, "run_nft", return_value=ok) as nft:
            helper.apply_rules(helper.parse_feed(feed()), ["gmec2"], 1000)
            self.assertEqual(nft.call_count, 2)
            self.assertEqual(nft.call_args_list[0].args[1], nft.call_args_list[1].args[1])

    def test_update_network_failure_retains_cache_and_restores_blocks(self):
        original = self.cache.read_bytes()
        with patch.object(helper, "fetch_feed", side_effect=OSError("offline")), patch.object(helper, "apply_rules") as apply:
            with self.assertRaisesRegex(RuntimeError, "saved blocks retained"):
                helper.refresh()
            self.assertEqual(apply.call_args.args[1], ["gmec2"])
        self.assertEqual(self.cache.read_bytes(), original)
        self.assertEqual(json.loads(self.state.read_text())["blocked"], ["gmec2"])

    def test_removed_server_does_not_replace_cache(self):
        original = self.cache.read_bytes()
        updated = feed()
        updated["servers"]["overwatch"][1]["token"] = "new1"
        ok = subprocess.CompletedProcess([], 0, "", "")
        with patch.object(helper, "fetch_feed", return_value=updated), patch.object(helper, "table_exists", return_value=True), patch.object(helper, "run_nft", return_value=ok):
            with self.assertRaisesRegex(RuntimeError, "no longer in the list"):
                helper.refresh()
        self.assertEqual(self.cache.read_bytes(), original)

    def test_successful_refresh_applies_new_ranges(self):
        updated = feed()
        updated["servers"]["overwatch"][1]["block"] = "34.167.0.0/16"
        with patch.object(helper, "fetch_feed", return_value=updated), patch.object(helper, "apply_rules") as apply:
            helper.refresh()
        self.assertEqual(str(apply.call_args.args[0][1].networks[0]), "34.167.0.0/16")
        self.assertEqual(json.loads(self.cache.read_text()), updated)
        self.assertIsNone(json.loads(self.state.read_text())["error"])

    def test_no_auto_update_restores_without_network(self):
        state = json.loads(self.state.read_text())
        state["auto_update"] = False
        atomic_json(self.state, state)
        with patch.object(helper, "fetch_feed") as fetch, patch.object(helper, "apply_rules"):
            helper.refresh()
        fetch.assert_not_called()

    def test_emergency_unblock_does_not_need_feed(self):
        self.cache.write_text("corrupted")
        with patch.object(helper, "fetch_feed") as fetch, patch.object(helper, "saved_feed", side_effect=OSError("broken")), patch.object(helper, "apply_rules") as apply:
            result = helper.apply_request({"blocked": [], "auto_update": True}, 1000)
        self.assertEqual(result["blocked"], [])
        apply.assert_called_once_with((), [], 1000)
        fetch.assert_not_called()

    def test_apply_failure_does_not_save_new_selection(self):
        original = self.state.read_bytes()
        with patch.object(helper, "fetch_feed", return_value=feed()), patch.object(helper, "apply_rules", side_effect=RuntimeError("kernel rejected")):
            with self.assertRaises(RuntimeError):
                helper.apply_request({"blocked": ["ams1"], "auto_update": True}, 1000)
        self.assertEqual(self.state.read_bytes(), original)

    def test_rejects_arbitrary_input_and_other_account(self):
        for request in [{"script": "flush ruleset"}, {"blocked": [], "auto_update": "yes"}]:
            with self.assertRaises(ValueError):
                helper.apply_request(request, 1000)
        with self.assertRaisesRegex(ValueError, "Another account"):
            helper.apply_request({"blocked": [], "auto_update": True}, 1001)


if __name__ == "__main__":
    unittest.main()
