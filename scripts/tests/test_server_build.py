import importlib.util
import json
import os
from pathlib import Path, PureWindowsPath
import tempfile
import unittest
from unittest.mock import patch


def load(name):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).parents[1] / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


BUILD = load("build-server")
PACKAGE = load("package-server")


class ServerBuildTests(unittest.TestCase):
    def test_smoke_checks_version_and_every_required_flag(self):
        flags = ("--model --host --port --tokenizer --max-seq-len --pool-size "
                 "--bearer-token --max-concurrent-requests --request-timeout-ms --config")
        with patch.object(BUILD, "run", side_effect=["oxibonsai 0.2.3", flags]):
            BUILD.smoke(Path("oxibonsai"), "0.2.3")
        with patch.object(BUILD, "run", return_value="oxibonsai 0.2.2"):
            with self.assertRaisesRegex(RuntimeError, "version"):
                BUILD.smoke(Path("oxibonsai"), "0.2.3")
        with patch.object(BUILD, "run", side_effect=["oxibonsai 0.2.3", "--model"]):
            with self.assertRaisesRegex(RuntimeError, "Missing server flag"):
                BUILD.smoke(Path("oxibonsai"), "0.2.3")

    def test_wrong_source_revision_is_rejected_before_build(self):
        with tempfile.TemporaryDirectory() as temp:
            with patch.object(BUILD, "run", return_value="wrong-revision"):
                with self.assertRaisesRegex(RuntimeError, "HEAD"):
                    BUILD.build("aarch64-apple-darwin", Path(temp), Path(temp))

    def test_modified_source_is_rejected_before_build(self):
        pin = json.loads((BUILD.ROOT / "upstream.json").read_text())
        with tempfile.TemporaryDirectory() as temp:
            with patch.object(BUILD, "run", side_effect=[pin["revision"], " M src/main.rs"]):
                with self.assertRaisesRegex(RuntimeError, "local changes"):
                    BUILD.build("aarch64-apple-darwin", Path(temp), Path(temp))

    def fixture(self, root):
        pin = json.loads((BUILD.ROOT / "upstream.json").read_text())
        for target, features in pin["targets"].items():
            folder = root / target
            folder.mkdir()
            name = "oxibonsai.exe" if "windows" in target else "oxibonsai"
            binary = folder / name
            binary.write_bytes(target.encode())
            license_file = BUILD.ROOT / "oxibonsai" / "third party" / "LICENSE.txt"
            (folder / "UPSTREAM-LICENSE.txt").write_bytes(license_file.read_bytes())
            manifest = {
                **{key: pin[key] for key in ("repository", "tag", "revision", "committed_at", "version")},
                "target": target, "features": features,
                "rustc": f"rustc {pin['rust']} (test)",
                "cargo_lock_sha256": BUILD.sha256(BUILD.ROOT / "Cargo.lock"),
                "license_sha256": BUILD.sha256(license_file),
                "binary_sha256": BUILD.sha256(binary),
            }
            (folder / "source.json").write_text(json.dumps(manifest))

    def test_package_rejects_mixed_provenance(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.fixture(root)
            manifest = root / "aarch64-apple-darwin" / "source.json"
            data = json.loads(manifest.read_text())
            data["revision"] = "wrong-revision"
            manifest.write_text(json.dumps(data))
            with self.assertRaisesRegex(RuntimeError, "revision"):
                PACKAGE.package(root, root / "output")

    def test_package_rejects_tampered_binary(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.fixture(root)
            (root / "aarch64-pc-windows-msvc" / "oxibonsai.exe").write_bytes(b"tampered")
            with self.assertRaisesRegex(RuntimeError, "binary_sha256"):
                PACKAGE.package(root, root / "output")

    def test_package_requires_all_four_targets(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with self.assertRaises(FileNotFoundError):
                PACKAGE.package(root, root / "output")

    def test_package_layout_and_universal_architecture_checks(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.fixture(root)
            output = root / "output"

            def lipo(args, check):
                self.assertTrue(check)
                if "-create" in args:
                    Path(args[-1]).write_bytes(b"universal")
                else:
                    self.assertEqual(args[-3:], ["-verify_arch", "arm64", "x86_64"])

            relative_to = Path.relative_to
            with patch.object(PACKAGE.subprocess, "run", side_effect=lipo), \
                    patch.object(PACKAGE.BUILD, "smoke"), \
                    patch.object(Path, "chmod", autospec=True, side_effect=Path.chmod) as chmod, \
                    patch.object(
                        Path, "relative_to", autospec=True,
                        side_effect=lambda path, base: PureWindowsPath(relative_to(path, base)),
                    ):
                PACKAGE.package(root, output)
            chmod.assert_called_once_with(output / "macOS" / "oxibonsai", 0o755)
            provenance = json.loads((output / "source.json").read_text())
            self.assertEqual(set(provenance["files"]), {
                "macOS/oxibonsai", "Windows/oxibonsai.exe", "WindowsARM/oxibonsai.exe",
                "UPSTREAM-LICENSE.txt",
            })
            self.assertEqual(len(provenance["builds"]), 4)
            if os.name != "nt":
                self.assertTrue((output / "macOS" / "oxibonsai").stat().st_mode & 0o111)
            (output / "Windows" / "oxibonsai.exe").write_bytes(b"tampered")
            with self.assertRaisesRegex(RuntimeError, "checksum"):
                PACKAGE.verify(output)

    def test_build_provenance_rejects_wrong_lock_features_and_toolchain(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.fixture(root)
            pin = json.loads((BUILD.ROOT / "upstream.json").read_text())
            target = "aarch64-apple-darwin"
            original = json.loads((root / target / "source.json").read_text())
            for key, value in (("features", ["server"]), ("cargo_lock_sha256", "bad"),
                               ("rustc", "rustc 1.86.0 (test)")):
                with self.subTest(key=key):
                    manifest = {**original, key: value}
                    with self.assertRaises(RuntimeError):
                        BUILD.verify_build(manifest, pin, target)


if __name__ == "__main__":
    unittest.main()
