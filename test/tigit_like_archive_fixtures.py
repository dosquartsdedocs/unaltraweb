"""Synthetic existing public student download: three files, seven empty dirs."""
import io
import zipfile

from unaltraweb_mcp import artifact_publication as pub


def public_student_download(f):
    workbook = io.BytesIO()
    with zipfile.ZipFile(workbook, "w") as archive:
        archive.writestr("xl/workbook.xml", '<workbook><sheets>' + ''.join(f'<sheet name="Synthetic{i}" sheetId="{i}"/>' for i in range(1, 14)) + '</sheets></workbook>')
        for index in range(1, 14):
            archive.writestr(f"xl/worksheets/sheet{index}.xml", '<worksheet><sheetData/></worksheet>')
    f.members = {"README.md": b"SYNTHETIC existing student download; original role known, language/approval unknown.\n",
                 "materials/README.md": b"Original synthetic workbook supplied as bytes; no formulas/recalculation/native qualification.\n",
                 "starter.xlsx": workbook.getvalue()}
    data = io.BytesIO()
    with zipfile.ZipFile(data, "w") as archive:
        for index in range(1, 8):
            archive.writestr(f"empty-{index}/", b"")
        for name, raw in f.members.items():
            archive.writestr(name, raw)
    f.path = "assets/downloads/course-starter-student.zip"
    f.write(f.path, data.getvalue())
    f.write("_config.yml", pub.canonical({"lang": "ca", "languages": ["ca"], "exclude": ["practiques/", "sandbox/", "dist/"],
        "include": ["assets/downloads"], "unaltraweb": {"site_profile": "unaltremanual"}}))
    f.request["archive"] = f.pin(f.path)
    f.request["classification"].update(role="student", language="unknown", full_offline="unknown")
    f.request.update(evidence=[], member_references=[], checksums=[])
    f.save()
