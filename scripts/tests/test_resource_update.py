import json
import os
from pathlib import Path
import struct
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from test_server_build import BUILD, load

CONTRACT = load("native-contract")
UPDATE = load("update-resources")
COMPONENT = load("component-contract")
SIGN = load("sign-component")


def pe_fixture(path, dll="kernel32.dll", machine=0x8664, delayed=False):
    data = bytearray(2048)
    data[:2] = b"MZ"
    struct.pack_into("<I", data, 0x3C, 0x80)
    data[0x80:0x84] = b"PE\0\0"
    struct.pack_into("<HH", data, 0x84, machine, 1)
    struct.pack_into("<H", data, 0x94, 240)
    optional = 0x98
    struct.pack_into("<H", data, optional, 0x20B)
    struct.pack_into("<I", data, optional + 108, 16)
    section = optional + 240
    struct.pack_into("<IIII", data, section + 8, 1024, 0x1000, 1024, 0x200)
    index, stride, offset = (13, 32, 4) if delayed else (1, 20, 12)
    struct.pack_into("<II", data, optional + 112 + index * 8, 0x1000, stride * 2)
    if delayed:
        struct.pack_into("<I", data, 0x200, 1)
    struct.pack_into("<I", data, 0x200 + offset, 0x1100)
    data[0x300:0x300 + len(dll) + 1] = dll.encode() + b"\0"
    path.write_bytes(data)


