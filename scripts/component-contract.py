#!/usr/bin/env python3
"""Install checksum-pinned 4D dependencies and require genuine compilation."""

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import stat
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
BUILD_SOURCE = ROOT / ".build" / "component-source"


def install():
    if BUILD_SOURCE.exists():
        raise RuntimeError("Use a fresh component build directory")
    shutil.copytree(
        ROOT / "oxibonsai", BUILD_SOURCE / "oxibonsai",
        ignore=shutil.ignore_patterns("Components", "Libraries", "DerivedData", "Data", "userPreferences.*"),
    )
    shutil.copyfile(ROOT / "package.json", BUILD_SOURCE / "package.json")
    lock = json.loads((ROOT / "component-dependencies.json").read_text())
    destination = BUILD_SOURCE / "oxibonsai" / "Components"
    destination.mkdir(parents=True, exist_ok=True)
    cache = ROOT / ".build" / "dependencies"
    cache.mkdir(parents=True, exist_ok=True)
    for name, pin in lock.items():
        archive = cache / f"{name}.zip"
        urllib.request.urlretrieve(
            f"https://github.com/miyako/{name}/releases/download/{pin['version']}/{name}.zip",
            archive,
        )
        if hashlib.sha256(archive.read_bytes()).hexdigest() != pin["sha256"]:
            raise RuntimeError(f"Dependency checksum mismatch: {name}")
        with zipfile.ZipFile(archive) as source:
            for entry in source.infolist():
                path = Path(entry.filename)
                if (path.is_absolute() or ".." in path.parts
                        or not path.parts or path.parts[0] != f"{name}.4dbase"
                        or stat.S_ISLNK(entry.external_attr >> 16)):
                    raise RuntimeError(f"Unsafe component archive path: {entry.filename}")
            source.extractall(destination)
        compiled = [path for path in (destination / f"{name}.4dbase").iterdir()
                    if path.suffix.lower() == ".4dz"]
        if len(compiled) != 1:
            raise RuntimeError(f"Missing compiled dependency: {name}")
        canonical = destination / f"{name}.4dbase" / f"{name}.4DZ"
        if compiled[0].name != canonical.name:
            compiled[0].rename(canonical)


def report(path):
    data = json.loads(path.read_text())
    if data.get("success") is not True or data.get("errors") != []:
        raise RuntimeError(f"4D compilation did not succeed without diagnostics: {data}")


def product(path):
    archives = [item for item in path.iterdir() if item.suffix.lower() == ".4dz"]
    libraries = list((path / "Libraries").rglob("*"))
    if len(archives) != 1 or not archives[0].stat().st_size:
        raise RuntimeError("Missing compiled component .4DZ")
    with zipfile.ZipFile(archives[0]) as archive:
        if archive.testzip() is not None:
            raise RuntimeError("Corrupt compiled component archive")
        compiled = [item for item in archive.namelist()
                    if item.startswith("Project/DerivedData/CompiledCode/") and not item.endswith("/")]
        if not compiled or not any(Path(item).name.startswith("IX64 ") for item in compiled):
            raise RuntimeError("Missing generic Intel/Windows compiled code in .4DZ")
    if not any(item.is_file() for item in libraries):
        raise RuntimeError("Missing generated component Libraries")
    expected = ROOT / "oxibonsai" / "Resources" / "models" / "tokenizer.json"
    actual = path / "Resources" / "models" / "tokenizer.json"
    if expected.read_bytes() != actual.read_bytes():
        raise RuntimeError("Packaged tokenizer differs from the wrapper resource")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["install", "report", "product"])
    parser.add_argument("path", nargs="?", type=Path)
    args = parser.parse_args()
    if args.command == "install":
        install()
    elif args.path is None:
        parser.error("path is required")
    elif args.command == "report":
        report(args.path)
    else:
        product(args.path)
