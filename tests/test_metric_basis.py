from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).parents[1]
SPEC = importlib.util.spec_from_file_location(
    "validate_metric_basis_test", ROOT / "tools" / "research" / "validate_metric_basis.py"
)
assert SPEC and SPEC.loader
module = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = module
SPEC.loader.exec_module(module)


def registry() -> dict:
    bases = []
    for key in sorted(module.REQUIRED_METRIC_KEYS):
        bases.append(
            {
                "basis_id": f"{key}.official",
                "metric_key": key,
                "company_label": key,
                "company_definition": f"company definition for {key}",
                "standardized_formula": f"standardized({key})",
                "period": "FY2025",
                "currency": "USD",
                "unit": "millions",
                "source_refs": [{"publisher": "Annual report", "path": "report.pdf"}],
                "comparability": "comparable",
                "adjustment_note": "",
            }
        )
    return {"schema_version": 1, "company": "Example", "bases": bases}


def test_complete_registry_passes() -> None:
    assert module.validate_registry(registry()) == []


def test_missing_required_key_blocks() -> None:
    value = registry()
    value["bases"] = [b for b in value["bases"] if b["metric_key"] != "fcf"]
    assert any("fcf" in issue for issue in module.validate_registry(value))


def test_adjusted_basis_requires_note() -> None:
    value = registry()
    value["bases"][0]["comparability"] = "adjusted"
    assert any("adjustment_note" in issue for issue in module.validate_registry(value))


def test_calculation_claim_must_reference_existing_basis() -> None:
    notes = {"claims": [{"epistemic_type": "analyst_calculation", "basis_id": "missing"}]}
    assert any("unknown registry id" in issue for issue in module.validate_registry(registry(), notes))
