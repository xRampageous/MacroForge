"""Bump version.py. Usage: python bump_version.py [major|minor|patch]"""
import re
import sys
from pathlib import Path

FILE = str(Path(__file__).parent / "version.py")

def bump(version: str, part: str) -> str:
    m = re.match(r'(\d+)\.(\d+)\.(\d+)', version)
    if not m:
        raise ValueError(f"Cannot parse version: {version}")
    major, minor, patch = map(int, m.groups())
    if part == "major":
        major += 1
        minor = 0
        patch = 0
    elif part == "minor":
        minor += 1
        patch = 0
    else:
        patch += 1
    return f"{major}.{minor}.{patch}"


def main():
    part = sys.argv[1] if len(sys.argv) > 1 else "patch"
    if part not in ("major", "minor", "patch"):
        print("Usage: python bump_version.py [major|minor|patch]")
        sys.exit(1)

    with open(FILE, "r", encoding="utf-8") as f:
        content = f.read()

    m = re.search(r'VERSION\s*=\s*"([^"]+)"', content)
    if not m:
        print(f"VERSION not found in {FILE}")
        sys.exit(1)

    old = m.group(1)
    new = bump(old, part)
    content = content.replace(f'VERSION = "{old}"', f'VERSION = "{new}"')

    with open(FILE, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"Bumped {old} -> {new}")


if __name__ == "__main__":
    main()
