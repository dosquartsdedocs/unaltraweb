#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests
import yaml

try:
    import bibtexparser
    from bibtexparser.bparser import BibTexParser
    from bibtexparser.bwriter import BibTexWriter
    from bibtexparser.customization import convert_to_unicode
except Exception as exc:  # pragma: no cover - runtime guard
    print("Missing dependency 'bibtexparser'. Install dependencies first:", file=sys.stderr)
    print("  python3 -m venv .venv && .venv/bin/pip install -r requirements.txt", file=sys.stderr)
    print(f"Details: {exc}", file=sys.stderr)
    sys.exit(1)

from metrics_common import SummaryContext, as_bool, as_float, as_int, compact_categories, compute_summary, fmt_float


X_FIELDS = [
    "x_openalex_id",
    "x_openalex_cited_by",
    "x_crossref_cited_by",
    "x_gs_id",
    "x_gs_cited_by",
    "x_openalex_fwci",
    "x_openalex_citation_normalized_percentile",
    "x_openalex_topic",
    "x_openalex_subfield",
    "x_openalex_field",
    "x_openalex_domain",
    "x_openalex_funders",
    "x_openalex_source_display_name",
    "x_openalex_source_works_count",
    "x_openalex_source_cited_by_count",
    "x_openalex_source_is_oa",
    "x_openalex_source_is_core",
    "x_openalex_source_is_in_doaj",
    "x_openalex_source_h_index",
    "x_openalex_source_i10_index",
    "x_openalex_source_2yr_mean_citedness",
    "x_openalex_cited_by_2y",
    "x_openalex_cited_by_5y",
    "x_scimago_sjr",
    "x_scimago_quartile",
    "x_scimago_year",
    "x_scimago_categories",
    "x_scimago_h_index",
    "x_scimago_cites_per_doc_2y",
    "x_scimago_total_docs_3y",
    "x_scimago_total_cites_3y",
    "x_scimago_country",
    "x_scimago_type",
    "x_scimago_coverage",
    "x_metrics_updated",
    "note",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Update bibliography with bibliometric metrics.")
    parser.add_argument(
        "--bib",
        action="append",
        default=[],
        help="BibTeX file path (can be repeated). Defaults to all _bibliography/*.bib",
    )
    parser.add_argument("--overrides", default="_data/metrics-overrides.yml", help="Overrides YAML path")
    parser.add_argument("--citations-data", default="_data/citations.yml", help="Google Scholar citations YAML path")
    parser.add_argument("--scimago-csv", default=".cache/scimago/scimagojr.csv", help="Local Scimago CSV path")
    parser.add_argument("--metrics-out", default="_data/metrics.yml", help="Aggregated metrics YAML output")
    parser.add_argument("--report-json", default="tmp/metrics-report.json", help="Diagnostics JSON output")
    parser.add_argument("--unmatched-tsv", default="tmp/metrics-unmatched.tsv", help="Diagnostics TSV output")
    parser.add_argument("--max-year-gap", type=int, default=2, help="Max gap between publication year and Scimago year")
    parser.add_argument("--offline", action="store_true", help="Do not call OpenAlex/Crossref")
    parser.add_argument("--dry-run", action="store_true", help="Do not rewrite BibTeX files")
    parser.add_argument(
        "--validate-scimago",
        default="",
        help="Only validate a Scimago CSV file and exit (path argument)",
    )
    return parser.parse_args()


def normalize_doi(value: str | None) -> str | None:
    if not value:
        return None
    doi = value.strip()
    doi = doi.replace("https://doi.org/", "").replace("http://doi.org/", "")
    doi = doi.replace("doi:", "").strip()
    return doi.lower() if doi else None


def normalize_issn_token(value: str) -> str | None:
    token = re.sub(r"[^0-9xX]", "", value or "")
    if len(token) != 8:
        return None
    return f"{token[:4]}-{token[4:].upper()}"


def normalize_issn_list(raw_value: str | None) -> list[str]:
    if not raw_value:
        return []
    items = re.split(r"[;,|\s]+", raw_value)
    normalized = []
    seen = set()
    for item in items:
        issn = normalize_issn_token(item)
        if issn and issn not in seen:
            seen.add(issn)
            normalized.append(issn)
    return normalized


def load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def find_bib_files(cli_bib_args: list[str]) -> list[Path]:
    if cli_bib_args:
        return [Path(p) for p in cli_bib_args]
    return sorted(Path("_bibliography").glob("*.bib"))


def split_bib_front_matter(content: str) -> tuple[str, str]:
    match = re.search(r"@\w+\s*\{", content)
    if not match:
        return content, ""
    return content[: match.start()], content[match.start() :]


def parse_bib_database(path: Path) -> tuple[str, Any]:
    content = path.read_text(encoding="utf-8")
    prefix, bib_body = split_bib_front_matter(content)

    parser = BibTexParser(common_strings=True)
    parser.ignore_nonstandard_types = False
    parser.homogenize_fields = False
    parser.customization = convert_to_unicode
    db = bibtexparser.loads(bib_body, parser=parser) if bib_body.strip() else bibtexparser.bibdatabase.BibDatabase()
    return prefix, db


def write_bib_database(path: Path, prefix: str, db: Any) -> None:
    writer = BibTexWriter()
    writer.indent = "  "
    writer.comma_first = False
    writer.display_order = []
    writer.order_entries_by = ("ID",)
    rendered = bibtexparser.dumps(db, writer)
    path.write_text(f"{prefix}{rendered}", encoding="utf-8")


def parse_float_text(value: str | None) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    text = text.replace(" ", "")
    if text.count(",") == 1 and text.count(".") == 0:
        text = text.replace(",", ".")
    elif text.count(",") > 1 and text.count(".") == 0:
        text = text.replace(".", "").replace(",", ".")
    else:
        text = text.replace(",", "")
    try:
        return float(text)
    except ValueError:
        return None


def parse_int_text(value: str | None) -> int | None:
    if value is None:
        return None
    text = str(value).strip().replace(" ", "")
    if not text:
        return None
    if re.fullmatch(r"-?\d+(?:\.\d+)?", text):
        try:
            return int(float(text))
        except ValueError:
            return None
    token = re.sub(r"[^0-9-]", "", text)
    if not token:
        return None
    try:
        return int(token)
    except ValueError:
        return None


def normalize_column_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (name or "").lower())


