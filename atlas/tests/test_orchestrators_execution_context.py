def test_orchestrators_attach_execution_context():
    """Static check: orchestrator scripts must attach `execution_context` to engines."""
    import pathlib

    base = pathlib.Path(__file__).resolve().parents[2] / "scripts"
    files = [
        base / "phase36_full_ecosystem_activation.py",
        base / "phase37_long_horizon_intelligence.py",
    ]

    for f in files:
        assert f.exists(), f"Orchestrator script missing: {f}"
        text = f.read_text(encoding="utf-8")
        assert "execution_context" in text, f"{f.name} does not reference execution_context"
