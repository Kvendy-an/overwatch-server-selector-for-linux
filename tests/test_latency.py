import subprocess
import unittest
from unittest.mock import patch

from owselector.core import parse_feed
from owselector.latency import measure
from test_core import feed


class LatencyTests(unittest.TestCase):
    def test_optional_ping_targets_accept_only_public_literals(self):
        for target, expected in [("34.166.0.84", "34.166.0.84"), ("2600:1900:5400::1", "2600:1900:5400::1"), (None, None), ("127.0.0.1", None), ("10.0.0.1", None), ("example.com", None), ("1.1.1.1; id", None), ([], None)]:
            data = feed()
            data['servers']['overwatch'][0]['ping'] = target
            with self.subTest(target=target):
                self.assertEqual(parse_feed(data)[0].ping, expected)

    @patch('owselector.latency.subprocess.run')
    def test_invalid_target_never_launches_command(self, run):
        for target in (None, 'localhost', '127.0.0.1', '1.1.1.1; id'):
            self.assertEqual(measure(target)[0], '—')
        run.assert_not_called()

    @patch('owselector.latency.shutil.which', return_value='/usr/bin/ping')
    @patch('owselector.latency.subprocess.run')
    def test_uses_median_and_isolates_host_runtime(self, run, which):
        run.return_value = subprocess.CompletedProcess([], 0, '64 bytes: time=10.4 ms\n64 bytes: time=40.0 ms\n64 bytes: time=12.2 ms\n', '')
        with patch.dict('os.environ', {'LD_LIBRARY_PATH': '/app/lib', 'PYTHONHOME': '/app/usr'}):
            text, tip = measure('34.166.0.84')
        self.assertEqual(text, '12 ms')
        self.assertIn('3 ICMP replies', tip)
        args, kwargs = run.call_args
        self.assertEqual(args[0][-1], '34.166.0.84')
        self.assertEqual(kwargs['timeout'], 5)
        self.assertEqual(kwargs['env']['LC_ALL'], 'C')
        self.assertNotIn('LD_LIBRARY_PATH', kwargs['env'])

    @patch('owselector.latency.shutil.which', return_value='/usr/bin/ping')
    @patch('owselector.latency.subprocess.run')
    def test_timeouts_no_replies_and_permission_errors(self, run, which):
        run.side_effect = subprocess.TimeoutExpired('ping', 5)
        self.assertEqual(measure('34.166.0.84')[0], 'No reply')
        run.side_effect = None
        for code, expected in [(1, 'No reply'), (2, 'Unavailable')]:
            run.return_value = subprocess.CompletedProcess([], code, '', '')
            self.assertEqual(measure('34.166.0.84')[0], expected)
        run.return_value = subprocess.CompletedProcess([], 1, '64 bytes: time<1 ms', '')
        self.assertEqual(measure('34.166.0.84')[0], '1 ms')

    @patch('owselector.latency.shutil.which', return_value=None)
    def test_missing_ping(self, which):
        self.assertEqual(measure('34.166.0.84')[0], 'Unavailable')
