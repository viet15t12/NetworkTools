#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib
import importlib.metadata
import importlib.util
import re
import sys
from pathlib import Path


EXPLICIT_IMPORT_MAP = {
    "pyyaml": "yaml",
    "nornir-netmiko": "nornir_netmiko",
}


SPEC_PATTERN = re.compile(r"\s*([A-Za-z0-9_.-]+)")


def parse_packages_file(path: Path) -> list[str]:
    packages: list[str] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        match = SPEC_PATTERN.match(line)
        if match:
            packages.append(match.group(1))
    return packages


def package_installed_name_set() -> set[str]:
    return {dist.metadata["Name"].lower() for dist in importlib.metadata.distributions() if dist.metadata.get("Name")}


def candidate_import_names(package_name: str) -> list[str]:
    key = package_name.lower()
    candidates: list[str] = []

    explicit = EXPLICIT_IMPORT_MAP.get(key)
    if explicit:
        candidates.append(explicit)

    normalized = key.replace("-", "_").replace(".", "_")
    if normalized not in candidates:
        candidates.append(normalized)

    plain = key.replace("-", "")
    if plain not in candidates:
        candidates.append(plain)

    if key not in candidates:
        candidates.append(key)

    return candidates


def resolve_import_name(package_name: str) -> tuple[str | None, str | None]:
    for module_name in candidate_import_names(package_name):
        try:
            if importlib.util.find_spec(module_name) is not None:
                return module_name, None
        except Exception as exc:
            return None, f"find_spec_error: {exc}"
    return None, None


def get_module_version(module_name: str | None) -> str:
    if not module_name:
        return ""
    try:
        module = importlib.import_module(module_name)
    except Exception:
        return ""
    return getattr(module, "__version__", "") or ""


def main() -> int:
    parser = argparse.ArgumentParser(description="Check packages.txt against installed packages and importable modules")
    parser.add_argument("--packages", "-p", type=Path, default=Path("packages.txt"), help="Path to packages file")
    args = parser.parse_args()

    if not args.packages.exists():
        print(f"[ERROR] packages file not found: {args.packages}")
        return 1

    packages = parse_packages_file(args.packages)
    installed = package_installed_name_set()

    header = f"{'Package':<24} {'Installed?':<12} {'Import?':<10} Details"
    print(header)
    print("-" * len(header))

    missing_installed: list[str] = []
    missing_import: list[str] = []

    for pkg in packages:
        installed_ok = pkg.lower() in installed
        import_name, import_err = resolve_import_name(pkg)
        import_ok = import_name is not None

        if not installed_ok:
            missing_installed.append(pkg)
        if not import_ok:
            missing_import.append(pkg)

        if import_err:
            details = import_err
        elif import_name:
            version = get_module_version(import_name)
            details = f"import={import_name}" + (f", version={version}" if version else "")
        else:
            details = "no import name resolved"

        print(f"{pkg:<24} {('yes' if installed_ok else 'no'):<12} {('yes' if import_ok else 'no'):<10} {details}")

    print()
    print(f"Total packages: {len(packages)}")
    print(f"Missing install: {len(missing_installed)}")
    print(f"Missing import : {len(missing_import)}")

    if missing_installed:
        print("Install-missing:", ", ".join(missing_installed))
    if missing_import:
        print("Import-missing :", ", ".join(missing_import))

    return 0 if not missing_installed and not missing_import else 2


if __name__ == "__main__":
    sys.exit(main())