def detect_scimago_columns(fieldnames: list[str]) -> dict[str, str]:
    normalized = {normalize_column_name(name): name for name in fieldnames if name}

    def pick(*candidates: str) -> str | None:
        for candidate in candidates:
            if candidate in normalized:
                return normalized[candidate]
        return None

    columns = {
        "title": pick("title", "sourcetitle", "journaltitle"),
        "issn": pick("issn", "issns", "issncode", "issnprint"),
        "year": pick("year", "rankyear"),
        "sjr": pick("sjr", "sjrindex"),
        "quartile": pick("sjrbestquartile", "bestquartile", "quartile"),
        "categories": pick("categories", "category", "subjectareaandcategory"),
        "h_index": pick("hindex", "hindexscore"),
        "cites_per_doc_2y": pick("citesdoc2years", "citesdoc2year", "citesdoc2y", "citesperdoc2years", "citesperdoc2year"),
        "total_docs_3y": pick("totaldocs3years", "totaldocs3year"),
        "total_cites_3y": pick("totalcites3years", "totalcites3year"),
        "country": pick("country", "sourcecountry"),
        "type": pick("type", "sourcetype"),
        "coverage": pick("coverage"),
    }
    return columns


def load_scimago(path: Path) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    if not path.exists():
        return {}, {"available": False, "message": f"missing: {path}"}

    sample = path.read_text(encoding="utf-8", errors="ignore")[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=";,\t,")
        delimiter = dialect.delimiter
    except csv.Error:
        delimiter = ";"

    with path.open("r", encoding="utf-8", errors="ignore", newline="") as handle:
        reader = csv.DictReader(handle, delimiter=delimiter)
        fieldnames = reader.fieldnames or []
        columns = detect_scimago_columns(fieldnames)

        if not columns["issn"] or not columns["year"] or not columns["sjr"]:
            raise ValueError(
                "Scimago CSV missing required columns. Required: ISSN, Year, SJR. "
                f"Detected headers: {fieldnames}"
            )

        index: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in reader:
            issns = normalize_issn_list(row.get(columns["issn"], ""))
            if not issns:
                continue

            year = parse_int_text(row.get(columns["year"]))
            sjr = parse_float_text(row.get(columns["sjr"]))
            quartile = (row.get(columns["quartile"]) or "").strip().upper() if columns["quartile"] else ""
            categories = (row.get(columns["categories"]) or "").strip() if columns["categories"] else ""
            title = (row.get(columns["title"]) or "").strip() if columns["title"] else ""
            h_index = parse_int_text(row.get(columns["h_index"])) if columns["h_index"] else None
            cites_per_doc_2y = parse_float_text(row.get(columns["cites_per_doc_2y"])) if columns["cites_per_doc_2y"] else None
            total_docs_3y = parse_int_text(row.get(columns["total_docs_3y"])) if columns["total_docs_3y"] else None
            total_cites_3y = parse_int_text(row.get(columns["total_cites_3y"])) if columns["total_cites_3y"] else None
            country = (row.get(columns["country"]) or "").strip() if columns["country"] else ""
            source_type = (row.get(columns["type"]) or "").strip() if columns["type"] else ""
            coverage = (row.get(columns["coverage"]) or "").strip() if columns["coverage"] else ""

            payload = {
                "title": title,
                "year": year,
                "sjr": sjr,
                "quartile": quartile if quartile in {"Q1", "Q2", "Q3", "Q4"} else "",
                "categories": categories,
                "h_index": h_index,
                "cites_per_doc_2y": cites_per_doc_2y,
                "total_docs_3y": total_docs_3y,
                "total_cites_3y": total_cites_3y,
                "country": country,
                "type": source_type,
                "coverage": coverage,
            }
            for issn in issns:
                index[issn].append(payload)

    return index, {"available": True, "path": str(path), "records": sum(len(v) for v in index.values())}


