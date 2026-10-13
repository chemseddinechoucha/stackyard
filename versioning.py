"""Stackyard versioning helper and commit-msg hook.

Every commit gets a release number, chosen from the commit message using
Conventional Commits:

    feat: ...            -> minor bump   (0.1.1 -> 0.2.0)
    fix: ...             -> patch bump   (0.1.1 -> 0.1.2)
    ...!: ... or
    BREAKING CHANGE: ... -> major bump   (0.1.1 -> 1.0.0)
    anything else        -> patch bump

On each commit it bumps ``VERSION``, moves the CHANGELOG ``[Unreleased]`` notes
(plus this commit) into a new dated release section, refreshes the README version
badge and stages those three files so they are part of the commit.

Git writes the commit's tree *before* the ``commit-msg`` hook runs, so a hook
cannot add files to the commit it is invoked for. The hook therefore works in two
passes: the first run bumps and stages the version files and pauses the commit;
running the same commit again includes them and the commit goes through. Running
``bump`` explicitly stages the files too, so the following commit just picks them
up.

Usage:
    python versioning.py current
    python versioning.py preview "feat(ui): dark mode"
    python versioning.py bump minor "optional message"
    python versioning.py hook .git/COMMIT_EDITMSG              # commit-msg hook
    python versioning.py prepare .git/COMMIT_EDITMSG message   # prepare-commit-msg hook

Add ``[skip version]`` anywhere in the commit message to keep the version as is.
Merges are skipped automatically. Amendments are skipped when Git reports the
amend to the ``prepare-commit-msg`` hook (``git commit --amend`` without ``-m``);
``git commit --amend -m "..."`` looks like a normal commit to Git, so add
``[skip version]`` there to avoid a bump.
"""
from __future__ import annotations

import re
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VERSION_FILE = ROOT / "VERSION"
CHANGELOG_FILE = ROOT / "CHANGELOG.md"
README_FILE = ROOT / "README.md"

README_MARK_BEGIN = "<!-- version:start -->"
README_MARK_END = "<!-- version:end -->"

# Conventional-commit type -> Keep a Changelog category.
CATEGORY = {
    "feat": "Added",
    "fix": "Fixed",
    "perf": "Changed",
    "refactor": "Changed",
    "style": "Changed",
    "chore": "Changed",
    "docs": "Documentation",
    "test": "Tests",
    "build": "Build",
    "ci": "Build",
    "revert": "Reverted",
}
HEADER_RE = re.compile(
    r"^(?P<type>[A-Za-z]+)(?:\((?P<scope>[^)]*)\))?(?P<bang>!)?:\s*(?P<desc>.+?)\s*$"
)
LINK_RE = re.compile(r"^\[(?P<name>[^\]]+)\]:\s+(?P<url>https?://\S+)\s*$")


# --------------------------------------------------------------------- version
def read_version() -> str:
    if VERSION_FILE.is_file():
        v = VERSION_FILE.read_text(encoding="utf-8").strip()
        if re.fullmatch(r"\d+\.\d+\.\d+", v):
            return v
    return "0.0.0"


def write_version(version: str) -> None:
    VERSION_FILE.write_text(version + "\n", encoding="utf-8")


def bump(version: str, kind: str) -> str:
    major, minor, patch = (int(p) for p in version.split("."))
    if kind == "major":
        return f"{major + 1}.0.0"
    if kind == "minor":
        return f"{major}.{minor + 1}.0"
    return f"{major}.{minor}.{patch + 1}"


# --------------------------------------------------------------------- message
def classify(message: str) -> tuple[str, str, str]:
    """Return (bump kind, changelog category, changelog entry) for a commit message."""
    lines = [ln for ln in message.splitlines() if ln.strip() and not ln.lstrip().startswith("#")]
    subject = lines[0].strip() if lines else "update"
    full = "\n".join(lines)

    breaking = "BREAKING CHANGE" in full or "BREAKING-CHANGE" in full.upper()
    m = HEADER_RE.match(subject)
    if m:
        ctype = m.group("type").lower()
        scope = (m.group("scope") or "").strip()
        desc = m.group("desc").strip()
        breaking = breaking or bool(m.group("bang"))
        category = CATEGORY.get(ctype, "Changed")
        kind = "major" if breaking else ("minor" if ctype == "feat" else "patch")
    else:
        ctype, scope, desc, category, kind = None, "", subject, "Changed", "patch"

    prefix = f"**{scope}:** " if scope else ""
    if breaking:
        prefix = "**BREAKING** " + prefix
    return kind, category, f"{prefix}{desc}"


