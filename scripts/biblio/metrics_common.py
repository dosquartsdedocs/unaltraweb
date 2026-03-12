#!/usr/bin/env python3

from __future__ import annotations

from dataclasses import dataclass
from statistics import fmean
from typing import Any


def as_int(value: Any) -> int | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    text = text.replace(",", "").replace(".", "") if text.isdigit() is False else text
    try:
        return int(float(text))
    except (TypeError, ValueError):
        return None


def as_float(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    text = text.replace(",", ".")
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def as_bool(value: Any) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"true", "yes", "1", "y"}:
        return True
    if text in {"false", "no", "0", "n"}:
        return False
    return None


def fmt_float(value: float | None, digits: int = 4) -> str | None:
    if value is None:
        return None
    text = f"{value:.{digits}f}".rstrip("0").rstrip(".")
    return text if text else "0"


def compact_categories(categories: str | None, max_items: int = 2) -> str | None:
    if not categories:
        return None
    chunks = [c.strip() for c in categories.replace("|", ";").split(";") if c.strip()]
    if not chunks:
        return None
    if len(chunks) <= max_items:
        return ", ".join(chunks)
    return ", ".join(chunks[:max_items]) + f" (+{len(chunks) - max_items})"


@dataclass
class SummaryContext:
    max_year_gap: int
    stale_rejected: int


def compute_summary(entries: list[dict[str, Any]], context: SummaryContext) -> dict[str, Any]:
    article_entries = [e for e in entries if str(e.get("type", "")).lower() == "article"]

    articles_with_metrics = 0
    openalex_citations_total = 0
    crossref_citations_total = 0
    google_scholar_citations_total = 0
    openalex_citations_2y_total = 0
    openalex_citations_5y_total = 0

    fwci_values: list[float] = []
    cnp_values: list[float] = []

    core_sources: set[str] = set()
    doaj_sources: set[str] = set()

    scimago_articles_count = 0
    scimago_q = {"Q1": 0, "Q2": 0, "Q3": 0, "Q4": 0}
    scimago_years: list[int] = []

    for entry in entries:
      oa = as_int(entry.get("x_openalex_cited_by"))
      cr = as_int(entry.get("x_crossref_cited_by"))
      gs = as_int(entry.get("x_gs_cited_by"))
      oa2 = as_int(entry.get("x_openalex_cited_by_2y"))
      oa5 = as_int(entry.get("x_openalex_cited_by_5y"))

      if any(v is not None for v in (oa, cr, gs)):
          if str(entry.get("type", "")).lower() == "article":
              articles_with_metrics += 1

      openalex_citations_total += oa or 0
      crossref_citations_total += cr or 0
      google_scholar_citations_total += gs or 0
      openalex_citations_2y_total += oa2 or 0
      openalex_citations_5y_total += oa5 or 0

      fwci = as_float(entry.get("x_openalex_fwci"))
      if fwci is not None:
          fwci_values.append(fwci)

      cnp = as_float(entry.get("x_openalex_citation_normalized_percentile"))
      if cnp is not None:
          cnp_values.append(cnp)

      source_id = str(entry.get("x_openalex_source_id", "")).strip()
      if source_id:
          if as_bool(entry.get("x_openalex_source_is_core")) is True:
              core_sources.add(source_id)
          if as_bool(entry.get("x_openalex_source_is_in_doaj")) is True:
              doaj_sources.add(source_id)

      if str(entry.get("type", "")).lower() == "article":
          q = str(entry.get("x_scimago_quartile", "")).strip().upper()
          if q in scimago_q:
              scimago_articles_count += 1
              scimago_q[q] += 1
              y = as_int(entry.get("x_scimago_year"))
              if y is not None:
                  scimago_years.append(y)

    return {
        "articles_with_metrics": articles_with_metrics,
        "openalex_citations_total": openalex_citations_total,
        "crossref_citations_total": crossref_citations_total,
        "google_scholar_citations_total": google_scholar_citations_total,
        "openalex_citations_2y_total": openalex_citations_2y_total,
        "openalex_citations_5y_total": openalex_citations_5y_total,
        "fwci_avg": round(fmean(fwci_values), 4) if fwci_values else 0,
        "cnp_avg": round(fmean(cnp_values), 4) if cnp_values else 0,
        "journals_core_count": len(core_sources),
        "journals_doaj_count": len(doaj_sources),
        "scimago_articles_count": scimago_articles_count,
        "scimago_q1_count": scimago_q["Q1"],
        "scimago_q2_count": scimago_q["Q2"],
        "scimago_q3_count": scimago_q["Q3"],
        "scimago_q4_count": scimago_q["Q4"],
        "scimago_stale_rejected": context.stale_rejected,
        "scimago_max_year_gap": context.max_year_gap,
        "scimago_year_min": min(scimago_years) if scimago_years else None,
        "scimago_year_max": max(scimago_years) if scimago_years else None,
    }