def validate_scimago_file(path: Path) -> None:
    try:
        _, meta = load_scimago(path)
        if not meta.get("available"):
            raise ValueError(meta.get("message", "Scimago file unavailable"))
        print(f"Scimago CSV validated: {path}")
    except Exception as exc:
        print(f"Scimago CSV validation failed: {exc}", file=sys.stderr)
        sys.exit(1)


class MetricsClient:
    def __init__(self, offline: bool, email: str = "") -> None:
        self.offline = offline
        ua = "unaltraweb-biblio-metrics/1.0"
        if email:
            ua += f" (mailto:{email})"
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": ua})

        self.oa_work_cache: dict[str, dict[str, Any] | None] = {}
        self.oa_source_cache: dict[str, dict[str, Any] | None] = {}
        self.crossref_cache: dict[str, dict[str, Any] | None] = {}

    def _get_json(self, url: str) -> dict[str, Any] | None:
        if self.offline:
            return None
        try:
            response = self.session.get(url, timeout=30)
            if response.status_code == 404:
                return None
            response.raise_for_status()
            return response.json()
        except requests.RequestException:
            return None

    def get_openalex_work(self, doi: str | None = None, openalex_id: str | None = None) -> dict[str, Any] | None:
        if openalex_id:
            key = f"id:{openalex_id}"
            if key not in self.oa_work_cache:
                api_id = openalex_id.split("/")[-1] if openalex_id.startswith("http") else openalex_id
                self.oa_work_cache[key] = self._get_json(f"https://api.openalex.org/works/{api_id}")
            return self.oa_work_cache[key]

        if doi:
            key = f"doi:{doi}"
            if key not in self.oa_work_cache:
                self.oa_work_cache[key] = self._get_json(f"https://api.openalex.org/works/https://doi.org/{doi}")
            return self.oa_work_cache[key]
        return None

    def get_openalex_source(self, source_id: str | None) -> dict[str, Any] | None:
        if not source_id:
            return None
        sid = source_id.split("/")[-1]
        if sid not in self.oa_source_cache:
            self.oa_source_cache[sid] = self._get_json(f"https://api.openalex.org/sources/{sid}")
        return self.oa_source_cache[sid]

    def get_crossref_work(self, doi: str | None) -> dict[str, Any] | None:
        if not doi:
            return None
        if doi not in self.crossref_cache:
            payload = self._get_json(f"https://api.crossref.org/works/{doi}")
            self.crossref_cache[doi] = payload.get("message") if payload and "message" in payload else payload
        return self.crossref_cache[doi]


