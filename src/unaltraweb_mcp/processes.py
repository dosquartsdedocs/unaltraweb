from __future__ import annotations

import os
import selectors
import signal
import subprocess
import time
from dataclasses import dataclass
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
) -> ProcessResult:
    """Run a bounded child process and terminate its process group on timeout."""
    if timeout_seconds <= 0:
        raise ValueError("Process timeout must be positive.")
    if output_limit <= 0:
        raise ValueError("Process output limit must be positive.")

    process = subprocess.Popen(
        command,
        cwd=str(cwd) if cwd is not None else None,
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )
    assert process.stdout is not None
    assert process.stderr is not None

    selector = selectors.DefaultSelector()
    selector.register(process.stdout, selectors.EVENT_READ, "stdout")
    selector.register(process.stderr, selectors.EVENT_READ, "stderr")
    output = {"stdout": bytearray(), "stderr": bytearray()}
    truncated = {"stdout": False, "stderr": False}
    deadline = time.monotonic() + timeout_seconds
    timed_out = False
    terminate_deadline = 0.0
    drain_deadline = float("inf")
    killed = False

    try:
        while selector.get_map() or process.poll() is None:
            now = time.monotonic()
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
    finally:
        selector.close()
        process.stdout.close()
        process.stderr.close()

    return ProcessResult(
        args=list(command),
        returncode=124 if timed_out else process.returncode,
        stdout=output["stdout"].decode("utf-8", errors="replace"),
        stderr=output["stderr"].decode("utf-8", errors="replace"),
        timed_out=timed_out,
        stdout_truncated=truncated["stdout"],
        stderr_truncated=truncated["stderr"],
    )
