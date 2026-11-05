"""Validate CVSS metadata syntax only; OSV remains the sole score calculator.

FIRST specification vector tables:
https://www.first.org/cvss/v3.1/specification-document#Vector-String
https://www.first.org/cvss/v4.0/specification-document#Vector-String
Unsupported versions/metrics fail closed as Needs Triage.
"""

from __future__ import annotations

V3_BASE = {
    "AV": "NALP",
    "AC": "LH",
    "PR": "NLH",
    "UI": "NR",
    "S": "UC",
    "C": "HLN",
    "I": "HLN",
    "A": "HLN",
}
V4_BASE = {
    "AV": "NALP",
    "AC": "LH",
    "AT": "NP",
    "PR": "NLH",
    "UI": "NPA",
    "VC": "HLN",
    "VI": "HLN",
    "VA": "HLN",
    "SC": "HLN",
    "SI": "HLN",
    "SA": "HLN",
}


def metric_values(base: dict[str, str], extra: dict[str, str]) -> dict[str, frozenset[str]]:
    """Normalize all metric values to the same immutable set representation."""
    return {
        key: frozenset(values)
        for key, values in {
            **base,
            **{"M" + key: "X" + values for key, values in base.items()},
            **extra,
        }.items()
    }


V3_VALUES = metric_values(
    V3_BASE,
    {
        "E": "XUPFH",
        "RL": "XOTWU",
        "RC": "XURC",
        "CR": "XHML",
        "IR": "XHML",
        "AR": "XHML",
    },
)
V4_VALUES = metric_values(
    V4_BASE,
    {
        "E": "XAPU",
        "CR": "XHML",
        "IR": "XHML",
        "AR": "XHML",
        "MSI": "XHLNS",
        "MSA": "XHLNS",
        "S": "XNP",
        "AU": "XNY",
        "R": "XAUI",
        "V": "XDC",
        "RE": "XLMH",
    },
)
V4_VALUES["U"] = frozenset({"X", "Clear", "Green", "Amber", "Red"})
VECTOR_SCHEMAS = {
    ("CVSS_V3", "CVSS:3.0"): (frozenset(V3_BASE), V3_VALUES),
    ("CVSS_V3", "CVSS:3.1"): (frozenset(V3_BASE), V3_VALUES),
    ("CVSS_V4", "CVSS:4.0"): (frozenset(V4_BASE), V4_VALUES),
}


def valid_vector(value: object) -> bool:
    if not isinstance(value, dict):
        return False
    vector, kind = value.get("score"), value.get("type")
    if not isinstance(vector, str) or not isinstance(kind, str):
        return False
    parts = vector.split("/")
    schema = VECTOR_SCHEMAS.get((kind, parts[0]))
    if schema is None:
        return False
    required, allowed = schema
    seen: set[str] = set()
    for part in parts[1:]:
        if part.count(":") != 1:
            return False
        key, metric = part.split(":")
        if key in seen or key not in allowed or metric not in allowed[key]:
            return False
        seen.add(key)
    return required <= seen
