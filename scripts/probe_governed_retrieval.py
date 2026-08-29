"""Probe the configured Orac model for structured-tool framing."""
# Author: Clive Bostock
# Date: 2026-08-29
# Description: Runs a bounded read-only Phase 2A capability fixture.
# Purpose: Produce content-free evidence for explicit administrative review.
# Usage: python scripts/probe_governed_retrieval.py [--pretty]

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from lib.config_mgr import ConfigManager  # noqa: E402
from model.provider_registry import ProviderRegistry  # noqa: E402
from orac_core.governed_retrieval import StructuredToolCapabilityProbe  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    """Build the small probe command-line parser."""
    parser = argparse.ArgumentParser(
        description=(
            "Probe the configured provider/runtime/model structured-tool framing. "
            "The probe never executes retrieval or mutates capability evidence."
        )
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Indent the content-free JSON report.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the fixed fixture and print only safe aggregate evidence."""
    args = build_parser().parse_args(argv)
    config = ConfigManager(
        config_file_path=PROJECT_ROOT / "resources" / "config" / "orac.ini"
    )
    provider = config.config_value("service", "llm_service_id").strip().lower()
    service_url = config.config_value("service", "service_url").strip()
    model_name = config.config_value("service", "default_model_name").strip()
    connector = ProviderRegistry().create_connector(
        provider_id=provider,
        service_url=service_url,
        model_name=model_name,
    )
    report = StructuredToolCapabilityProbe().run(connector)
    print(
        json.dumps(
            {
                "schema_version": 1,
                "provider": provider,
                "model": model_name,
                "report": asdict(report),
                "evidence_mutated": False,
                "retrieval_executed": False,
            },
            indent=2 if args.pretty else None,
            sort_keys=True,
        )
    )
    return 0 if report.streamed_framing_valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
