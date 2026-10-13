"""Install the Stackyard git hooks (a commit-msg hook that runs versioning.py).

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


def main() -> int:
    hooks = hooks_dir()
    hooks.mkdir(parents=True, exist_ok=True)
    hook = hooks / "commit-msg"

    python = Path(sys.executable).as_posix()
    script = (ROOT / "versioning.py").as_posix()
    hook.write_text(
        "#!/bin/sh\n"
        "# Installed by install_hooks.py - bumps the version on each commit.\n"
        f'"{python}" "{script}" hook "$1"\n',
        encoding="utf-8",
    )
    try:
        os.chmod(hook, 0o755)
    except OSError:
        pass

    print(f"Installed commit-msg hook: {hook}")
    print(f"Interpreter: {python}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