class RuntimeContractTests(unittest.TestCase):
    def test_component_product_requires_actual_compiled_archive_and_tokenizer(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "oxibonsai/Resources/models/tokenizer.json"
            source.parent.mkdir(parents=True)
            source.write_bytes(b"tokenizer")
            product = root / "product"
            tokenizer = product / "Resources/models/tokenizer.json"
            tokenizer.parent.mkdir(parents=True)
            tokenizer.write_bytes(b"tokenizer")
            library = product / "Libraries/lib4d-arm64.dylib"
            library.parent.mkdir()
            library.write_bytes(b"\xcf\xfa\xed\xfe")
            archive = product / "oxibonsai.4dz"
            with patch.object(COMPONENT, "ROOT", root):
                with zipfile.ZipFile(archive, "w") as output:
                    output.writestr("Project/Sources/example.4dm", "source only")
                with self.assertRaisesRegex(RuntimeError, "compiled code"):
                    COMPONENT.product(product)
                with zipfile.ZipFile(archive, "w") as output:
                    output.writestr("Project/DerivedData/CompiledCode/IX64 -2", b"compiled")
                COMPONENT.product(product)
                tokenizer.write_bytes(b"changed")
                with self.assertRaisesRegex(RuntimeError, "tokenizer"):
                    COMPONENT.product(product)

    def test_pe_architecture_and_normal_and_delayed_runtime_imports(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "server.exe"
            for target, machine in (("x86_64-pc-windows-msvc", 0x8664),
                                    ("aarch64-pc-windows-msvc", 0xAA64)):
                for delayed in (False, True):
                    with self.subTest(target=target, delayed=delayed):
                        pe_fixture(path, machine=machine, delayed=delayed)
                        self.assertEqual(CONTRACT.audit(path, target), ["kernel32.dll"])
                        pe_fixture(path, "vcruntime140.dll", machine, delayed)
                        with self.assertRaisesRegex(RuntimeError, "Unbundled Windows"):
                            CONTRACT.audit(path, target)
            pe_fixture(path, machine=0xAA64)
            with self.assertRaisesRegex(RuntimeError, "architecture"):
                CONTRACT.audit(path, "x86_64-pc-windows-msvc")

    def test_macho_rejects_build_machine_dependency_and_wrong_arch(self):
        with patch.object(CONTRACT.subprocess, "check_output", side_effect=[
            "arm64", "server:\n\t@rpath/libprivate.dylib (compatibility version 1.0.0)\n",
        ]):
            with self.assertRaisesRegex(RuntimeError, "Unbundled Mach-O"):
                CONTRACT.audit(Path("server"), "aarch64-apple-darwin")
        with patch.object(CONTRACT.subprocess, "check_output", return_value="arm64"):
            with self.assertRaisesRegex(RuntimeError, "architectures"):
                CONTRACT.audit(Path("server"), "universal-apple-darwin")

    def test_exact_git_size_limit_and_symlinks(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            path = folder / "binary"
            with path.open("wb") as stream:
                stream.truncate(CONTRACT.GIT_LIMIT - 1)
            self.assertEqual(CONTRACT.sizes(folder), {"binary": CONTRACT.GIT_LIMIT - 1})
            with path.open("ab") as stream:
                stream.write(b"\0")
            with self.assertRaisesRegex(RuntimeError, "100 MiB"):
                CONTRACT.sizes(folder)
            path.unlink()
            if os.name != "nt":
                path.symlink_to(folder / "absent")
                with self.assertRaisesRegex(RuntimeError, "symlink"):
                    CONTRACT.sizes(folder)

    def test_structured_compile_report_rejects_false_empty_missing_and_diagnostics(self):
        with tempfile.TemporaryDirectory() as temp:
            report = Path(temp) / "report.json"
            for data in ({}, {"success": False, "errors": []},
                         {"success": True}, {"success": True, "errors": [{"message": "warning"}]}):
                report.write_text(json.dumps(data))
                with self.assertRaisesRegex(RuntimeError, "compilation"):
                    COMPONENT.report(report)
            report.write_text('{"success": true, "errors": []}')
            COMPONENT.report(report)

    def test_signing_covers_generated_libraries_not_just_cli(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            cli = root / "Resources/bin/macOS/oxibonsai"
            cli.parent.mkdir(parents=True)
            cli.write_bytes(b"\xcf\xfa\xed\xfecli")
            with self.assertRaisesRegex(RuntimeError, "CLI-only"):
                SIGN.code_files(root)
            library = root / "Libraries/macos/library.dylib"
            library.parent.mkdir(parents=True)
            library.write_bytes(b"\xcf\xfa\xed\xfelibrary")
            self.assertEqual(set(SIGN.code_files(root)), {cli, library})

    def test_signing_rejects_notarization_failure_after_signing_every_code_object(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            cli = root / "Resources/bin/macOS/oxibonsai"
            library = root / "Libraries/lib4d-arm64.dylib"
            for path in (cli, library):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"\xcf\xfa\xed\xfe")
            environment = {"SIGNING_IDENTITY": "test", "TEAM_ID": "TESTTEAM",
                           "KEYCHAIN_PATH": "test", "APPLE_ID": "test", "NOTARY_PASSWORD": "test"}
            signature = ("TeamIdentifier=TESTTEAM\nTimestamp=test\nflags=runtime\n"
                         "Authority=Developer ID Application: test")
            with patch.dict(os.environ, environment), patch.object(SIGN, "run") as run, \
                    patch.object(SIGN.subprocess, "check_output", side_effect=[
                        signature, signature, signature,
                        '{"status": "Invalid"}',
                    ]):
                with self.assertRaisesRegex(RuntimeError, "notarization"):
                    SIGN.sign(root, root / "test.dmg", root / "test.zip")
            signed = {call.args[-1] for call in run.call_args_list
                      if call.args[:2] == ("codesign", "--force")}
            self.assertTrue({str(cli), str(library)} <= signed)
            self.assertFalse(any(call.args[:2] == ("xcrun", "stapler") for call in run.call_args_list))

    def test_git_update_entry_point_rejects_untrusted_execution(self):
        with patch.dict(os.environ, {"GITHUB_ACTIONS": "false"}):
            with self.assertRaisesRegex(RuntimeError, "trusted main"):
                UPDATE.update(Path("unused"), "a" * 40)


class SourceInitializationTests(unittest.TestCase):
    def test_fresh_cached_checkout_and_dirty_rejection_with_real_git(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "upstream"
            source.mkdir()
            subprocess.run(["git", "init", "-q", str(source)], check=True)
            subprocess.run(["git", "-C", str(source), "config", "user.name", "test"], check=True)
            subprocess.run(["git", "-C", str(source), "config", "user.email", "test@example.com"], check=True)
            (source / "LICENSE").write_text("test license\n")
            subprocess.run(["git", "-C", str(source), "add", "LICENSE"], check=True)
            subprocess.run(["git", "-C", str(source), "commit", "-qm", "fixture"], check=True)
            revision = subprocess.check_output(
                ["git", "-C", str(source), "rev-parse", "HEAD"], text=True,
            ).strip()
            repository = root / "repository"
            repository.mkdir()
            pin = json.loads((BUILD.ROOT / "upstream.json").read_text())
            pin.update(repository=str(source), revision=revision)
            (repository / "upstream.json").write_text(json.dumps(pin))
            (repository / "Cargo.lock").write_text("test lock\n")
            work = root / "work"

            def stop(*args, **kwargs):
                if args and isinstance(args[0], list) and args[0][0] == "cargo":
                    raise RuntimeError("reached cargo")
                return original_run(*args, **kwargs)

            original_run = subprocess.run
            with patch.object(BUILD, "ROOT", repository), \
                    patch.object(BUILD.subprocess, "run", side_effect=stop):
                for _ in range(2):
                    with self.assertRaisesRegex(RuntimeError, "reached cargo"):
                        BUILD.build("aarch64-apple-darwin", work)
                (work / "source" / "LICENSE").write_text("dirty\n")
                with self.assertRaisesRegex(RuntimeError, "local changes"):
                    BUILD.build("aarch64-apple-darwin", work)


class UpdaterGitTests(unittest.TestCase):
    def test_authorized_update_pushes_exact_paths_and_rejects_stale_main(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            remote, checkout, artifacts = root / "remote.git", root / "checkout", root / "artifacts"

            def git(*args):
                return subprocess.check_output(["git", "-C", str(checkout), *args], text=True).strip()

            subprocess.run(["git", "init", "-q", "--bare", str(remote)], check=True)
            subprocess.run(["git", "init", "-q", "-b", "main", str(checkout)], check=True)
            git("config", "user.name", "fixture")
            git("config", "user.email", "fixture@example.com")
            (checkout / "upstream.json").write_text('{"version":"0.2.3"}')
            (checkout / "unrelated.txt").write_text("preserved")
            git("add", "upstream.json", "unrelated.txt")
            git("commit", "-qm", "base")
            git("remote", "add", "origin", str(remote))
            git("push", "-q", "origin", "HEAD:main")
            expected = git("rev-parse", "HEAD")
            for path in UPDATE.FILES:
                file = artifacts / path
                file.parent.mkdir(parents=True, exist_ok=True)
                file.write_bytes(b"fixture")
            environment = {"GITHUB_ACTIONS": "true", "GITHUB_EVENT_NAME": "workflow_dispatch",
                           "GITHUB_REF": "refs/heads/main"}
            with patch.object(UPDATE, "ROOT", checkout), patch.dict(os.environ, environment), \
                    patch.object(UPDATE.PACKAGE, "verify"), patch.object(UPDATE.PACKAGE.BUILD, "smoke"):
                UPDATE.update(artifacts, expected)
                changed = set(git("diff", "--name-only", expected, "HEAD").splitlines())
                self.assertEqual(changed, set(UPDATE.PATHS))
                self.assertEqual(git("rev-parse", "HEAD"), git("rev-parse", "origin/main"))
                self.assertEqual((checkout / "unrelated.txt").read_text(), "preserved")
                with self.assertRaisesRegex(RuntimeError, "main advanced"):
                    UPDATE.fresh(expected)
                self.assertEqual(git("tag", "--list"), "")


if __name__ == "__main__":
    unittest.main()
