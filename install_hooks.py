"""Install the Stackyard git hooks that run versioning.py.

Installs ``commit-msg`` (bumps the version, two-pass) and
``prepare-commit-msg`` (flags amendments and merges so they do not bump).

Run once per clone:  python install_hooks.py
(or double-click install-hooks.bat).
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def git_dir() -> Path:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            cwd=ROOT, capture_output=True, text=True, check=True,
        ).stdout.strip()
        return (ROOT / out).resolve()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return ROOT / ".git"


def hooks_dir() -> Path:
    try:
        out = subprocess.run(
            ["git", "config", "--get", "core.hooksPath"],
            cwd=ROOT, capture_output=True, text=True, check=True,
        ).stdout.strip()
        if out:
            p = Path(out)
            return (p if p.is_absolute() else ROOT / p).resolve()
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass
    return git_dir() / "hooks"


def _install(path: Path, body: str) -> None:
    path.write_text(body, encoding="utf-8")
    try:
        os.chmod(path, 0o755)
    except OSError:
        pass


def main() -> int:
    hooks = hooks_dir()
    hooks.mkdir(parents=True, exist_ok=True)

    python = Path(sys.executable).as_posix()
    script = (ROOT / "versioning.py").as_posix()

    commit_msg = hooks / "commit-msg"
    _install(commit_msg, (
        "#!/bin/sh\n"
        "# Installed by install_hooks.py - bumps the version on each commit.\n"
        "# Git builds the tree before this hook runs, so the first run pauses the\n"
        "# commit and the second run (same message) includes the bumped files.\n"
        f'"{python}" "{script}" hook "$1"\n'
    ))

    prepare = hooks / "prepare-commit-msg"
    _install(prepare, (
        "#!/bin/sh\n"
        "# Installed by install_hooks.py - tells versioning.py to skip amendments\n"
        "# and merges so they do not bump the version. $2 is the message source:\n"
        "# 'commit <sha>' for --amend/-c/-C, 'merge'/'squash' for merges.\n"
        f'"{python}" "{script}" prepare "$1" "$2"\n'
    ))

    print(f"Installed commit-msg hook:        {commit_msg}")
    print(f"Installed prepare-commit-msg hook: {prepare}")
    print(f"Interpreter: {python}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
