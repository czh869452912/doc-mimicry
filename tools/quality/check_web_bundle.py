from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path


DEFAULT_INITIAL_MAX_KB = 760.0
DEFAULT_EDITOR_MAX_KB = 650.0


@dataclass(frozen=True)
class JsAsset:
    name: str
    path: Path
    size_kb: float
    initial: bool


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check DocAgent web bundle budgets.")
    parser.add_argument("dist", type=Path, help="Path to apps/web/dist")
    parser.add_argument("--initial-max-kb", type=float, default=DEFAULT_INITIAL_MAX_KB)
    parser.add_argument("--editor-max-kb", type=float, default=DEFAULT_EDITOR_MAX_KB)
    args = parser.parse_args(argv)

    assets = _read_assets(args.dist)
    if not assets:
        print(f"No JavaScript assets found under {args.dist}", file=sys.stderr)
        return 2

    for asset in sorted(assets, key=lambda item: item.size_kb, reverse=True):
        marker = "initial" if asset.initial else "lazy"
        print(f"{asset.name}: {asset.size_kb:.2f} kB ({marker})")

    failures: list[str] = []
    initial_assets = [asset for asset in assets if asset.initial]
    if not initial_assets:
        failures.append("No initial JavaScript asset referenced by dist/index.html")
    for asset in initial_assets:
        if asset.size_kb > args.initial_max_kb:
            failures.append(
                f"Initial chunk {asset.name} is {asset.size_kb:.2f} kB; "
                f"budget is {args.initial_max_kb:.2f} kB"
            )

    editor_assets = [asset for asset in assets if asset.name.startswith("DraftEditor-")]
    if not editor_assets:
        failures.append("Expected DraftEditor lazy chunk was not found")
    for asset in editor_assets:
        if asset.size_kb > args.editor_max_kb:
            failures.append(
                f"DraftEditor chunk {asset.name} is {asset.size_kb:.2f} kB; "
                f"budget is {args.editor_max_kb:.2f} kB"
            )

    if failures:
        print("\nBundle budget failed:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1
    return 0


def _read_assets(dist: Path) -> list[JsAsset]:
    assets_dir = dist / "assets"
    initial_names = _initial_js_names(dist / "index.html")
    return [
        JsAsset(
            name=path.name,
            path=path,
            size_kb=path.stat().st_size / 1000,
            initial=path.name in initial_names,
        )
        for path in sorted(assets_dir.glob("*.js"))
    ]


def _initial_js_names(index_html: Path) -> set[str]:
    if not index_html.is_file():
        return set()
    html = index_html.read_text(encoding="utf-8")
    return {
        Path(match).name
        for match in re.findall(r'<script[^>]+src="([^"]+\.js)"', html)
    }


if __name__ == "__main__":
    raise SystemExit(main())
