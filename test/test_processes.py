import sys
import os
import hashlib
import tempfile
import time
import unittest

from unaltraweb_mcp.processes import run_process


class ProcessInputTests(unittest.TestCase):
    def test_binary_stdout_stream_is_complete_without_bypassing_stderr_bound(self):
        hasher = hashlib.sha256()
        size = 0
        def consume(stream):
            nonlocal size
            while chunk := stream.read(16384):
                size += len(chunk)
                hasher.update(chunk)
        result = run_process([sys.executable, "-c", "import sys; sys.stderr.write('e'*20000); sys.stderr.flush(); sys.stdout.buffer.write(bytes(range(256))*8192)"],
                             timeout_seconds=5, output_limit=100, stdout_consumer=consume)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(size, 2*1024*1024)
        self.assertEqual(hasher.hexdigest(), hashlib.sha256(bytes(range(256))*8192).hexdigest())
        self.assertEqual(result.stdout, "")
        self.assertFalse(result.stdout_truncated)
        self.assertEqual(result.stderr, "e"*100)
        self.assertTrue(result.stderr_truncated)

    def test_receiver_failure_preserves_partial_data_and_terminates_writer(self):
        partial = bytearray()
        def consume(stream):
            partial.extend(stream.read(1024))
            raise ValueError("receiver rejected its partial copy")
        started = time.monotonic()
        with self.assertRaisesRegex(ValueError, "receiver rejected"):
            run_process([sys.executable, "-c", "import os;\nwhile True: os.write(1,b'x'*65536)"],
                        timeout_seconds=10, stdout_consumer=consume)
        self.assertLess(time.monotonic() - started, 5)
        self.assertEqual(partial, b"x"*1024)

    def test_stream_deadline_terminates_descendants_after_the_leader_exits(self):
        partial = bytearray()
        def consume(stream):
            while chunk := stream.read(1024):
                partial.extend(chunk)
        script = "import os,time; pid=os.fork();\nif pid: os._exit(0)\nos.write(1,b'partial'); time.sleep(30)"
        started = time.monotonic()
        result = run_process([sys.executable, "-c", script], timeout_seconds=.2, stdout_consumer=consume)
        self.assertTrue(result.timed_out)
        self.assertEqual(result.returncode, 124)
        self.assertEqual(partial, b"partial")
        self.assertLess(time.monotonic() - started, 5)

    def test_chunk_stream_is_consumed_without_collecting_a_bulk_payload(self):
        count = 0
        def chunks():
            nonlocal count
            for _ in range(32):
                count += 1
                yield b"x" * 65536
        result = run_process([sys.executable, "-c", "import sys; print(len(sys.stdin.buffer.read()))"],
                             input_chunks=chunks(), timeout_seconds=5)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), str(32*65536))
        self.assertEqual(count, 32)

    def test_explicit_guard_descriptor_is_inherited_and_other_descriptors_are_closed(self):
        with tempfile.TemporaryFile() as guard, tempfile.TemporaryFile() as unrelated:
            os.set_inheritable(unrelated.fileno(), True)
            script = "import os,sys; os.fstat(int(sys.argv[1]));\ntry: os.fstat(int(sys.argv[2]))\nexcept OSError: print('guard-only')\nelse: sys.exit(7)"
            result = run_process([sys.executable, "-c", script, str(guard.fileno()), str(unrelated.fileno())],
                                 pass_fds=(guard.fileno(),), timeout_seconds=3)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip(), "guard-only")

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
