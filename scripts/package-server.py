#!/usr/bin/env python3
"""Verify native artifacts and assemble the 4D Resources/bin layout on macOS."""

import argparse
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

from importlib.util import module_from_spec, spec_from_file_location

SPEC = spec_from_file_location("build_server", Path(__file__).with_name("build-server.py"))
BUILD = module_from_spec(SPEC)
SPEC.loader.exec_module(BUILD)
ROOT = BUILD.ROOT


def package(artifacts, output):
    pin = json.loads((ROOT / "upstream.json").read_text())
    if output.exists() and any(output.iterdir()):
        raise RuntimeError("Use an empty output directory; never merge stale artifacts")
    if {path.name for path in artifacts.iterdir()} != set(pin["targets"]):
        raise RuntimeError("Expected exactly the complete supported target set")
    manifests = {}
    binaries = {}
    for target in pin["targets"]:
        folder = artifacts / target
        manifest = json.loads((folder / "source.json").read_text())
        name = "oxibonsai.exe" if "windows" in target else "oxibonsai"
        binary = folder / name
        BUILD.verify_build(manifest, pin, target)
        if manifest["binary_sha256"] != BUILD.sha256(binary):
            raise RuntimeError(f"{target}: provenance mismatch for binary_sha256")
        if manifest["license_sha256"] != BUILD.sha256(folder / "UPSTREAM-LICENSE.txt"):
            raise RuntimeError(f"{target}: provenance mismatch for license_sha256")
        if set(path.name for path in folder.iterdir()) != {name, "source.json", "UPSTREAM-LICENSE.txt"}:
            raise RuntimeError(f"{target}: unexpected native artifact files")
        BUILD.CONTRACT.sizes(folder)
        if manifest["runtime_dependencies"] != BUILD.CONTRACT.audit(binary, target):
            raise RuntimeError(f"{target}: runtime audit mismatch")
        manifests[target] = manifest
        binaries[target] = binary
    output.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ROOT / "oxibonsai" / "third party" / "LICENSE.txt",
                    output / "UPSTREAM-LICENSE.txt")
    mac = output / "macOS"
    mac.mkdir(exist_ok=True)
    subprocess.run(
        ["lipo", "-create", str(binaries["aarch64-apple-darwin"]),
         str(binaries["x86_64-apple-darwin"]), "-output", str(mac / "oxibonsai")],
        check=True,
    )
    subprocess.run(
        ["lipo", str(mac / "oxibonsai"), "-verify_arch", "arm64", "x86_64"], check=True,
    )
    (mac / "oxibonsai").chmod(0o755)
    BUILD.smoke((mac / "oxibonsai").resolve(), pin["version"])
    for target, platform in (
        ("x86_64-pc-windows-msvc", "Windows"),
        ("aarch64-pc-windows-msvc", "WindowsARM"),
    ):
        folder = output / platform
        folder.mkdir(exist_ok=True)
        shutil.copy2(binaries[target], folder / "oxibonsai.exe")
    manifest = {
        "checksum_stage": "pre-component-signing",
        "upstream": pin,
        "builds": manifests,
        "files": {
            path.relative_to(output).as_posix(): BUILD.sha256(path)
            for path in (mac / "oxibonsai", output / "Windows" / "oxibonsai.exe",
                         output / "WindowsARM" / "oxibonsai.exe",
                         output / "UPSTREAM-LICENSE.txt")
        },
    }
    (output / "source.json").write_text(json.dumps(manifest, indent=2) + "\n")
    verify(output)


def verify(output):
    pin = json.loads((ROOT / "upstream.json").read_text())
    manifest = json.loads((output / "source.json").read_text())
    if manifest["upstream"] != pin or set(manifest["builds"]) != set(pin["targets"]):
        raise RuntimeError("Packaged source selection differs from upstream.json")
    for target in pin["targets"]:
        BUILD.verify_build(manifest["builds"][target], pin, target)
    paths = {"macOS/oxibonsai", "Windows/oxibonsai.exe", "WindowsARM/oxibonsai.exe",
             "UPSTREAM-LICENSE.txt"}
    if set(manifest["files"]) != paths:
        raise RuntimeError("Incomplete packaged target layout")
    for path in paths:
        if BUILD.sha256(output / path) != manifest["files"][path]:
            raise RuntimeError(f"Packaged binary checksum mismatch: {path}")
    if manifest.get("checksum_stage") != "pre-component-signing":
        raise RuntimeError("Missing pre-signing checksum scope")
    actual = set(BUILD.CONTRACT.sizes(output))
    if actual != paths | {"source.json"}:
        raise RuntimeError(f"Unexpected resource closure: {actual}")
    mac_dependencies = BUILD.CONTRACT.audit(
        output / "macOS" / "oxibonsai", "universal-apple-darwin",
    )
    for target, arch in (("aarch64-apple-darwin", "arm64"), ("x86_64-apple-darwin", "x86_64")):
        expected = manifest["builds"][target]["runtime_dependencies"]
        if expected != {arch: mac_dependencies[arch]}:
            raise RuntimeError(f"{target}: packaged Mach-O runtime audit mismatch")
        with tempfile.TemporaryDirectory() as temp:
            thin = Path(temp) / "oxibonsai"
            subprocess.run(
                ["lipo", str(output / "macOS" / "oxibonsai"), "-thin", arch,
                 "-output", str(thin)], check=True,
            )
            if BUILD.sha256(thin) != manifest["builds"][target]["binary_sha256"]:
                raise RuntimeError(f"{target}: build/package slice checksum mismatch")
    for target, platform in (("x86_64-pc-windows-msvc", "Windows"),
                             ("aarch64-pc-windows-msvc", "WindowsARM")):
        binary = output / platform / "oxibonsai.exe"
        if BUILD.sha256(binary) != manifest["builds"][target]["binary_sha256"]:
            raise RuntimeError(f"{target}: build/package binary mismatch")
        if BUILD.CONTRACT.audit(binary, target) != manifest["builds"][target]["runtime_dependencies"]:
            raise RuntimeError(f"{target}: runtime audit mismatch")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifacts", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    if args.verify_only:
        verify(args.output)
    elif args.artifacts is None:
        parser.error("--artifacts is required unless --verify-only is set")
    else:
        package(args.artifacts, args.output)
