"""
Contract Governance Check — CLI tool for Route ↔ Auth ↔ Scope contract validation.

Validates that all API routes are declared in the contract manifest and that
auth/scope assignments match the contract. Designed for CI/CD gating or
operator audit.

Usage:
    python scripts/contract_governance_check.py
    python scripts/contract_governance_check.py --json
    python scripts/contract_governance_check.py --report-file contract_report.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="ATLAS Contract Governance Check")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument(
        "--report-file", type=str, default=None, help="Write report to file"
    )
    args = parser.parse_args()

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

    from atlas.api.day4_api import app as day4_app
    from atlas.api.contracts.validator import validate_app_routes, format_report
    from atlas.api.contracts.manifest import get_contract_manifest

    manifest = get_contract_manifest()
    report = validate_app_routes(day4_app, manifest)

    if args.json or args.report_file:
        output = {
            "passed": report.passed,
            "routes_checked": report.checked,
            "manifest_contracts": report.manifest_count,
            "app_routes": report.app_route_count,
            "errors": len(report.errors),
            "warnings": len(report.warnings),
            "violations": [
                {
                    "contract_key": v.contract_key,
                    "category": v.category,
                    "severity": v.severity,
                    "message": v.message,
                }
                for v in report.violations
            ],
        }
        if args.report_file:
            Path(args.report_file).write_text(json.dumps(output, indent=2))
            print(f"Report written to {args.report_file}")
        if args.json:
            print(json.dumps(output, indent=2))
    else:
        print(format_report(report))

    sys.exit(0 if report.passed else 1)


if __name__ == "__main__":
    main()