def choose_scimago_record(candidates: list[dict[str, Any]], publication_year: int | None, max_year_gap: int) -> tuple[dict[str, Any] | None, str]:
    if not candidates:
        return None, "no-issn-match"

    if publication_year is None:
        sorted_by_year = sorted(
            [c for c in candidates if c.get("year") is not None], key=lambda item: item["year"], reverse=True
        )
        return (sorted_by_year[0], "matched") if sorted_by_year else (candidates[0], "matched")

    ranked: list[tuple[Any, dict[str, Any]]] = []
    for candidate in candidates:
        year = candidate.get("year")
        if year is None:
            continue
        gap = abs(publication_year - year)
        bias = 0 if year <= publication_year else 1
        tie = -year if year <= publication_year else year
        ranked.append(((gap, bias, tie), candidate))

    if not ranked:
        return None, "no-year-in-scimago"

    ranked.sort(key=lambda item: item[0])
    best = ranked[0][1]
    best_gap = abs(publication_year - best["year"])

    if best_gap > max_year_gap:
        return None, "stale-rejected"
    return best, "matched"


def parse_counts_by_year(work: dict[str, Any]) -> tuple[int | None, int | None]:
    counts = work.get("counts_by_year") or []
    now = datetime.now(timezone.utc).year
    total_2y = 0
    total_5y = 0
    found_any = False

    for row in counts:
        year = as_int(row.get("year"))
        cited = as_int(row.get("cited_by_count")) or 0
        if year is None:
            continue
        found_any = True
        if year >= now - 1:
            total_2y += cited
        if year >= now - 4:
            total_5y += cited

    if not found_any:
        return None, None
    return total_2y, total_5y


def set_field(entry: dict[str, Any], field: str, value: Any) -> None:
    if value is None:
        return
    if isinstance(value, bool):
        entry[field] = "true" if value else "false"
    elif isinstance(value, float):
        entry[field] = fmt_float(value, digits=4)
    else:
        entry[field] = str(value)


def build_metrics_note(entry: dict[str, Any], original_note: str) -> str | None:
    blocks: list[str] = []

    oa = as_int(entry.get("x_openalex_cited_by"))
    cr = as_int(entry.get("x_crossref_cited_by"))
    gs = as_int(entry.get("x_gs_cited_by"))
    cites = []
    if oa is not None and oa > 0:
        cites.append(f"OA: {oa}")
    if cr is not None and cr > 0:
        cites.append(f"CR: {cr}")
    if gs is not None and gs > 0:
        cites.append(f"GS: {gs}")
    if cites:
        blocks.append("Cites: " + " / ".join(cites))

    fwci = as_float(entry.get("x_openalex_fwci"))
    if fwci is not None:
        blocks.append(f"FWCI: {fmt_float(fwci, 2)}")

    cnp = as_float(entry.get("x_openalex_citation_normalized_percentile"))
    if cnp is not None:
        blocks.append(f"CNP: {fmt_float(cnp, 2)}")

    core = as_bool(entry.get("x_openalex_source_is_core"))
    if core is not None:
        blocks.append(f"Core {'yes' if core else 'no'}")

    doaj = as_bool(entry.get("x_openalex_source_is_in_doaj"))
    if doaj is not None:
        blocks.append(f"DOAJ {'yes' if doaj else 'no'}")

    q = str(entry.get("x_scimago_quartile", "")).strip().upper()
    sjr = as_float(entry.get("x_scimago_sjr"))
    sc_year = as_int(entry.get("x_scimago_year"))
    categories = compact_categories(entry.get("x_scimago_categories"))
    if q or sjr is not None or sc_year is not None or categories:
        sc_parts = []
        if q:
            sc_parts.append(q)
        if sjr is not None:
            sc_parts.append(f"SJR: {fmt_float(sjr, 3)}")
        if sc_year is not None:
            sc_parts.append(str(sc_year))
        if categories:
            sc_parts.append(categories)
        blocks.append("Scimago: " + ", ".join(sc_parts))

    if not blocks and not original_note:
        return None

    note = "Metrics: " + " | ".join(blocks) if blocks else ""
    if original_note and not original_note.startswith("Metrics:"):
        note = f"{note} | {original_note}" if note else original_note
    return note


