"""Real MCP resource reads, independent of QGIS images or teaching inputs."""
from __future__ import annotations

import asyncio
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

from unaltraweb_mcp.practice_verifier import CONTRACT


async def assert_practice_resources(session) -> None:
    """Shared by source regression and installed-image MCP smoke."""
    schemas = {
        "web://practice-edition-schema": CONTRACT.with_name("practice-edition-v1.schema.json"),
        "web://practice-verifier-runtime": CONTRACT,
    }
    resources = {str(item.uri) for item in (await session.list_resources()).resources}
    assert schemas.keys() <= resources, resources
    values = {}
    for uri, path in schemas.items():
        response = await session.read_resource(uri)
        assert len(response.contents) == 1 and hasattr(response.contents[0], "text"), response
        values[uri] = json.loads(response.contents[0].text)
        assert values[uri] == json.loads(path.read_bytes()), uri

    edition = values["web://practice-edition-schema"]
    assert edition["properties"]["kind"]["const"] == "unaltraweb-practice-edition"
    assert edition["properties"]["gis"]["properties"]["profile"]["enum"] == ["qgis-practice-v1", "qgis-practice-v2"]
    verifier = values["web://practice-verifier-runtime"]
    assert verifier["kind"] == "unaltraweb-private-practice-verifier" and verifier["origin"] == "prepared-image"
    assert verifier["provider"] == {
        "name": "unaltracaptura-qgis", "version": "0.6.1",
        "installed_revision": "sha256:4604801be887a19747aa74c84a2d99141308fadde44f5cddacb4d821b6861398",
    }
    assert verifier["controller"]["image_id"] == "sha256:d06b742c3e7d2e9383cf8a1d22bce928dd806f316a0bcbb1f676f50e22e94b05"
    assert verifier["engine"]["image_id"] == "sha256:1003721d96abe9607d8337b36851f9b29f84c2f8f92b377d1a73ff03c9d15cd2"
    assert verifier["profiles"] == {
        "qgis-practice-v1": "9bc7f15ede9d67b3e1209c329da13d9fcb08004090d05b27662a43de6edf3445",
        "qgis-practice-v2": "528c8be229c72c346f134ffaa60094f94224094a25b6fb11bcc87802ddc7fffb",
    }
    assert verifier["release"]["practice_producer_revision"] == "sha256:35443a3343f403892b387c1622656ff3a242044b890fe4ea0cd1e66dd52653e1"
    assert verifier["release"]["receipt"]["sha256"] == "c09148927767855e6694e246ae38a9bdda4181086d18f78c204999648ec1089c"
    assert verifier["release"]["source_commit"] == "1ca6ed95195d44097057d7165dc5dc0730cdf1c0"
    assert verifier["release"]["wheel"] == {
        "bytes": 334648, "sha256": "89998d9e41dcc90b8768ac036bf480e3501138d715824e12f928ab15f75dfbb7",
    }
    assert verifier["acquisition"] == {
        "visibility": "private", "prepared_by": "hub", "implicit_pull": False,
        "public_web_contains_provider_package": False,
    }


@unittest.skipUnless(importlib.util.find_spec("mcp"), "Optional MCP SDK required; installed in the Python CI lanes")
class PracticeResourceProtocolTests(unittest.TestCase):
    def test_practice_resources_read_over_real_stdio_after_initialize_and_list(self):
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

        factory = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory(prefix="unaltraweb-resource-protocol-") as temporary, \
                tempfile.TemporaryFile(mode="w+", encoding="utf-8") as errors:
            project = Path(temporary)
            params = StdioServerParameters(
                command=sys.executable,
                args=["-B", "-m", "unaltraweb_mcp.cli", "--project", str(project), "mcp", "serve"],
                cwd=str(project),
                env={"PYTHONPATH": str(factory / "src"), "PYTHONDONTWRITEBYTECODE": "1",
                     "UNALTRAWEB_FACTORY_DIR": str(factory), "HOME": str(project),
                     "PATH": str(project / "no-executables")},
            )

            async def roundtrip():
                async with stdio_client(params, errlog=errors) as (incoming, outgoing):
                    async with ClientSession(incoming, outgoing) as session:
                        initialized = await session.initialize()
                        self.assertIsNotNone(initialized.capabilities.resources)
                        await assert_practice_resources(session)

            try:
                asyncio.run(asyncio.wait_for(roundtrip(), timeout=45))
            except Exception:
                errors.seek(0)
                self.fail("Real MCP resources/read failed:\n" + errors.read(65536))


if __name__ == "__main__":
    unittest.main()
