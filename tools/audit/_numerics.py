"""Shared numeric extraction helpers for the P12 audit tools.

Extracts numeric tokens from arbitrary strings (CN + EN), with unit awareness.
A "numeric token" carries: raw text, normalized float, declared unit (%, pp, B/亿,
M/万, x, 倍, USD/RMB, etc.), and a sign. Two tokens "match within tolerance"
if their normalized values are close given declared units.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

# Number with optional sign + thousand separator + decimal
NUMBER_RE = re.compile(r"(?<![A-Za-z\.])([+\-]?\d{1,3}(?:,\d{3})+(?:\.\d+)?|[+\-]?\d+(?:\.\d+)?)")

# Common unit suffixes / context words. Order matters — longer/specific first.
UNIT_PATTERNS = [
    (re.compile(r"^(pp|个百分点|百分点)\b"), "pp"),
    (re.compile(r"^%"), "pct"),
    (re.compile(r"^(亿美元|亿元|亿)\b"), "yi"),                # 0.01B = 1 yi
    (re.compile(r"^(万亿|万亿元)\b"), "wanyi"),               # = 10000 yi
    (re.compile(r"^(万|万元)\b"), "wan"),
    (re.compile(r"^(billion|bn|B)\b", re.I), "billion"),
    (re.compile(r"^(million|mn|M)\b", re.I), "million"),
    (re.compile(r"^(倍|x|×)\b"), "x"),
    (re.compile(r"^(USD|US\$|\$)\b"), "usd"),
    (re.compile(r"^(RMB|人民币|元)\b"), "rmb"),
    (re.compile(r"^(港币|港元|HK\$)\b"), "hkd"),
]

CN_DIGITS_RE = re.compile(r"[一二三四五六七八九十百千万亿]+")  # rough — not normalised


@dataclass
class NumericToken:
    raw: str
    value: float
    unit: Optional[str]
    context: str  # ±10 chars around the match for human-readable diff
    path: str = ""  # JSON path or slot path
    note: str = field(default="")


def normalise(value: float, unit: Optional[str]) -> tuple[float, str]:
    """Return (canonical_value, canonical_unit). Canonical units:
    - 'pct' for percent, 'pp' for percentage points (kept distinct)
    - 'amount_yi' for currency / volume amounts in 亿 (=1e8)
    - 'multiple' for multiples
    - None for plain integer/index
    Conversions: million → /100, billion → ×10, wanyi → ×10000.
    """
    if unit == "pct":
        return value, "pct"
    if unit == "pp":
        return value, "pp"
    if unit == "x":
        return value, "multiple"
    if unit == "yi":
        return value, "amount_yi"
    if unit == "wan":
        return value / 10000.0, "amount_yi"
    if unit == "wanyi":
        return value * 10000.0, "amount_yi"
    if unit == "billion":
        return value * 10.0, "amount_yi"           # 1 B = 10 亿
    if unit == "million":
        return value / 100.0, "amount_yi"          # 100 M = 1 亿
    if unit in {"usd", "rmb", "hkd"}:
        return value, "amount_unknown"
    return value, "raw"


def detect_unit_after(text: str, end_idx: int) -> Optional[str]:
    after = text[end_idx:end_idx + 12]
    for pat, name in UNIT_PATTERNS:
        if pat.match(after):
            return name
    return None


def extract_numerics(text: str, path: str = "") -> list[NumericToken]:
    if not text:
        return []
    out: list[NumericToken] = []
    for m in NUMBER_RE.finditer(text):
        raw = m.group(1)
        try:
            v = float(raw.replace(",", ""))
        except ValueError:
            continue
        unit = detect_unit_after(text, m.end())
        # Skip year-shaped 4-digit ints with no unit context — too noisy
        if unit is None and 1900 <= v <= 2100 and "." not in raw:
            continue
        ctx_start = max(0, m.start() - 8)
        ctx_end = min(len(text), m.end() + 12)
        out.append(
            NumericToken(
                raw=raw + (m.string[m.end():m.end() + len(_unit_text(unit, m.string, m.end()))] if unit else ""),
                value=v,
                unit=unit,
                context=text[ctx_start:ctx_end].replace("\n", " ").strip(),
                path=path,
            )
        )
    return out


def _unit_text(unit: Optional[str], full: str, idx: int) -> str:
    if not unit:
        return ""
    after = full[idx:idx + 12]
    for pat, name in UNIT_PATTERNS:
        if name == unit:
            m = pat.match(after)
            if m:
                return m.group(0)
    return ""


def within_tolerance(a: NumericToken, b: NumericToken, *, pp_abs: float = 0.5, pct_rel: float = 0.005) -> tuple[bool, dict]:
    """Per MEMORY.md tolerances:
    - pp values: ±0.5pp absolute
    - currency amounts: ±0.5% relative
    - multiples: ±0.1 absolute
    Returns (ok, info).
    """
    av, au = normalise(a.value, a.unit)
    bv, bu = normalise(b.value, b.unit)
    info = {"a_norm": (av, au), "b_norm": (bv, bu)}
    if au != bu and "amount" not in (au + bu):
        return False, info | {"reason": f"unit mismatch ({au} vs {bu})"}
    if au in {"pct", "pp"}:
        ok = abs(av - bv) <= pp_abs
        return ok, info | {"abs_diff": abs(av - bv), "tol_pp_abs": pp_abs}
    if au == "multiple":
        ok = abs(av - bv) <= 0.1
        return ok, info | {"abs_diff": abs(av - bv)}
    if au == "amount_yi" or "amount" in au:
        denom = max(abs(av), abs(bv), 1e-9)
        rel = abs(av - bv) / denom
        ok = rel <= pct_rel
        return ok, info | {"rel_diff": rel, "tol_pct_rel": pct_rel}
    # raw integers / indices: exact
    ok = a.value == b.value
    return ok, info | {"abs_diff": abs(a.value - b.value)}
