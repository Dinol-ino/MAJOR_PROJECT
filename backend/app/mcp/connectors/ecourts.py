"""eCourtsIndia partner API connector (case metadata search).

External source: results are labelled as such and never treated as the user's evidence. The
API key is read from the environment only. Outbound queries are PII-scrubbed and must pass
the allowlist in legal_sources.yaml; the MCP policy engine additionally requires ONLINE mode.
"""
import os
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

import httpx

DEFAULT_BASE_URL = "https://webapi.ecourtsindia.com"
SOURCE_LABEL = "eCourtsIndia (external source, case metadata; verify against the official order)"

# Test seam: tests inject an httpx.MockTransport here; production leaves it None.
_transport: Optional[httpx.BaseTransport] = None


def _base_url() -> str:
    return os.getenv("ECOURTSINDIA_BASE_URL", DEFAULT_BASE_URL).rstrip("/")


def configured() -> bool:
    return bool(os.getenv("ECOURTSINDIA_API_KEY"))


def _title(r: Dict[str, Any]) -> str:
    pet = ", ".join(r.get("petitioners") or [])[:120]
    res = ", ".join(r.get("respondents") or [])[:120]
    return f"{pet} v. {res}".strip(" v.") if (pet or res) else str(r.get("cnr", ""))


def search_cases(query: str, max_cases: int = 3, state_code: Optional[str] = None) -> Dict[str, Any]:
    key = os.getenv("ECOURTSINDIA_API_KEY")
    if not key:
        raise RuntimeError("eCourtsIndia is not configured (ECOURTSINDIA_API_KEY is empty); nothing was retrieved.")

    from app.network.mode_enforcer import mode_enforcer
    from app.security.pii_scanner import PIIScanner

    clean_query = PIIScanner().scan_and_redact(query)[:300]
    params = {"query": clean_query, "page": 1, "pageSize": max(1, min(int(max_cases), 5))}
    if state_code:
        params["stateCode"] = state_code
    url = f"{_base_url()}/api/partner/search?{urlencode(params)}"
    mode_enforcer.validate_outbound_url(url)  # allowlist + offline check; raises when blocked

    with httpx.Client(verify=True, timeout=15.0, follow_redirects=False, transport=_transport) as client:
        resp = client.get(url, headers={"Authorization": f"Bearer {key}", "Accept": "application/json"})
    if resp.status_code in (401, 403):
        raise RuntimeError("eCourtsIndia rejected the API key; check ECOURTSINDIA_API_KEY.")
    if resp.status_code == 402 or resp.status_code == 429:
        raise RuntimeError("eCourtsIndia credit or rate limit reached; nothing was retrieved.")
    resp.raise_for_status()

    data = (resp.json() or {}).get("data") or {}
    cases: List[Dict[str, Any]] = []
    for r in (data.get("results") or [])[: int(max_cases)]:
        cases.append({
            "cnr": r.get("cnr"),
            "title": _title(r),
            "case_type": r.get("caseType"),
            "status": r.get("caseStatus"),
            "filing_date": r.get("filingDate"),
            "next_hearing_date": r.get("nextHearingDate"),
            "court_code": r.get("courtCode"),
            "judges": r.get("judges") or [],
            "source_kind": "external",
        })
    return {"cases": cases, "source": SOURCE_LABEL, "total_hits": data.get("totalHits")}
