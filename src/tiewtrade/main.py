"""Application entry point."""

from __future__ import annotations

import argparse
import os
from collections.abc import Sequence
from pathlib import Path

from tiewtrade import __version__
from tiewtrade.application.bootstrap import ApplicationBootstrap


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="tiewtrade", description="TiewTrade desktop app")
    parser.add_argument("--version", action="store_true", help="Show application version and exit")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Initialize foundation services and print a readiness message",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Optional TOML configuration file",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.version:
        print(__version__)
        return 0

    environ = os.environ
    bootstrap = ApplicationBootstrap(config_path=args.config, environ=environ)
    context = bootstrap.initialize()
    context.logger.info("TiewTrade foundation is ready")

    if args.check:
        print("TiewTrade foundation initialized")

    return 0
