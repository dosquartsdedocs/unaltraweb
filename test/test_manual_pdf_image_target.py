from __future__ import annotations

import os
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class ManualPdfImageTargetTests(unittest.TestCase):
    def test_missing_registry_image_falls_back_to_factory_build(self) -> None:
        with tempfile.TemporaryDirectory() as raw_temp:
            temp = Path(raw_temp)
            docker = temp / "docker"
            log = temp / "docker.log"
            docker.write_text(
                """#!/bin/sh
printf '%s\\n' "$*" >> "$DOCKER_LOG"
case "$1" in
  image) exit 1 ;;
  pull) exit 1 ;;
  build) exit 0 ;;
esac
exit 0
""",
                encoding="utf-8",
            )
            docker.chmod(0o755)
            env = {
                **os.environ,
                "DOCKER_LOG": str(log),
                "PATH": f"{temp}:{os.environ['PATH']}",
            }

            completed = subprocess.run(
                [
                    "make",
                    "--silent",
                    "manual-pdf-image",
                    "MANUAL_PDF_IMAGE=example.test/unaltraweb-manual-pdf:0.3.0",
                ],
                cwd=ROOT,
                env=env,
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertIn("not published", completed.stderr)
            self.assertEqual(
                log.read_text(encoding="utf-8").splitlines(),
                [
                    "image inspect example.test/unaltraweb-manual-pdf:0.3.0",
                    "pull example.test/unaltraweb-manual-pdf:0.3.0",
                    "build --network default -f scripts/manual/Dockerfile -t example.test/unaltraweb-manual-pdf:0.3.0 scripts/manual",
                ],
            )


if __name__ == "__main__":
    unittest.main()
