"""Build ocgcore from source and bundle it into src/data/core.

Requirements: Git, Meson, Ninja, C++ compiler, and Lua 5.4 development files.

Usage:
    python scripts/build_ocgcore.py [--tag TAG]
    python scripts/build_ocgcore.py --arch x64
    python scripts/build_ocgcore.py --clean
"""

import argparse
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
BUILD_DIR = ROOT / "build" / "ocgcore"
OUTPUT_DIR = ROOT / "src" / "data" / "core"
REPO_URL = "https://github.com/edo9300/ygopro-core.git"
DEFAULT_TAG = "master"
WINDOWS_MACHINE_BITS = {
    0x014C: 32,
    0x8664: 64,
    0xAA64: 64,
}


def tool_path(name: str) -> str | None:
    found = shutil.which(name)
    if found:
        return found
    if platform.system() == "Windows":
        for prefix in [Path(r"C:\msys64\mingw64\bin"), Path(r"C:\msys64\usr\bin")]:
            msys_tool = prefix / f"{name}.exe"
            if msys_tool.exists():
                return str(msys_tool)
    suffix = ".exe" if platform.system() == "Windows" else ""
    local_tool = ROOT / ".venv" / "Scripts" / f"{name}{suffix}"
    if local_tool.exists():
        return str(local_tool)
    return None


def read_pe_machine_bits(path: Path) -> int | None:
    if platform.system() != "Windows":
        return None
    with path.open("rb") as fp:
        header = fp.read(64)
        if len(header) < 64 or header[:2] != b"MZ":
            return None
        pe_offset = int.from_bytes(header[0x3C:0x40], "little")
        fp.seek(pe_offset)
        pe_header = fp.read(6)
        if len(pe_header) < 6 or pe_header[:4] != b"PE\0\0":
            return None
        machine = int.from_bytes(pe_header[4:6], "little")
        return WINDOWS_MACHINE_BITS.get(machine)


