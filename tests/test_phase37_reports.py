import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _find_score(text: str, label: str):
    # matches lines like 'Long-horizon specialization score: 0.381'
    m = re.search(rf"{re.escape(label)}:\s*([0-9]+\.?[0-9]*)", text)
    return float(m.group(1)) if m else None


def test_phase37_reports_exist_and_scores():
    files = [
        "PHASE37_SPECIALIZATION_EVOLUTION_REPORT.md",
        "PHASE37_MUTATION_DOMINANCE_REPORT.md",
        "PHASE37_SCOUT_INTELLIGENCE_REPORT.md",
        "PHASE37_CAPITAL_MIGRATION_REPORT.md",
        "PHASE37_SURVIVAL_QUALITY_REPORT.md",
        "PHASE37_REGIME_PERTURBATION_REPORT.md",
        "PHASE37_LONG_HORIZON_CERTIFICATION.md",
    ]

    for fname in files:
        p = ROOT / fname
        assert p.exists(), f"Missing report: {p}"
        txt = _read(p)
        # basic sanity: file should have a title header
        assert txt.strip().startswith("#"), f"Report {fname} looks empty"

    # Check numeric score in specialization report
    spec = _read(ROOT / files[0])
    val = _find_score(spec, "Long-horizon specialization score")
    assert val is not None and 0.0 <= val <= 1.0, "Specialization score missing or out of range"

    # Check mutation dominance present as numeric
    mut = _read(ROOT / files[1])
    val2 = _find_score(mut, "Mutation dominance score")
    assert val2 is not None and 0.0 <= val2 <= 1.0, "Mutation dominance score missing or out of range"
