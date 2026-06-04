import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _find_score(text: str, label: str):
    # handle both plain 'label: 0.123' and JSON '"label": 0.123'
    m = re.search(rf"{re.escape(label)}:\s*([0-9]+\.?[0-9]*)", text)
    if not m:
        m = re.search(rf'"{re.escape(label)}"\s*:\s*([0-9]+\.?[0-9]*)', text)
    return float(m.group(1)) if m else None


def test_phase37a_short_reports_exist_and_scores():
    files = [
        "PHASE37_SHORT_REGIME_ANALYSIS.md",
        "PHASE37_SCOUT_DIVERGENCE_REPORT.md",
        "PHASE37_MUTATION_RESPONSE_REPORT.md",
        "PHASE37_ADAPTIVE_CAPITAL_FLOW_REPORT.md",
        "PHASE37_SHORT_INTELLIGENCE_CERTIFICATION.md",
    ]

    for fname in files:
        p = ROOT / fname
        assert p.exists(), f"Missing report: {p}"
        txt = _read(p)
        assert txt.strip().startswith("#"), f"Report {fname} looks empty"

    cert = _read(ROOT / "PHASE37_SHORT_INTELLIGENCE_CERTIFICATION.md")
    # certification should include at least regime and scout scores
    assert _find_score(cert, "regime_adaptation_quality") is not None
    assert _find_score(cert, "scout_intelligence_score") is not None
