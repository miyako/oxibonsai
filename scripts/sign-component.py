#!/usr/bin/env python3
"""Sign every Mach-O (including generated Libraries), then notarize and staple."""

import hashlib
import json
import os
from pathlib import Path
import subprocess

MACHO = {b"\xfe\xed\xfa\xce", b"\xce\xfa\xed\xfe", b"\xfe\xed\xfa\xcf",
         b"\xcf\xfa\xed\xfe", b"\xca\xfe\xba\xbe", b"\xbe\xba\xfe\xca",
         b"\xca\xfe\xba\xbf", b"\xbf\xba\xfe\xca"}
BUNDLES = {".app", ".framework", ".bundle", ".plugin", ".kext"}


def code_files(product):
    result = []
    for path in product.rglob("*"):
        if path.is_file() and not path.is_symlink():
            with path.open("rb") as stream:
                if stream.read(4) in MACHO:
                    result.append(path)
    if not any("Libraries" in path.relative_to(product).parts for path in result):
        raise RuntimeError("No generated Mach-O Libraries found; refusing CLI-only signing")
    if product / "Resources/bin/macOS/oxibonsai" not in result:
        raise RuntimeError("Missing native CLI from signing coverage")
    return sorted(result, key=lambda path: (-len(path.parts), str(path)))


def run(*args):
    subprocess.run(args, check=True)


def verify_signature(path, team, runtime=True):
    run("codesign", "--verify", "--strict", str(path))
    details = subprocess.check_output(
        ["codesign", "-d", "--verbose=4", str(path)], stderr=subprocess.STDOUT, text=True,
    )
    if (f"TeamIdentifier={team}" not in details or "Timestamp=" not in details
            or "Authority=Developer ID Application:" not in details
            or (runtime and "runtime" not in details)):
        raise RuntimeError(f"Missing Developer ID/team/timestamp/runtime: {path}")


def sign(product, dmg, archive):
    identity, team = os.environ["SIGNING_IDENTITY"], os.environ["TEAM_ID"]
    keychain = os.environ["KEYCHAIN_PATH"]
    files = code_files(product)
    bundles = sorted((path for path in product.rglob("*")
                      if path.is_dir() and path.suffix in BUNDLES),
                     key=lambda path: (-len(path.parts), str(path)))
    for path in [*files, *bundles]:
        run("codesign", "--force", "--options", "runtime", "--timestamp",
            "--sign", identity, "--keychain", keychain, str(path))
    for path in [*files, *bundles]:
        verify_signature(path, team)
    inventory = {path.relative_to(product).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
                 for path in files}
    (product / "Resources" / "signed-code.json").write_text(
        json.dumps({"checksum_stage": "final-component-signing", "files": inventory}, indent=2) + "\n",
    )
    run("hdiutil", "create", "-format", "UDBZ", "-srcfolder", str(product), str(dmg))
    run("codesign", "--force", "--timestamp", "--sign", identity, "--keychain", keychain, str(dmg))
    verify_signature(dmg, team, runtime=False)
    result = subprocess.check_output([
        "xcrun", "notarytool", "submit", str(dmg), "--apple-id", os.environ["APPLE_ID"],
        "--team-id", team, "--password", os.environ["NOTARY_PASSWORD"], "--wait",
        "--timeout", "30m", "--output-format", "json",
    ], text=True)
    (dmg.parent / "notarization.json").write_text(result)
    if json.loads(result).get("status") != "Accepted":
        raise RuntimeError("Apple notarization was not Accepted")
    run("xcrun", "stapler", "staple", str(dmg))
    run("xcrun", "stapler", "validate", str(dmg))
    run("spctl", "--assess", "--type", "open", "--context", "context:primary-signature", str(dmg))
    run("ditto", "-c", "-k", "--keepParent", str(product), str(archive))
    checksums = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in (dmg, archive)}
    (dmg.parent / "SHA256SUMS").write_text(
        "".join(f"{digest}  {name}\n" for name, digest in checksums.items()),
    )


if __name__ == "__main__":
    root = Path.cwd()
    sign(root / "Components/oxibonsai.4dbase", root / "oxibonsai.dmg", root / "oxibonsai.zip")
