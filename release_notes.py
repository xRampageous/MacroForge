#!/usr/bin/env python3
"""Generate short release notes from recent git history."""
import sys

from build_helper import get_version, release_notes_from_git


if __name__ == "__main__":
    version = sys.argv[1] if len(sys.argv) > 1 else get_version()
    print(release_notes_from_git(version))