# --------------------------------------------------------------------- git
def git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout


def git_dir() -> Path:
    try:
        out = git("rev-parse", "--git-dir").strip()
        return (ROOT / out).resolve()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return ROOT / ".git"


def pending_file() -> Path:
    """Records a bump that has been staged but not yet committed (see run_hook)."""
    return git_dir() / "STACKYARD_VERSION_PENDING"


def write_pending(version: str) -> None:
    try:
        pending_file().write_text(version + "\n", encoding="utf-8")
    except OSError:
        pass


def clear_pending() -> None:
    try:
        pending_file().unlink()
    except OSError:
        pass


def skip_file() -> Path:
    """Set by the prepare-commit-msg hook for commits that must not bump."""
    return git_dir() / "STACKYARD_VERSION_SKIP"


def write_skip() -> None:
    try:
        skip_file().write_text("skip\n", encoding="utf-8")
    except OSError:
        pass


def clear_skip() -> None:
    try:
        skip_file().unlink()
    except OSError:
        pass


def repo_url() -> str:
    try:
        url = git("config", "--get", "remote.origin.url").strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "https://example.com"
    if not url:
        return "https://example.com"
    if url.startswith("git@"):                       # git@host:owner/repo.git
        url = "https://" + url[4:].replace(":", "/", 1)
    url = re.sub(r"\.git$", "", url.rstrip("/"))
    return url


# --------------------------------------------------------------------- changelog
def _add_entry(body: str, category: str, entry: str) -> str:
    lines = [ln for ln in body.strip("\n").split("\n")] if body.strip() else []
    heading = f"### {category}"
    if heading in lines:
        idx = lines.index(heading)
        if idx + 1 < len(lines) and not lines[idx + 1].strip():
            lines.insert(idx + 2, f"- {entry}")
        else:
            lines.insert(idx + 1, "")
            lines.insert(idx + 2, f"- {entry}")
    else:
        if lines and lines[-1].strip():
            lines.append("")
        lines += [heading, "", f"- {entry}"]
    return "\n".join(lines).strip("\n")


def update_changelog(version: str, category: str, entry: str) -> None:
    text = CHANGELOG_FILE.read_text(encoding="utf-8") if CHANGELOG_FILE.is_file() else "# Changelog\n"

    # Pull the link-reference lines out so they do not become part of a section body.
    raw_lines = text.split("\n")
    links: list[tuple[str, str]] = []
    content_lines: list[str] = []
    for ln in raw_lines:
        m = LINK_RE.match(ln)
        if m:
            links.append((m.group("name"), m.group("url")))
        else:
            content_lines.append(ln)
    text = "\n".join(content_lines)

    # Split intro from the "## ..." sections.
    lines = text.split("\n")
    first = next((i for i, ln in enumerate(lines) if ln.startswith("## ")), None)
    intro = "\n".join(lines[:first]).strip("\n") if first is not None else text.strip("\n")

    sections: list[tuple[str, list[str]]] = []
    if first is not None:
        head, body = None, []
        for ln in lines[first:]:
            if ln.startswith("## "):
                if head is not None:
                    sections.append((head, body))
                head, body = ln, []
            else:
                body.append(ln)
        if head is not None:
            sections.append((head, body))

    # Fold any [Unreleased] body into the new release.
    unreleased_body = ""
    remaining = []
    for head, body in sections:
        if head.strip().lower() in ("## [unreleased]", "## unreleased"):
            unreleased_body = "\n".join(body)
        else:
            remaining.append((head, body))

    new_body = _add_entry(unreleased_body, category, entry)
    new_head = f"## [{version}] - {date.today().isoformat()}"
    sections = [(new_head, new_body.split("\n"))] + remaining

    parts = [intro]
    for head, body in sections:
        b = "\n".join(body).strip("\n")
        parts.append(head if not b else f"{head}\n\n{b}")
    out = "\n\n".join(p for p in parts if p is not None).rstrip("\n") + "\n"

    # Rebuild the link references: drop the stale [Unreleased], add this version.
    links = [pair for pair in links if pair[0].lower() != "unreleased"]
    url = repo_url()
    if not any(name.lower() == version.lower() for name, _ in links):
        links.append((version, f"{url}/releases/tag/v{version}"))
    out += "\n" + "\n".join(f"[{name}]: {link}" for name, link in links) + "\n"

    CHANGELOG_FILE.write_text(out, encoding="utf-8")