def write_mingw_native_file(path: Path, arch: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if arch == "x64":
        mingw_root = Path(os.environ.get("MINGW64_PREFIX", r"C:\msys64\mingw64"))
        cpu_family = "x86_64"
    else:
        mingw_root = Path(os.environ.get("MINGW32_PREFIX", r"C:\msys64\mingw32"))
        cpu_family = "x86"

    bin_dir = mingw_root / "bin"
    cpp = bin_dir / "c++.exe"
    c = bin_dir / "gcc.exe"
    ar = bin_dir / "gcc-ar.exe"
    pkg_config = bin_dir / "pkg-config.exe"

    missing = [tool for tool in [cpp, c, ar, pkg_config] if not tool.exists()]
    if missing:
        names = ", ".join(str(tool) for tool in missing)
        print(f"ERROR: missing {arch} MinGW tools: {names}", file=sys.stderr)
        sys.exit(1)

    path.write_text(
        "\n".join(
            [
                "[binaries]",
                f"c = '{c.as_posix()}'",
                f"cpp = '{cpp.as_posix()}'",
                f"ar = '{ar.as_posix()}'",
                f"pkg-config = '{pkg_config.as_posix()}'",
                "",
                "[host_machine]",
                "system = 'windows'",
                f"cpu_family = '{cpu_family}'",
                f"cpu = '{cpu_family}'",
                "endian = 'little'",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return bin_dir


def build_windows_premake(source_dir: Path, arch: str) -> Path:
    make = tool_path("make")
    bash = tool_path("bash")
    premake = source_dir / "premake5.exe"
    makefile = source_dir / "build" / "Makefile"

    if not makefile.exists():
        if not premake.exists():
            if not bash:
                print("ERROR: bash not found; cannot install premake5", file=sys.stderr)
                sys.exit(1)
            run([bash, "scripts/install-premake5.sh", "windows"], cwd=str(source_dir))
        run([str(premake), "gmake2"], cwd=str(source_dir))

    if not make:
        print("ERROR: make not found; install MSYS2 make or add it to PATH", file=sys.stderr)
        sys.exit(1)

    config = "Release_x64" if arch == "x64" else "Release_Win32"
    run([make, "-C", "build", "ocgcoreshared", f"config={config}"], cwd=str(source_dir))

    output_arch = "x64" if arch == "x64" else "x86"
    lib = source_dir / "bin" / output_arch / "Release" / "ocgcore.dll"
    if not lib.exists():
        lib = source_dir / "bin" / output_arch / "release" / "ocgcore.dll"
    if not lib.exists():
        print(f"ERROR: premake output not found: {lib}", file=sys.stderr)
        sys.exit(1)
    return lib


def run(cmd, **kwargs):
    print(f"  $ {' '.join(str(c) for c in cmd)}")
    result = subprocess.run(cmd, **kwargs)
    if result.returncode != 0:
        print(f"Command failed with exit code {result.returncode}", file=sys.stderr)
        sys.exit(1)
    return result


def remove_tree(path: Path):
    def onerror(func, target, _exc_info):
        os.chmod(target, 0o700)
        func(target)

    shutil.rmtree(path, onerror=onerror)


def main():
    parser = argparse.ArgumentParser(description="Build ocgcore shared library")
    parser.add_argument("--tag", default=DEFAULT_TAG, help="Git tag/branch to checkout")
    parser.add_argument(
        "--arch",
        choices=["x64", "x86"],
        default="x64",
        help="Windows target architecture. Defaults to x64.",
    )
    parser.add_argument("--clean", action="store_true", help="Clean build directory first")
    args = parser.parse_args()

    required_tools = ["git"]
    if platform.system() != "Windows":
        required_tools.extend(["meson", "ninja"])
    tools = {tool: tool_path(tool) for tool in required_tools}
    for tool, path in tools.items():
        if not path:
            print(f"ERROR: {tool} not found in PATH", file=sys.stderr)
            sys.exit(1)

    source_dir = BUILD_DIR / "source"

    if args.clean and BUILD_DIR.exists():
        remove_tree(BUILD_DIR)

    # Clone or update source
    if not source_dir.exists():
        print(f"Cloning EDOPro-core ({args.tag})...")
        BUILD_DIR.mkdir(parents=True, exist_ok=True)
        run(["git", "clone", "--depth", "1", "--branch", args.tag, REPO_URL, str(source_dir)])
    else:
        print("Updating existing source...")
        run(["git", "fetch", "origin", args.tag], cwd=str(source_dir))
        run(["git", "checkout", f"origin/{args.tag}"], cwd=str(source_dir))

    if platform.system() == "Windows":
        lib_found = build_windows_premake(source_dir, args.arch)
        bits = read_pe_machine_bits(lib_found)
        expected_bits = 64 if args.arch == "x64" else 32
        if bits and bits != expected_bits:
            print(
                f"ERROR: built {lib_found.name} is {bits}-bit, expected {expected_bits}-bit",
                file=sys.stderr,
            )
            sys.exit(1)
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        dest = OUTPUT_DIR / "ocgcore.dll"
        shutil.copy2(lib_found, dest)
        strip = tool_path("strip")
        if strip:
            run([strip, str(dest)])
        print(f"Built: {dest} ({dest.stat().st_size / 1024:.0f} KB, {expected_bits}-bit)")
        return

    build_dir = BUILD_DIR / "build"
    build_dir.mkdir(exist_ok=True)
    meson_setup = [
        "meson",
        "setup",
        str(build_dir),
        str(source_dir),
        "--buildtype=release",
        "--default-library=shared",
    ]

    if platform.system() == "Windows":
        native_file = BUILD_DIR / f"mingw-{args.arch}.ini"
        mingw_bin = write_mingw_native_file(native_file, args.arch)
        os.environ["PATH"] = f"{mingw_bin}{os.pathsep}{os.environ.get('PATH', '')}"
        meson_setup.extend(["--native-file", str(native_file)])

    if not (build_dir / "build.ninja").exists():
        print("Configuring Meson...")
        run([tools["meson"], *meson_setup[1:]])
    else:
        run([tools["meson"], *meson_setup[1:], "--reconfigure"])

    print("Building...")
    run([tools["meson"], "compile", "-C", str(build_dir)])

    # Copy output
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    system = platform.system()
    if system == "Windows":
        runtime_lib_name = "ocgcore.dll"
        candidate_names = ["ocgcore.dll", "libocgcore.dll"]
    elif system == "Darwin":
        runtime_lib_name = "libocgcore.dylib"
        candidate_names = [runtime_lib_name]
    else:
        runtime_lib_name = "libocgcore.so"
        candidate_names = [runtime_lib_name]

    lib_found = next((p for name in candidate_names for p in build_dir.rglob(name)), None)

    if lib_found:
        if system == "Windows":
            bits = read_pe_machine_bits(lib_found)
            expected_bits = 64 if args.arch == "x64" else 32
            if bits and bits != expected_bits:
                print(
                    f"ERROR: built {lib_found.name} is {bits}-bit, expected {expected_bits}-bit",
                    file=sys.stderr,
                )
                sys.exit(1)
        dest = OUTPUT_DIR / runtime_lib_name
        shutil.copy2(lib_found, dest)
        print(f"Built: {dest} ({dest.stat().st_size / 1024:.0f} KB)")
    else:
        print(f"ERROR: none of {', '.join(candidate_names)} found in build output", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
