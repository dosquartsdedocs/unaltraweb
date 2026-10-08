from __future__ import annotations

import os
import selectors
import signal
import subprocess
import time
import threading
from dataclasses import dataclass
from collections.abc import Iterable
from pathlib import Path


DEFAULT_OUTPUT_LIMIT = 128 * 1024


@dataclass(frozen=True)
class ProcessResult:
    args: list[str]
    returncode: int
    stdout: str
    stderr: str
    timed_out: bool
    stdout_truncated: bool
    stderr_truncated: bool


def run_process(
    command: list[str],
    *,
    cwd: Path | str | None = None,
    env: dict[str, str] | None = None,
    timeout_seconds: float,
    output_limit: int = DEFAULT_OUTPUT_LIMIT,
    input_data: bytes | None = None,
    pass_fds: tuple[int, ...] = (),
    input_chunks: Iterable[bytes] | None = None,
    stdout_consumer=None,
) -> ProcessResult:
    """Run a bounded child process and terminate its process group on timeout."""
    if timeout_seconds <= 0:
        raise ValueError("Process timeout must be positive.")
    if output_limit <= 0:
        raise ValueError("Process output limit must be positive.")
    if input_data is not None and not isinstance(input_data, bytes):
        raise ValueError("Process input must be bytes.")
    if input_data is not None and input_chunks is not None:
        raise ValueError("Process input must use bytes or a bounded chunk stream, not both.")
    if not isinstance(pass_fds, tuple) or any(type(fd) is not int or fd < 0 for fd in pass_fds):
        raise ValueError("Inherited process descriptors must be a tuple of non-negative integers.")
    if stdout_consumer is not None and not callable(stdout_consumer):
        raise ValueError("Process stdout consumer must be callable.")
    chunks = iter(input_chunks) if input_chunks is not None else iter([input_data or b""])

    process = subprocess.Popen(
        command,
        cwd=str(cwd) if cwd is not None else None,
        env=env,
        stdin=subprocess.PIPE if input_data is not None or input_chunks is not None else subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
        **({"pass_fds": pass_fds} if pass_fds else {}),
    )
    assert process.stdout is not None
    assert process.stderr is not None

    selector = selectors.DefaultSelector()
    consumer_error = []
    consumer_thread = None
    if stdout_consumer is None:
        selector.register(process.stdout, selectors.EVENT_READ, "stdout")
    else:
        def consume():
            try:
                stdout_consumer(process.stdout)
            except BaseException as exc:
                consumer_error.append(exc)
            finally:
                process.stdout.close()
        consumer_thread = threading.Thread(target=consume, daemon=True)
        consumer_thread.start()
    selector.register(process.stderr, selectors.EVENT_READ, "stderr")
    pending_input = memoryview(b"")
    input_complete = False
    if process.stdin is not None:
        os.set_blocking(process.stdin.fileno(), False)
        selector.register(process.stdin, selectors.EVENT_WRITE, "stdin")
    output = {"stdout": bytearray(), "stderr": bytearray()}
    truncated = {"stdout": False, "stderr": False}
    deadline = time.monotonic() + timeout_seconds
    timed_out = False
    terminate_deadline = 0.0
    drain_deadline = float("inf")
    killed = False

    try:
        while selector.get_map() or process.poll() is None or (consumer_thread and consumer_thread.is_alive()):
            now = time.monotonic()
            if consumer_error:
                raise consumer_error[0]
            if not timed_out and now >= deadline:
                timed_out = True
                terminate_deadline = now + 1.0
                drain_deadline = now + 2.0
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
            elif timed_out and not killed and now >= terminate_deadline:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                if process.poll() is None:
                    process.kill()
                killed = True
                drain_deadline = now + 1.0
            elif timed_out and now >= drain_deadline and process.poll() is not None:
                for key in list(selector.get_map().values()):
                    selector.unregister(key.fileobj)
                break

            events = selector.select(0.05)
            for key, _ in events:
                stream = str(key.data)
                if stream == "stdin":
                    if not pending_input and not input_complete:
                        try:
                            chunk = next(chunks)
                        except StopIteration:
                            input_complete = True
                        else:
                            if not isinstance(chunk, bytes) or (input_chunks is not None and len(chunk) > 1024*1024):
                                raise ValueError("Process stream chunks must be bytes of at most one MiB.")
                            pending_input = memoryview(chunk)
                            if not pending_input:
                                continue
                    if input_complete:
                        selector.unregister(key.fileobj)
                        key.fileobj.close()
                        continue
                    try:
                        written = os.write(key.fd, pending_input[:65536])
                        pending_input = pending_input[written:]
                    except BlockingIOError:
                        continue
                    except BrokenPipeError:
                        pending_input = memoryview(b"")
                        input_complete = True
                    if input_complete:
                        selector.unregister(key.fileobj)
                        key.fileobj.close()
                    continue
                try:
                    chunk = os.read(key.fd, 65536)
                except BlockingIOError:
                    continue
                if not chunk:
                    selector.unregister(key.fileobj)
                    continue
                remaining = output_limit - len(output[stream])
                if remaining > 0:
                    output[stream].extend(chunk[:remaining])
                if len(chunk) > remaining:
                    truncated[stream] = True

        try:
            process.wait(timeout=1.0 if timed_out else None)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
        if consumer_thread is not None:
            consumer_thread.join(timeout=2)
            if consumer_thread.is_alive():
                raise RuntimeError("Process stream consumer did not terminate; preserve partial output.")
            if consumer_error:
                raise consumer_error[0]
    except BaseException:
        # The group can outlive its leader while descendants still own a pipe.
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait()
        if consumer_thread is not None:
            consumer_thread.join(timeout=2)
        raise
    finally:
        selector.close()
        # The consumer owns its buffered stream; closing it from another thread
        # can deadlock while that thread holds the buffered reader's lock.
        if consumer_thread is None:
            process.stdout.close()
        process.stderr.close()
        if process.stdin is not None and not process.stdin.closed:
            process.stdin.close()

    return ProcessResult(
        args=list(command),
        returncode=124 if timed_out else process.returncode,
        stdout=output["stdout"].decode("utf-8", errors="replace"),
        stderr=output["stderr"].decode("utf-8", errors="replace"),
        timed_out=timed_out,
        stdout_truncated=truncated["stdout"],
        stderr_truncated=truncated["stderr"],
    )