# --------------------------------------------------------------------- readme
def update_readme(version: str) -> None:
    badge = f"![version](https://img.shields.io/badge/version-{version}-2f6feb)"
    text = README_FILE.read_text(encoding="utf-8") if README_FILE.is_file() else "# Stackyard\n"
    block = f"{README_MARK_BEGIN}\n{badge}\n{README_MARK_END}"

    if README_MARK_BEGIN in text and README_MARK_END in text:
        text = re.sub(
            re.escape(README_MARK_BEGIN) + r".*?" + re.escape(README_MARK_END),
            block, text, flags=re.DOTALL,
        )
    else:                                            # insert right after the first heading
        lines = text.split("\n")
        at = 1 if lines and lines[0].startswith("# ") else 0
        lines[at:at] = ["", block]
        text = "\n".join(lines)

    README_FILE.write_text(text, encoding="utf-8")


# --------------------------------------------------------------------- hook
def release(message: str, dry_run: bool = False, kind_override: str | None = None) -> str:
    old = read_version()
    kind, category, entry = classify(message)
    if kind_override:
        kind = kind_override
    new = bump(old, kind)
    print(f"release {old} -> {new}  ({kind}, changelog: {category})")
    if not dry_run:
        write_version(new)
        update_changelog(new, category, entry)
        update_readme(new)
        git("add", "VERSION", "CHANGELOG.md", "README.md")
    return new


def prepare_commit_msg(source: str) -> int:
    """prepare-commit-msg hook: flag commits that must not bump.

    Git passes the message source as the second hook argument: ``commit <sha>``
    for ``--amend``/``-c``/``-C`` and ``merge``/``squash`` for merges. A normal
    commit clears the flag so a stale one cannot leak into the next commit.
    """
    if source.startswith("commit") or source in ("merge", "squash"):
        write_skip()
    else:
        clear_skip()
    return 0


def run_hook(msg_path: str, dry_run: bool = False) -> int:
    try:
        message = Path(msg_path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return 0
    subject = next((ln for ln in message.splitlines() if ln.strip() and not ln.startswith("#")), "")
    if subject.startswith("Merge ") or "[skip version]" in message.lower():
        return 0
    if skip_file().exists():                          # amending a commit must not bump again
        clear_skip()
        return 0

    if dry_run:
        release(message, dry_run=True)
        return 0

    # Git writes the commit's tree *before* the commit-msg hook runs, so files
    # staged here are not part of this commit. Work in two passes instead: the
    # first run bumps and stages the version files and pauses the commit; running
    # the same commit again has them already staged, so it goes through.
    marker = pending_file()
    if marker.exists():
        try:
            expected = marker.read_text(encoding="utf-8").strip()
        except OSError:
            expected = ""
        clear_pending()
        if expected and read_version() == expected:
            return 0                                  # second pass: include the bump

    new = release(message)
    write_pending(new)
    print(
        f"Version bumped to {new} and staged, but the commit was paused: Git builds "
        "the commit before this hook runs, so the new files are not in it yet.\n"
        "Run the same commit again to include them.",
        file=sys.stderr,
    )
    return 1


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 0
    cmd, rest = argv[0], argv[1:]
    if cmd == "current":
        print(read_version())
    elif cmd == "preview":
        kind, category, entry = classify(rest[0] if rest else "")
        print(f"{read_version()} -> {bump(read_version(), kind)}  ({kind}, {category})\n- {entry}")
    elif cmd == "bump":
        kind = rest[0] if rest else "patch"
        if kind not in ("major", "minor", "patch"):
            print(f"unknown bump kind: {kind!r} (expected major, minor or patch)", file=sys.stderr)
            return 1
        release(rest[1] if len(rest) > 1 else f"chore: {kind} release", kind_override=kind)
        write_pending(read_version())                 # keep the next commit from bumping again
    elif cmd == "hook":
        return run_hook(rest[0] if rest else ".git/COMMIT_EDITMSG",
                        dry_run="--dry-run" in rest)
    elif cmd == "prepare":
        return prepare_commit_msg(rest[1] if len(rest) > 1 else "")
    else:
        print(__doc__)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
