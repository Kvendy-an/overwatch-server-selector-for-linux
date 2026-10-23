import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from owselector import client


class SetupTests(unittest.TestCase):
    def test_host_environment_removes_bundled_runtime_paths(self):
        with patch.dict(os.environ, {"LD_LIBRARY_PATH": "/app/lib", "PYTHONHOME": "/app/python", "PYTHONPATH": "/app/gi", "GI_TYPELIB_PATH": "/app/typelibs", "GIO_MODULE_DIR": "/app/gio", "GSETTINGS_SCHEMA_DIR": "/app/schemas", "DISPLAY": ":0"}):
            environment = client.host_environment()
        for name in ("LD_LIBRARY_PATH", "PYTHONHOME", "PYTHONPATH", "GI_TYPELIB_PATH", "GIO_MODULE_DIR", "GSETTINGS_SCHEMA_DIR"):
            self.assertNotIn(name, environment)
        self.assertEqual(environment["DISPLAY"], ":0")

    def test_setup_stages_payload_and_cleans_up(self):
        recorded = []
        def install(args, **kwargs):
            stage = Path(args[2]).parent
            recorded.append(stage)
            self.assertEqual(args[:2], ["pkexec", "/usr/bin/bash"])
            self.assertEqual(args[-1], "--helper-only")
            for path in ("install.sh", "owselector/helper.py", "data/servers.json", "packaging/ow-server-selector.service"):
                self.assertTrue((stage / path).exists())
            self.assertIn("env", kwargs)
            return subprocess.CompletedProcess(args, 0, "Helper installed", "")
        with tempfile.TemporaryDirectory() as cache, patch.object(client.shutil, "which", return_value="/usr/bin/pkexec"), patch.object(client.subprocess, "run", side_effect=install):
            self.assertEqual(client.Client(cache).install_helper(), "Helper installed")
        self.assertFalse(recorded[0].exists())

    def test_setup_failure_reports_error(self):
        with tempfile.TemporaryDirectory() as cache, patch.object(client.shutil, "which", return_value="/usr/bin/pkexec"), patch.object(client.subprocess, "run", return_value=subprocess.CompletedProcess([], 1, "", "nftables missing")):
            with self.assertRaisesRegex(RuntimeError, "nftables missing"):
                client.Client(cache).install_helper()

    def test_missing_polkit_stops_before_staging(self):
        with tempfile.TemporaryDirectory() as cache, patch.object(client.shutil, "which", return_value=None):
            with self.assertRaisesRegex(RuntimeError, "PolicyKit"):
                client.Client(cache).install_helper()


if __name__ == "__main__":
    unittest.main()
