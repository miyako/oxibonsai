#!/usr/bin/env python3
"""Build the pinned upstream CLI; never download an upstream executable."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def run(*args, cwd=None):
    return subprocess.check_output(args, cwd=cwd, text=True).strip()


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def smoke(binary, version):
    actual = run(str(binary), "--version")
    if actual != f"oxibonsai {version}":
        raise RuntimeError(f"Unexpected CLI version: {actual}")
    help_text = run(str(binary), "serve", "--help")
    for flag in (
        "--model", "--host", "--port", "--tokenizer", "--max-seq-len",
        "--pool-size", "--bearer-token", "--max-concurrent-requests",
        "--request-timeout-ms", "--config",
    ):
        if flag not in help_text:
            raise RuntimeError(f"Missing server flag: {flag}")


def verify_build(manifest, pin, target):
    expected = {
        **{key: pin[key] for key in ("repository", "tag", "revision", "committed_at", "version")},
        "target": target,
        "features": pin["targets"][target],
        "cargo_lock_sha256": sha256(ROOT / "Cargo.lock"),
        "license_sha256": sha256(ROOT / "oxibonsai" / "third party" / "LICENSE.txt"),
    }
    for key, value in expected.items():
        if manifest.get(key) != value:
            raise RuntimeError(f"{target}: provenance mismatch for {key}")
    if not manifest["rustc"].startswith(f"rustc {pin['rust']} "):
        raise RuntimeError(f"{target}: toolchain mismatch")


def build(target, work, source=None):
    pin = json.loads((ROOT / "upstream.json").read_text())
    features = pin["targets"][target]
    work = work.resolve()
    work.mkdir(parents=True, exist_ok=True)
    if source is None:
        source = work / "source"
        if not source.exists():
            subprocess.run(["git", "init", "--quiet", str(source)], check=True)
            subprocess.run(
                ["git", "-C", str(source), "fetch", "--quiet", "--depth=1",
                 pin["repository"], pin["revision"]], check=True,
            )
            subprocess.run(
                ["git", "-C", str(source), "checkout", "--quiet", "--detach", "FETCH_HEAD"],
                check=True,
            )
    source = source.resolve()
    if run("git", "rev-parse", "HEAD", cwd=source) != pin["revision"]:
        raise RuntimeError("Source HEAD does not match upstream.json; use a fresh work directory")
    if run("git", "status", "--porcelain", "--untracked-files=normal", cwd=source):
        raise RuntimeError("Upstream source has local changes")
    lock = ROOT / "Cargo.lock"
    shutil.copyfile(lock, source / "Cargo.lock")
    env = os.environ.copy()
    # Do not silently produce a host-tuned binary unsuitable for distribution.
    for key in ("RUSTFLAGS", "CARGO_ENCODED_RUSTFLAGS"):
        if env.get(key):
            raise RuntimeError(f"Unset {key} for a portable distribution build")
    env["CARGO_TARGET_DIR"] = str(work / "target")
    subprocess.run(
        ["cargo", f"+{pin['rust']}", "build", "--locked", "--release",
         "--manifest-path", str(source / "Cargo.toml"),
         "--package", pin["package"], "--bin", pin["binary"],
         "--no-default-features", "--features", ",".join(features), "--target", target],
        check=True, env=env,
    )
    name = pin["binary"] + (".exe" if "windows" in target else "")
    binary = work / "target" / target / "release" / name
    smoke(binary, pin["version"])
    output = work / "artifacts" / target
    output.mkdir(parents=True, exist_ok=True)
    shutil.copy2(binary, output / name)
    (output / "UPSTREAM-LICENSE.txt").write_bytes(
        subprocess.check_output(["git", "show", f"{pin['revision']}:LICENSE"], cwd=source)
    )
    manifest = {
        **{key: pin[key] for key in ("repository", "tag", "revision", "committed_at", "version")},
        "target": target,
        "features": features,
        "rustc": run("rustc", f"+{pin['rust']}", "--version"),
        "cargo_lock_sha256": sha256(lock),
        "license_sha256": sha256(output / "UPSTREAM-LICENSE.txt"),
        "binary_sha256": sha256(output / name),
    }
    verify_build(manifest, pin, target)
    (output / "source.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", required=True)
    parser.add_argument("--work-dir", type=Path, default=ROOT / ".build" / "server")
    parser.add_argument("--source-dir", type=Path, help="Reuse a clean checkout at the pinned revision")
    args = parser.parse_args()
    print(build(args.target, args.work_dir, args.source_dir))
