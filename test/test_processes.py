import sys
import unittest

from unaltraweb_mcp.processes import run_process


class ProcessInputTests(unittest.TestCase):
    def test_large_input_is_drained_with_simultaneous_bounded_output(self):
        payload = b"a" * 1024 * 1024
        result = run_process([sys.executable, "-c", "import sys; sys.stdout.write('x'*200000); sys.stdout.flush(); data=sys.stdin.buffer.read(); sys.stderr.write(str(len(data)))"],
                             input_data=payload, timeout_seconds=5, output_limit=100)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stderr, str(len(payload)))
        self.assertTrue(result.stdout_truncated)
        self.assertEqual(len(result.stdout), 100)

    def test_empty_input_closes_pipe_and_early_exit_is_safe(self):
        empty = run_process([sys.executable, "-c", "import sys; print(len(sys.stdin.buffer.read()))"], input_data=b"", timeout_seconds=3)
        self.assertEqual(empty.stdout.strip(), "0")
        early = run_process([sys.executable, "-c", "pass"], input_data=b"a" * 1024 * 1024, timeout_seconds=3)
        self.assertEqual(early.returncode, 0)

    def test_stalled_input_is_bounded_by_the_deadline(self):
        stalled = run_process([sys.executable, "-c", "import time; time.sleep(30)"], input_data=b"a" * 1024 * 1024, timeout_seconds=.1)
        self.assertEqual(stalled.returncode, 124)
        self.assertTrue(stalled.timed_out)