def main() -> None:
    args = parse_args()

    if args.validate_scimago:
        validate_scimago_file(Path(args.validate_scimago))
        return

    bib_files = find_bib_files(args.bib)
    if not bib_files:
        print("No BibTeX files found.", file=sys.stderr)
        sys.exit(1)

    overrides_data = load_yaml(Path(args.overrides))
    overrides_entries = overrides_data.get("entries", overrides_data)
    overrides_defaults = overrides_data.get("defaults", {}) if isinstance(overrides_data, dict) else {}

    max_year_gap = int(overrides_defaults.get("max_year_gap", args.max_year_gap))
    contact_email = str(overrides_defaults.get("mailto", "")).strip()

    citations_data = load_yaml(Path(args.citations_data))
    scholar_map = citations_data.get("papers", {}) if isinstance(citations_data, dict) else {}

    scimago_index, scimago_meta = load_scimago(Path(args.scimago_csv))

    client = MetricsClient(offline=args.offline, email=contact_email)

    updated_on = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    stale_rejected_count = 0
    report_entries: list[dict[str, Any]] = []
    unmatched_rows: list[dict[str, Any]] = []

    for bib_path in bib_files:
        if not bib_path.exists():
            print(f"Skipping missing BibTeX file: {bib_path}", file=sys.stderr)
            continue

        prefix, db = parse_bib_database(bib_path)

        for entry in db.entries:
            key = entry.get("ID", "")
            entry_type = entry.get("ENTRYTYPE", "")
            override = overrides_entries.get(key, {}) if isinstance(overrides_entries, dict) else {}

            doi = normalize_doi(entry.get("doi"))
            year = as_int(entry.get("year"))
            original_note = str(entry.get("note", "")).strip()

            status = {
                "openalex": "skipped",
                "crossref": "skipped",
                "scimago": "skipped",
                "google_scholar": "skipped",
            }

            # Google Scholar compatibility bridge
            gs_id = override.get("x_gs_id") or override.get("gs_id") or entry.get("x_gs_id") or entry.get("google_scholar_id")
            gs_cited = (
                override.get("x_gs_cited_by")
                or override.get("gs_cited_by")
                or entry.get("x_gs_cited_by")
                or entry.get("google_scholar_citations")
            )

            if gs_id:
                set_field(entry, "x_gs_id", gs_id)
                status["google_scholar"] = "matched"
            if gs_cited is None and gs_id:
                scholar_key = str(gs_id).replace("cites:", "")
                scholar_hit = None
                for k, v in scholar_map.items():
                    if scholar_key and scholar_key in str(k):
                        scholar_hit = v
                        break
                if isinstance(scholar_hit, dict):
                    gs_cited = scholar_hit.get("citations")
            if gs_cited is not None:
                set_field(entry, "x_gs_cited_by", as_int(gs_cited))
                status["google_scholar"] = "matched"

            # OpenAlex
            oa_override_id = override.get("x_openalex_id") or override.get("openalex_id")
            work = client.get_openalex_work(doi=doi, openalex_id=oa_override_id)
            if work:
                status["openalex"] = "matched"
                set_field(entry, "x_openalex_id", work.get("id"))
                set_field(entry, "x_openalex_cited_by", as_int(work.get("cited_by_count")))
                set_field(entry, "x_openalex_fwci", as_float(work.get("fwci")))

                cnp_raw = (work.get("citation_normalized_percentile") or {}).get("value")
                cnp = as_float(cnp_raw)
                if cnp is not None:
                    set_field(entry, "x_openalex_citation_normalized_percentile", cnp * 100)

                primary_topic = work.get("primary_topic") or {}
                if isinstance(primary_topic, dict):
                    subfield = primary_topic.get("subfield")
                    field = primary_topic.get("field")
                    domain = primary_topic.get("domain")
                    subfield_name = subfield.get("display_name") if isinstance(subfield, dict) else ""
                    field_name = field.get("display_name") if isinstance(field, dict) else ""
                    domain_name = domain.get("display_name") if isinstance(domain, dict) else ""
                    set_field(entry, "x_openalex_topic", str(primary_topic.get("display_name") or "").strip())
                    set_field(entry, "x_openalex_subfield", str(subfield_name or "").strip())
                    set_field(entry, "x_openalex_field", str(field_name or "").strip())
                    set_field(entry, "x_openalex_domain", str(domain_name or "").strip())
                else:
                    set_field(entry, "x_openalex_topic", "")
                    set_field(entry, "x_openalex_subfield", "")
                    set_field(entry, "x_openalex_field", "")
                    set_field(entry, "x_openalex_domain", "")

                funders: list[str] = []
                seen_funders: set[str] = set()
                for grant in (work.get("grants") or []):
                    if not isinstance(grant, dict):
                        continue
                    funder_name = str(grant.get("funder_display_name") or "").strip()
                    if not funder_name:
                        funder = grant.get("funder")
                        if isinstance(funder, dict):
                            funder_name = str(funder.get("display_name") or "").strip()
                    if not funder_name:
                        continue
                    canonical = funder_name.lower()
                    if canonical in seen_funders:
                        continue
                    seen_funders.add(canonical)
                    funders.append(funder_name)
                set_field(entry, "x_openalex_funders", "; ".join(funders))

                cited_2y, cited_5y = parse_counts_by_year(work)
                set_field(entry, "x_openalex_cited_by_2y", cited_2y)
                set_field(entry, "x_openalex_cited_by_5y", cited_5y)

                source = (work.get("primary_location") or {}).get("source") or {}
                source_id = source.get("id")
                if source_id:
                    set_field(entry, "x_openalex_source_id", source_id)
                source_full = client.get_openalex_source(source_id)
                source_payload = source_full or source
                set_field(entry, "x_openalex_source_display_name", str(source_payload.get("display_name") or "").strip())
                set_field(entry, "x_openalex_source_works_count", as_int(source_payload.get("works_count")))
                set_field(entry, "x_openalex_source_cited_by_count", as_int(source_payload.get("cited_by_count")))
                set_field(entry, "x_openalex_source_is_oa", as_bool(source_payload.get("is_oa")))
                set_field(entry, "x_openalex_source_is_core", as_bool(source_payload.get("is_core")))
                set_field(entry, "x_openalex_source_is_in_doaj", as_bool(source_payload.get("is_in_doaj")))
                summary_stats = source_payload.get("summary_stats") or {}
                set_field(entry, "x_openalex_source_h_index", as_int(summary_stats.get("h_index")))
                set_field(entry, "x_openalex_source_i10_index", as_int(summary_stats.get("i10_index")))
                set_field(entry, "x_openalex_source_2yr_mean_citedness", as_float(summary_stats.get("2yr_mean_citedness")))
            else:
                status["openalex"] = "not-found" if doi or oa_override_id else "no-doi"

            # Crossref
            cr_override = override.get("x_crossref_cited_by") or override.get("crossref_cited_by")
            if cr_override is not None:
                set_field(entry, "x_crossref_cited_by", as_int(cr_override))
                status["crossref"] = "matched"
            else:
                crossref_work = client.get_crossref_work(doi)
                if crossref_work:
                    set_field(entry, "x_crossref_cited_by", as_int(crossref_work.get("is-referenced-by-count")))
                    status["crossref"] = "matched"
                else:
                    status["crossref"] = "not-found" if doi else "no-doi"

            # Scimago (articles only)
            if str(entry_type).lower() == "article":
                issns = []
                for field_name in ("issn", "eissn"):
                    issns.extend(normalize_issn_list(entry.get(field_name)))
                unique_issns = sorted(set(issns))

                candidates: list[dict[str, Any]] = []
                for issn in unique_issns:
                    candidates.extend(scimago_index.get(issn, []))

                chosen, sc_status = choose_scimago_record(candidates, year, max_year_gap)
                status["scimago"] = sc_status if scimago_meta.get("available") else "scimago-missing"

                if sc_status == "stale-rejected":
                    stale_rejected_count += 1

                if chosen:
                    set_field(entry, "x_scimago_sjr", chosen.get("sjr"))
                    set_field(entry, "x_scimago_quartile", chosen.get("quartile"))
                    set_field(entry, "x_scimago_year", chosen.get("year"))
                    set_field(entry, "x_scimago_categories", chosen.get("categories"))
                    set_field(entry, "x_scimago_h_index", chosen.get("h_index"))
                    set_field(entry, "x_scimago_cites_per_doc_2y", chosen.get("cites_per_doc_2y"))
                    set_field(entry, "x_scimago_total_docs_3y", chosen.get("total_docs_3y"))
                    set_field(entry, "x_scimago_total_cites_3y", chosen.get("total_cites_3y"))
                    set_field(entry, "x_scimago_country", chosen.get("country"))
                    set_field(entry, "x_scimago_type", chosen.get("type"))
                    set_field(entry, "x_scimago_coverage", chosen.get("coverage"))
            else:
                status["scimago"] = "not-article"

            set_field(entry, "x_metrics_updated", updated_on)

            note = build_metrics_note(entry, original_note)
            if note:
                entry["note"] = note

            snapshot = {
                "key": key,
                "type": entry_type,
                "title": entry.get("title", ""),
                "doi": doi,
                "status": status,
            }
            for field in X_FIELDS:
                if field in entry:
                    snapshot[field] = entry[field]
            report_entries.append(snapshot)

            if any(value not in {"matched", "not-article", "skipped"} for value in status.values()):
                unmatched_rows.append(
                    {
                        "key": key,
                        "type": entry_type,
                        "title": entry.get("title", ""),
                        "doi": doi or "",
                        "openalex_status": status["openalex"],
                        "crossref_status": status["crossref"],
                        "scimago_status": status["scimago"],
                        "google_scholar_status": status["google_scholar"],
                    }
                )

        if not args.dry_run:
            write_bib_database(bib_path, prefix, db)

    summary = compute_summary(report_entries, SummaryContext(max_year_gap=max_year_gap, stale_rejected=stale_rejected_count))

    metrics_payload = {
        "metrics": {
            "updated_on": updated_on,
            "sources": {
                "openalex": "api" if not args.offline else "offline",
                "crossref": "api" if not args.offline else "offline",
                "google_scholar": "bibtex + _data/citations.yml",
                "scimago": str(scimago_meta.get("path", args.scimago_csv)) if scimago_meta.get("available") else "missing",
            },
            "summary": summary,
        }
    }

    metrics_out = Path(args.metrics_out)
    metrics_out.parent.mkdir(parents=True, exist_ok=True)
    metrics_out.write_text(yaml.safe_dump(metrics_payload, sort_keys=False, allow_unicode=True), encoding="utf-8")

    report_out = Path(args.report_json)
    report_out.parent.mkdir(parents=True, exist_ok=True)
    report_out.write_text(
        json.dumps(
            {
                "generated_on": updated_on,
                "scimago": scimago_meta,
                "max_year_gap": max_year_gap,
                "entries": report_entries,
                "summary": summary,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    unmatched_out = Path(args.unmatched_tsv)
    unmatched_out.parent.mkdir(parents=True, exist_ok=True)
    with unmatched_out.open("w", encoding="utf-8", newline="") as handle:
        fieldnames = [
            "key",
            "type",
            "title",
            "doi",
            "openalex_status",
            "crossref_status",
            "scimago_status",
            "google_scholar_status",
        ]
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        writer.writerows(unmatched_rows)

    print(f"Metrics updated on {updated_on}")
    print(f"- Metrics summary: {metrics_out}")
    print(f"- Diagnostics JSON: {report_out}")
    print(f"- Unmatched TSV: {unmatched_out}")


if __name__ == "__main__":
    main()
