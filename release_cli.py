#!/usr/bin/env python3
"""MacroForge release command line.

This is the clean command surface for local release work.  It wraps the
existing battle-tested scripts, while adding faster no-rebuild publish and
repair paths for common release mistakes.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from bump_version import bump_version
from build_helper import release_notes_from_git
from release_doctor import REPO, release_assets, validate_release
from release_preflight import read_version, validate_release as validate_local_release


ROOT = Path(__file__).resolve().parent
GENERATED_FILES = (
    "debug.log",
    "macroforge_session.json",
    "test_dl.zip",
    "test_download.zip",
    "update_health.json",
    "upload_release.bat",
    "upload_to_github.py",
)
GENERATED_DIRS = (
    "__pycache__",
    ".pytest_cache",
)
BUILD_ARTIFACT_DIRS = (
    "build",
    "installer",
)


def run(cmd: list[str] | str, *, check: bool = True, stdin=None) -> subprocess.CompletedProcess:
    shell = isinstance(cmd, str)
    print("+", cmd if shell else " ".join(cmd))
    result = subprocess.run(cmd, cwd=ROOT, shell=shell, stdin=stdin)
    if check and result.returncode != 0:
        raise SystemExit(result.returncode)
    return result


def capture(cmd: list[str], *, check: bool = True) -> subprocess.CompletedProcess:
    result = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    if check and result.returncode != 0:
        message = (result.stderr or result.stdout or "command failed").strip()
        print(message)
        raise SystemExit(result.returncode)
    return result


def git_branch() -> str:
    return capture(["git", "branch", "--show-current"], check=False).stdout.strip()


def git_dirty() -> bool:
    return bool(capture(["git", "status", "--porcelain"], check=False).stdout.strip())


def release_exists(version: str, repo: str) -> bool:
    result = capture(["gh", "release", "view", f"v{version}", "--repo", repo], check=False)
    return result.returncode == 0


def print_asset_table(version: str, repo: str) -> None:
    for asset in release_assets(ROOT, version):
        exists = asset.path.exists()
        size = asset.path.stat().st_size if exists else 0
        status = "OK" if exists and size > 0 else "MISSING"
        url = asset.expected_url(version, repo) if asset.manifest_key else ""
        print(f"  {status:7} {asset.name:32} {size:>12} {url}")


def cmd_status(args: argparse.Namespace) -> int:
    version = args.version or read_version(ROOT)
    print(f"Version : {version}")
    print(f"Branch  : {git_branch() or 'unknown'}")
    print(f"Dirty   : {'yes' if git_dirty() else 'no'}")
    print(f"Release : {'exists' if release_exists(version, args.repo) else 'not published'}")
    print("Assets:")
    print_asset_table(version, args.repo)
    try:
        manifest = json.loads((ROOT / "update.json").read_text(encoding="utf-8"))
        print("Manifest:")
        print(f"  url     : {manifest.get('url', '')}")
        print(f"  zip_url : {manifest.get('zip_url', '')}")
    except Exception as exc:
        print(f"Manifest: unreadable ({exc})")
    return 0


def cmd_test(args: argparse.Namespace) -> int:
    cmd = [sys.executable, "-m", "pytest"]
    if args.pytest_args:
        cmd.extend(args.pytest_args)
    run(cmd)
    return 0


def cmd_build(args: argparse.Namespace) -> int:
    flags: list[str] = []
    if args.fast:
        flags.append("--fast")
    if args.no_zip:
        flags.append("--no-zip")
    if args.no_smoke:
        flags.append("--no-smoke")
    if args.no_installer:
        flags.append("--no-installer")
    if args.clean_release:
        flags.append("--clean-release")
    run(["cmd", "/c", "build.bat", *flags], stdin=subprocess.DEVNULL)
    return 0


def _clean_targets(include_build: bool = False) -> list[Path]:
    targets: list[Path] = []
    for name in GENERATED_FILES:
        path = ROOT / name
        if path.exists():
            targets.append(path)
    for name in GENERATED_DIRS:
        targets.extend(path for path in ROOT.rglob(name) if path.exists())
    if include_build:
        for name in BUILD_ARTIFACT_DIRS:
            path = ROOT / name
            if path.exists():
                targets.append(path)
    return sorted(set(targets), key=lambda p: str(p).lower())


def _assert_inside_root(path: Path) -> None:
    root = ROOT.resolve()
    resolved = path.resolve()
    if resolved != root and root not in resolved.parents:
        raise SystemExit(f"Refusing to clean outside repository: {resolved}")


def cmd_clean(args: argparse.Namespace) -> int:
    targets = _clean_targets(include_build=args.include_build)
    if not targets:
        print("[OK] No generated clutter found")
        return 0
    for path in targets:
        _assert_inside_root(path)
        rel = path.relative_to(ROOT)
        if args.dry_run:
            print(f"[DRY-RUN] Would remove {rel}")
            continue
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()
        print(f"[CLEAN] Removed {rel}")
    return 0


def cmd_bump(args: argparse.Namespace) -> int:
    old, new = bump_version(args.part, ROOT / "version.py")
    print(f"Bumped {old} -> {new}")
    return 0


def cmd_preflight(args: argparse.Namespace) -> int:
    errors, warnings = validate_local_release(ROOT, require_clean=not args.allow_dirty)
    for warning in warnings:
        print(f"[WARN] {warning}")
    if errors:
        for error in errors:
            print(f"[ERROR] {error}")
        return 1
    print("[OK] Release preflight passed")
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    version = args.version or read_version(ROOT)
    errors, warnings, _release = validate_release(ROOT, version, args.repo, online=not args.offline)
    for warning in warnings:
        print(f"[WARN] {warning}")
    if errors:
        for error in errors:
            print(f"[ERROR] {error}")
        return 1
    scope = "local" if args.offline else "published"
    print(f"[OK] Release doctor passed for {scope} v{version}")
    return 0


def cmd_repair(args: argparse.Namespace) -> int:
    version = args.version or read_version(ROOT)
    run([sys.executable, "release_doctor.py", version, "--repo", args.repo, "--repair"])
    return 0


def ensure_release(version: str, repo: str, notes_file: Path | None = None) -> None:
    if release_exists(version, repo):
        print(f"[PUBLISH] Reusing existing release v{version}")
        return
    notes_arg = ["--notes-file", str(notes_file)] if notes_file else ["--notes", release_notes_from_git(version)]
    run([
        "gh",
        "release",
        "create",
        f"v{version}",
        "--repo",
        repo,
        "--title",
        f"MacroForge v{version}",
        *notes_arg,
    ])


def upload_release_assets(version: str, repo: str) -> None:
    assets = release_assets(ROOT, version)
    missing = [asset.path for asset in assets if not asset.path.exists()]
    if missing:
        for path in missing:
            print(f"[ERROR] Missing local asset: {path}")
        raise SystemExit(1)
    run(["gh", "release", "upload", f"v{version}", "--repo", repo, "--clobber", *[str(asset.path) for asset in assets]])


def cmd_publish(args: argparse.Namespace) -> int:
    version = args.version or read_version(ROOT)
    if not args.skip_preflight:
        code = cmd_preflight(argparse.Namespace(allow_dirty=args.allow_dirty))
        if code:
            return code
    if args.dry_run:
        print(f"[DRY-RUN] Would publish v{version} to {args.repo}")
        print_asset_table(version, args.repo)
        return 0
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, suffix=".md") as handle:
        notes_path = Path(handle.name)
        handle.write(release_notes_from_git(version))
        handle.write("\n")
    try:
        ensure_release(version, args.repo, notes_path)
        upload_release_assets(version, args.repo)
    finally:
        try:
            notes_path.unlink()
        except OSError:
            pass
    return cmd_doctor(argparse.Namespace(version=version, repo=args.repo, offline=False))


def cmd_full(args: argparse.Namespace) -> int:
    flags = ["--bump", args.bump]
    if args.fast:
        flags.append("--fast")
    if args.no_smoke:
        flags.append("--no-smoke")
    if args.no_installer:
        flags.append("--no-installer")
    run(["cmd", "/c", "release.bat", *flags], stdin=subprocess.DEVNULL)
    return 0


def cmd_commit(args: argparse.Namespace) -> int:
    if not git_dirty():
        print("[OK] Working tree clean; nothing to commit")
        return 0
    run(["git", "add", "-A"])
    run(["git", "commit", "-m", args.message])
    return 0


def cmd_push(args: argparse.Namespace) -> int:
    branch = args.branch or git_branch() or "main"
    run(["git", "push", "origin", branch])
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="MacroForge release workflow helper")
    parser.set_defaults(func=lambda _args: 2)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("status", help="Show version, branch, manifest, and local assets")
    p.add_argument("version", nargs="?")
    p.add_argument("--repo", default=REPO)
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("test", help="Run pytest")
    p.add_argument("pytest_args", nargs=argparse.REMAINDER)
    p.set_defaults(func=cmd_test)

    p = sub.add_parser("build", help="Build local artifacts")
    p.add_argument("--fast", action="store_true")
    p.add_argument("--no-zip", action="store_true")
    p.add_argument("--no-smoke", action="store_true")
    p.add_argument("--no-installer", action="store_true")
    p.add_argument("--clean-release", action="store_true")
    p.set_defaults(func=cmd_build)

    p = sub.add_parser("clean", help="Remove generated local clutter")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--include-build", action="store_true", help="Also remove build/ and installer/")
    p.set_defaults(func=cmd_clean)

    p = sub.add_parser("bump", help="Bump version.py")
    p.add_argument("part", choices=["major", "minor", "patch"], nargs="?", default="patch")
    p.set_defaults(func=cmd_bump)

    p = sub.add_parser("preflight", help="Validate local release artifacts")
    p.add_argument("--allow-dirty", action="store_true")
    p.set_defaults(func=cmd_preflight)

    p = sub.add_parser("doctor", help="Validate local or published release")
    p.add_argument("version", nargs="?")
    p.add_argument("--repo", default=REPO)
    p.add_argument("--offline", action="store_true")
    p.set_defaults(func=cmd_doctor)

    p = sub.add_parser("repair", help="Upload current local assets to an existing release")
    p.add_argument("version", nargs="?")
    p.add_argument("--repo", default=REPO)
    p.set_defaults(func=cmd_repair)

    p = sub.add_parser("publish", help="Publish/upload current build without rebuilding")
    p.add_argument("version", nargs="?")
    p.add_argument("--repo", default=REPO)
    p.add_argument("--allow-dirty", action="store_true")
    p.add_argument("--skip-preflight", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(func=cmd_publish)

    p = sub.add_parser("full", help="Run the existing full release pipeline")
    p.add_argument("--bump", choices=["major", "minor", "patch", "none"], default="patch")
    p.add_argument("--fast", action="store_true")
    p.add_argument("--no-smoke", action="store_true")
    p.add_argument("--no-installer", action="store_true")
    p.set_defaults(func=cmd_full)

    p = sub.add_parser("commit", help="Commit all current changes")
    p.add_argument("-m", "--message", default="Update release tooling")
    p.set_defaults(func=cmd_commit)

    p = sub.add_parser("push", help="Push the current branch")
    p.add_argument("branch", nargs="?")
    p.set_defaults(func=cmd_push)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    result = args.func(args)
    return int(result or 0)


if __name__ == "__main__":
    raise SystemExit(main())
