"""
CI Runner — Local development CI pipeline simulator.

Runs all governance and validation checks locally.
Equivalent to the GitHub Actions CI workflow.

Usage:
    python scripts/run_ci.py                     # Full pipeline
    python scripts/run_ci.py --skip-api          # Skip API-dependent checks
    python scripts/run_ci.py --stage validation  # Run single stage
    python scripts/run_ci.py --list-stages       # List available stages

Exit code: 0 = PASS, 1 = FAIL
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path


STAGES = [
    "imports",
    "schema",
    "contract",
    "lineage",
    "validation",
    "summary",
]


def _print_header(title: str):
    print()
    print("=" * 65)
    print(f"  {title}")
    print("=" * 65)


def _print_result(name: str, passed: bool, detail: str = "", duration: float = 0.0):
    status = "PASS" if passed else "FAIL"
    dur = f" ({duration:.1f}s)" if duration else ""
    print(f"  [{status}] {name}{dur}")
    if detail:
        for line in detail.strip().split("\n"):
            print(f"         {line}")


async def stage_imports() -> bool:
    _print_header("Stage 1/5 — Import Verification")
    passed = True
    checks = [
        "atlas.config.settings",
        "atlas.data.storage.timescale_client",
        "atlas.api.day4_api",
        "atlas.api.services.auth_service",
        "atlas.api.contracts.manifest",
        "atlas.api.contracts.validator",
        "atlas.core.event_lineage",
        "atlas.agents.l2_strategy.coder_agent",
        "atlas.agents.l3_backtest.backtest_runner",
        "atlas.agents.l7_meta.pattern_agent",
        "atlas.agents.l7_meta.intelligence_brief_agent",
    ]
    for mod in checks:
        try:
            __import__(mod)
            _print_result(mod, True)
        except Exception as e:
            _print_result(mod, False, str(e)[:120])
            passed = False
    # Verification harness is in nested package — test via subprocess from atlas dir
    import subprocess, sys as _sys

    repo_root = Path(__file__).resolve().parent.parent
    atlas_dir = repo_root / "atlas"
    result = subprocess.run(
        [_sys.executable, "-c", "import atlas.validation.harness; print('OK')"],
        capture_output=True,
        text=True,
        timeout=15,
        cwd=str(atlas_dir),
    )
    if result.returncode == 0:
        _print_result("atlas.validation.harness", True)
    else:
        _print_result("atlas.validation.harness", False, result.stderr[:120])
        passed = False
    return passed


async def stage_schema(db_url: str) -> bool:
    _print_header("Stage 2/5 — Schema + Auto-Migration")
    start = time.time()
    try:
        from atlas.data.storage.timescale_client import TimescaleClient

        db = TimescaleClient(db_url)
        await db.connect()
        from sqlalchemy.sql import text

        async with db.engine.connect() as conn:
            tables = [
                "strategies",
                "backtest_results",
                "lifecycle_events",
                "pattern_memory",
                "api_keys",
                "audit_logs",
            ]
            for tbl in tables:
                r = await conn.execute(
                    text(
                        f"SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = '{tbl}')"
                    )
                )
                if not r.scalar():
                    _print_result(tbl, False, "table not found")
                    return False
                _print_result(tbl, True)
            # Verify trace_id column
            r = await conn.execute(
                text(
                    "SELECT column_name FROM information_schema.columns WHERE table_name = 'strategies' AND column_name = 'trace_id'"
                )
            )
        if r.fetchone():
            _print_result("strategies.trace_id column", True)
        else:
            _print_result("strategies.trace_id column", False)
            return False
        dur = time.time() - start
        _print_result("Schema check PASS", True, duration=dur)
        return True
    except Exception as e:
        _print_result("Schema check FAIL", False, str(e)[:200])
        return False


async def stage_contract() -> bool:
    _print_header("Stage 3/5 — Contract Governance")
    start = time.time()
    try:
        from atlas.api.day4_api import app as day4_app
        from atlas.api.contracts.validator import validate_app_routes, format_report
        from atlas.api.contracts.manifest import get_contract_manifest

        manifest = get_contract_manifest()
        report = validate_app_routes(day4_app, manifest)
        dur = time.time() - start
        _print_result(
            "Route-Auth-Scope contracts",
            report.passed,
            f"{report.checked} routes, {len(report.errors)} errors, {len(report.warnings)} warnings",
            dur,
        )
        if not report.passed:
            print(format_report(report))
        return report.passed
    except Exception as e:
        _print_result("Contract check FAIL", False, str(e)[:200])
        return False


async def stage_lineage() -> bool:
    _print_header("Stage 4/5 — Event Lineage")
    start = time.time()
    try:
        from atlas.config.settings import settings
        from atlas.data.storage.timescale_client import TimescaleClient
        from atlas.core.event_lineage import EventLineageClient

        db = TimescaleClient(settings.database_url)
        await db.connect()
        lineage = EventLineageClient(db)
        from sqlalchemy.sql import text

        async with db.engine.connect() as conn:
            r = await conn.execute(text("SELECT COUNT(*) FROM lifecycle_events"))
            count = r.scalar() or 0
            r = await conn.execute(
                text("SELECT COUNT(DISTINCT trace_id) FROM lifecycle_events")
            )
            traces = r.scalar() or 0
        dur = time.time() - start
        _print_result(
            "Lifecycle events check",
            True,
            f"{count} events across {traces} traces",
            dur,
        )
        return True
    except Exception as e:
        _print_result("Lineage check FAIL", False, str(e)[:200])
        return False


async def stage_validation(api_base: str) -> bool:
    _print_header("Stage 5/5 — ValidationHarness (requires API server)")
    start = time.time()
    try:
        import httpx

        async with httpx.AsyncClient(timeout=5) as c:
            r = await c.get(f"{api_base}/health")
            if r.status_code != 200:
                _print_result("API health check", False, f"Status {r.status_code}")
                return False
        _print_result("API reachable", True)
    except Exception as e:
        _print_result(
            "API unreachable",
            False,
            f"Start API: uvicorn atlas.api.day4_api:app --port 8000\n  {e}",
        )
        return False

    try:
        import subprocess, sys as _sys

        result = subprocess.run(
            [_sys.executable, "-m", "atlas.validation.__main__"],
            capture_output=True,
            text=True,
            timeout=120,
            cwd=Path(__file__).resolve().parent.parent,
        )
        dur = time.time() - start
        passed = result.returncode == 0
        last_lines = (
            "\n".join(result.stdout.strip().split("\n")[-5:]) if result.stdout else ""
        )
        _print_result(
            f"ValidationHarness ({'PASS' if passed else 'FAIL'})",
            passed,
            last_lines or (result.stderr[:200] if result.stderr else ""),
            dur,
        )
        return passed
    except subprocess.TimeoutExpired:
        _print_result("ValidationHarness", False, "TIMEOUT (120s)")
        return False
    except Exception as e:
        _print_result("ValidationHarness", False, str(e)[:200])
        return False


async def main():
    # Suppress loguru to avoid Unicode encoding crashes on Windows
    try:
        import loguru

        loguru.logger.remove()
    except Exception:
        pass

    repo_root = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(repo_root))
    atlas_pkg = repo_root / "atlas"
    if atlas_pkg.is_dir() and str(atlas_pkg) not in sys.path:
        sys.path.insert(0, str(atlas_pkg))

    parser = argparse.ArgumentParser(description="ATLAS Local CI Runner")
    parser.add_argument(
        "--skip-api", action="store_true", help="Skip API-dependent checks"
    )
    parser.add_argument("--stage", type=str, default=None, help="Run single stage")
    parser.add_argument(
        "--list-stages", action="store_true", help="List available stages"
    )
    parser.add_argument(
        "--api-base", default="http://localhost:8000", help="API base URL"
    )
    parser.add_argument(
        "--db-url", default=None, help="Database URL (default: from settings)"
    )
    args = parser.parse_args()

    if args.list_stages:
        print("Available CI stages:")
        for s in STAGES:
            print(f"  {s}")
        sys.exit(0)

    from atlas.config.settings import settings

    db_url = args.db_url or settings.database_url

    results: dict[str, bool] = {}

    if args.stage:
        stage_map = {
            "imports": stage_imports,
            "schema": lambda: stage_schema(db_url),
            "contract": stage_contract,
            "lineage": stage_lineage,
            "validation": lambda: stage_validation(args.api_base),
        }
        if args.stage not in stage_map:
            print(f"Unknown stage: {args.stage}")
            sys.exit(1)
        fn = stage_map[args.stage]
        passed = await fn()
        sys.exit(0 if passed else 1)
    else:
        results["imports"] = await stage_imports()
        results["schema"] = await stage_schema(db_url)
        results["contract"] = await stage_contract()
        results["lineage"] = await stage_lineage()
        if not args.skip_api:
            results["validation"] = await stage_validation(args.api_base)
        else:
            results["validation"] = True
            _print_result("ValidationHarness", True, "(skipped via --skip-api)")

        total = len(results)
        passed_count = sum(1 for v in results.values() if v)
        all_pass = all(results.values())

        print()
        print("=" * 65)
        print(f"  CI RUN SUMMARY")
        print(f"  Passed: {passed_count}/{total}")
        for stage, ok in results.items():
            print(f"    {'PASS' if ok else 'FAIL'}  {stage}")
        print(f"  Overall: {'PASS' if all_pass else 'FAIL'}")
        print("=" * 65)
        sys.exit(0 if all_pass else 1)


if __name__ == "__main__":
    asyncio.run(main())
