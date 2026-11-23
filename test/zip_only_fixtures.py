"""Synthetic original student/teacher ZIPs, with PDFs already embedded."""
import copy

from retained_manifest_fixtures import file_root_readings
from unaltraweb_mcp import artifact_publication as publication


def zip_only_intake(case):
    packages, sources = copy.deepcopy(case.request["packages"]), copy.deepcopy(case.request["sources"])
    file_root_readings(case)
    case.request["packages"], case.request["sources"] = packages, sources
    for item in packages:
        item["selected"] = [{"id": item["recipient"] + "-packet", "format": "zip"}]
    case.refresh()


def flat_routes(case, admitted):
    config, _ = case.routes(admitted)
    config["schema_version"] = 3
    config["publication"]["targets"]["s4"]["prefix"] = "practiques/ca"
    for route in config["artifacts"].values():
        route["delivery_layout"] = "files-v1"
    case.write(publication.CONFIG, publication.canonical(config))
    return config, case.pin(publication.CONFIG)["sha256"]
