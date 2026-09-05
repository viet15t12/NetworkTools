"""Command-line interface for the CAMS documentation renderer."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

from .environment import configure_qt_environment
from .shots import (
    DIALOG_REGRESSION_FILENAMES,
    SHOT_REGISTRY,
    VLAN_WORKFLOW_FILENAMES,
    resolve_shots,
)


APP_DIR = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = APP_DIR.parent
DEFAULT_OUTPUT_DIR = REPOSITORY_ROOT / "docs" / "research" / "book" / "figures" / "gui"


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return parsed


def _positive_scale(value: str) -> float:
    parsed = float(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return parsed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Render deterministic CAMS QML screenshots as PNG files."
    )
    parser.add_argument(
        "shot",
        choices=(*SHOT_REGISTRY.keys(), "vlan", "dialogs", "chapter-03", "chapter-04", "all"),
        help="registered screenshot name, a workflow ('vlan', 'dialogs', 'chapter-03', or 'chapter-04'), or 'all'",
    )
    parser.add_argument("--width", type=_positive_int, default=1600)
    parser.add_argument("--height", type=_positive_int, default=1000)
    parser.add_argument("--scale", type=_positive_scale, default=2.0)
    parser.add_argument("--theme", choices=("light", "dark"), default="light")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"PNG destination (default: {DEFAULT_OUTPUT_DIR})",
    )
    return parser


def ensure_output_directory(path: Path) -> Path:
    resolved = path.expanduser().resolve()
    resolved.mkdir(parents=True, exist_ok=True)
    return resolved


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    configure_qt_environment()

    # Qt and main.py must only be imported after the headless/DPI variables exist.
    from .runtime import (
        DocshotError,
        RenderRequest,
        render_dialog_regressions,
        render_shot,
        render_vlan_workflow,
    )

    # Chapter 3 always belongs to the current book, independent of CWD and
    # the legacy default/override used by older workflows.
    output_dir = ensure_output_directory(
        APP_DIR / "book" / "figures" / "gui" / args.shot
        if args.shot in {"chapter-03", "chapter-04"} else args.output_dir
    )
    request = RenderRequest(
        width=args.width,
        height=args.height,
        scale=args.scale,
        theme=args.theme,
        output_dir=output_dir,
    )
    try:
        if args.shot == "chapter-04":
            from .chapter04 import render_chapter_04_workflow
            for result in render_chapter_04_workflow(request):
                print(f"{result.path.name}: {result.path} ({result.width}x{result.height})")
            return 0
        if args.shot == "chapter-03":
            from .chapter03 import render_chapter_03_workflow
            for result in render_chapter_03_workflow(request):
                print(f"{result.path.name}: {result.path} ({result.width}x{result.height})")
            return 0
        if args.shot == "vlan":
            workflow_request = RenderRequest(
                width=request.width,
                height=request.height,
                scale=request.scale,
                theme=request.theme,
                output_dir=output_dir / "vlan",
                timeout_ms=request.timeout_ms,
            )
            results = render_vlan_workflow(workflow_request)
            print("Created VLAN documentation screenshots:")
            for filename, result in zip(VLAN_WORKFLOW_FILENAMES, results, strict=True):
                print(f"{filename}: {result.path} ({result.width}x{result.height})")
            return 0
        if args.shot == "dialogs":
            results = render_dialog_regressions(request)
            print("Created dialog regression screenshots:")
            for filename, result in zip(
                DIALOG_REGRESSION_FILENAMES, results, strict=True
            ):
                print(f"{filename}: {result.path} ({result.width}x{result.height})")
            return 0
        for shot in resolve_shots(args.shot):
            result = render_shot(shot, request)
            print(f"{shot.name}: {result.path} ({result.width}x{result.height})")
    except (DocshotError, OSError, ValueError) as exc:
        print(f"docshots: {exc}", file=sys.stderr)
        return 1
    return 0


__all__ = [
    "APP_DIR",
    "DEFAULT_OUTPUT_DIR",
    "REPOSITORY_ROOT",
    "build_parser",
    "ensure_output_directory",
    "main",
]
