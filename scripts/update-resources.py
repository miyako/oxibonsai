#!/usr/bin/env python3
"""Trusted workflow entry point: verify a complete build and fast-forward main."""

import argparse
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess

SPEC = importlib.util.spec_from_file_location("package", Path(__file__).with_name("package-server.py"))
PACKAGE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PACKAGE)
ROOT = PACKAGE.ROOT
RESOURCE = "oxibonsai/Resources/bin"
FILES = ("macOS/oxibonsai", "Windows/oxibonsai.exe", "WindowsARM/oxibonsai.exe",
         "UPSTREAM-LICENSE.txt", "source.json")
PATHS = tuple(f"{RESOURCE}/{path}" for path in FILES)


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def fresh(expected):
    git("fetch", "--quiet", "origin", "refs/heads/main:refs/remotes/origin/main")
    if git("rev-parse", "origin/main") != expected:
        raise RuntimeError("main advanced during the build; rerun the complete native updater")


def update(artifacts, expected):
    if (os.environ.get("GITHUB_ACTIONS") != "true"
            or os.environ.get("GITHUB_EVENT_NAME") != "workflow_dispatch"
            or os.environ.get("GITHUB_REF") != "refs/heads/main"):
        raise RuntimeError("Git updates are only allowed in the trusted main dispatch workflow")
    if not re.fullmatch(r"[0-9a-f]{40}", expected) or git("rev-parse", "HEAD") != expected:
        raise RuntimeError("Expected the exact build source checkout")
    if git("status", "--porcelain", "--untracked-files=normal"):
        raise RuntimeError("Native updater requires a clean checkout")
    PACKAGE.verify(artifacts)
    (artifacts / "macOS" / "oxibonsai").chmod(0o755)
    PACKAGE.BUILD.smoke((artifacts / "macOS" / "oxibonsai").resolve(),
                        json.loads((ROOT / "upstream.json").read_text())["version"])
    fresh(expected)
    for path in FILES:
        destination = ROOT / RESOURCE / path
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(artifacts / path, destination)
    (ROOT / RESOURCE / "macOS" / "oxibonsai").chmod(0o755)
    PACKAGE.verify(ROOT / RESOURCE)
    git("add", "--", *PATHS)
    staged = set(git("diff", "--cached", "--name-only").splitlines())
    if not staged <= set(PATHS):
        raise RuntimeError(f"Refusing unexpected staged files: {staged}")
    if not staged:
        print("Committed native resources already match the verified build")
        return
    fresh(expected)
    git("config", "user.name", "github-actions[bot]")
    git("config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com")
    git("commit", "-m", "Refresh pinned OxiBonsai native resources",
        "-m", f"Build source: {expected}",
        "-m", "Co-authored-by: Copilot App <223556219+Copilot@users.noreply.github.com>")
    # No force, rebase or retry: a concurrent main update must reject this push.
    git("push", "origin", "HEAD:refs/heads/main")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifacts", type=Path, required=True)
    parser.add_argument("--expected-sha", required=True)
    args = parser.parse_args()
    update(args.artifacts, args.expected_sha)
