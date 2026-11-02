"""Fail closed on unsupported architectures, external runtimes and Git-sized files."""

import argparse
import json
from pathlib import Path
import struct
import subprocess

GIT_LIMIT = 100 * 1024 * 1024
TARGETS = {
    "aarch64-apple-darwin", "x86_64-apple-darwin",
    "x86_64-pc-windows-msvc", "aarch64-pc-windows-msvc",
}
WINDOWS_SYSTEM_DLLS = {
    "advapi32.dll", "bcrypt.dll", "bcryptprimitives.dll", "crypt32.dll", "dbghelp.dll", "dnsapi.dll",
    "gdi32.dll", "iphlpapi.dll", "kernel32.dll", "msvcrt.dll", "ncrypt.dll",
    "ntdll.dll", "ole32.dll", "oleaut32.dll", "powrprof.dll", "psapi.dll",
    "secur32.dll", "shell32.dll", "shlwapi.dll", "user32.dll", "userenv.dll",
    "version.dll", "winhttp.dll", "winmm.dll", "ws2_32.dll", "normaliz.dll",
    "ucrtbase.dll", "kernelbase.dll",
}


def sizes(folder):
    result = {}
    for path in folder.rglob("*"):
        if path.is_symlink():
            raise RuntimeError(f"Unexpected resource symlink: {path}")
        if path.is_file():
            size = path.stat().st_size
            if size >= GIT_LIMIT:
                raise RuntimeError(f"Git 100 MiB limit: {path} ({size} bytes)")
            result[path.relative_to(folder).as_posix()] = size
    return result


def pe_imports(path, target):
    data = path.read_bytes()
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    if data[:2] != b"MZ" or data[pe:pe + 4] != b"PE\0\0":
        raise RuntimeError(f"Not a PE executable: {path}")
    machine, count = struct.unpack_from("<HH", data, pe + 4)
    if machine != (0xAA64 if target.startswith("aarch64") else 0x8664):
        raise RuntimeError(f"Wrong PE architecture: {path}")
    optional_size = struct.unpack_from("<H", data, pe + 20)[0]
    optional = pe + 24
    if struct.unpack_from("<H", data, optional)[0] != 0x20B:
        raise RuntimeError("Only PE32+ is supported")
    sections = optional + optional_size

    def offset(rva):
        for i in range(count):
            entry = sections + i * 40
            virtual_size, address, raw_size, raw = struct.unpack_from("<IIII", data, entry + 8)
            if address <= rva < address + max(virtual_size, raw_size):
                return raw + rva - address
        raise RuntimeError(f"Unmapped PE RVA: {rva}")

    def string(rva):
        start = offset(rva)
        return data[start:data.index(b"\0", start)].decode("ascii").lower()

    imports = set()
    directories = optional + 112
    number = struct.unpack_from("<I", data, optional + 108)[0]
    for index, stride, name_offset in ((1, 20, 12), (13, 32, 4)):
        if number <= index:
            continue
        rva, length = struct.unpack_from("<II", data, directories + index * 8)
        if not rva:
            continue
        start = offset(rva)
        for entry in range(start, start + length, stride):
            descriptor = data[entry:entry + stride]
            if not any(descriptor):
                break
            if index == 13 and struct.unpack_from("<I", descriptor)[0] != 1:
                raise RuntimeError("Unsupported VA-based delayed import")
            imports.add(string(struct.unpack_from("<I", descriptor, name_offset)[0]))
        else:
            raise RuntimeError("Unterminated PE import table")
    if not imports:
        raise RuntimeError("Missing PE import evidence")
    external = sorted(name for name in imports if name not in WINDOWS_SYSTEM_DLLS
                      and not name.startswith(("api-ms-win-", "ext-ms-win-")))
    if external:
        raise RuntimeError(f"Unbundled Windows runtimes: {external}; imports: {sorted(imports)}")
    return sorted(imports)


def audit(binary, target):
    if "windows" in target:
        return pe_imports(binary, target)
    architectures = {
        "aarch64-apple-darwin": ["arm64"],
        "x86_64-apple-darwin": ["x86_64"],
        "universal-apple-darwin": ["arm64", "x86_64"],
    }[target]
    actual = subprocess.check_output(["lipo", "-archs", str(binary)], text=True).split()
    if set(actual) != set(architectures):
        raise RuntimeError(f"Wrong Mach-O architectures: {actual}")
    dependencies = {}
    for arch in architectures:
        output = subprocess.check_output(
            ["otool", "-arch", arch, "-L", str(binary)], text=True,
        )
        names = [line.strip().split(" (", 1)[0] for line in output.splitlines()[1:]]
        if not names or any(not name.startswith(("/usr/lib/", "/System/Library/")) for name in names):
            raise RuntimeError(f"Unbundled Mach-O runtime: {names}")
        dependencies[arch] = sorted(names)
    return dependencies


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("binary", type=Path)
    parser.add_argument("--target", required=True)
    args = parser.parse_args()
    print(json.dumps(audit(args.binary, args.target), indent=2))
