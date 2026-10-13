"""Download / install helpers for add-on apps (phpMyAdmin, Composer, Node.js, anything from a zip URL)."""
from __future__ import annotations

import json
import platform
import secrets
import shutil
import tempfile
import urllib.request
import zipfile
from pathlib import Path
from typing import Callable, Optional

import core

Progress = Optional[Callable[[int, int], None]]
UA = {"User-Agent": "Stackyard/1.0 (+local dev environment manager)"}

PHPMYADMIN_URL = "https://www.phpmyadmin.net/downloads/phpMyAdmin-latest-all-languages.zip"
COMPOSER_URL = "https://getcomposer.org/download/latest-stable/composer.phar"
NODE_INDEX_URL = "https://nodejs.org/dist/index.json"


def download(url: str, dest: Path, progress: Progress = None) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers=UA)
    try:
        with urllib.request.urlopen(req, timeout=60) as r, open(dest, "wb") as f:
            total = int(r.headers.get("Content-Length") or 0)
            done = 0
            while True:
                chunk = r.read(1 << 16)
                if not chunk:
                    break
                f.write(chunk)
                done += len(chunk)
                if progress:
                    progress(done, total)
            if progress:
                progress(done, done)
    except OSError as e:
        raise core.StackyardError(f"Download failed ({url}): {e}")


def extract_to(zip_path: Path, target: Path, replace: bool = False) -> None:
    """Extract a zip into target; a single top-level folder inside the zip is flattened."""
    tmp = Path(tempfile.mkdtemp(prefix=".stackyard_", dir=core.BASE_DIR))
    try:
        try:
            with zipfile.ZipFile(zip_path) as z:
                z.extractall(tmp)
        except zipfile.BadZipFile:
            raise core.StackyardError("The downloaded file is not a valid zip archive.")
        items = list(tmp.iterdir())
        src = items[0] if len(items) == 1 and items[0].is_dir() else tmp
        if target.exists():
            if not replace:
                raise core.StackyardError(f"{target} already exists.")
            shutil.rmtree(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(target))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _download_zip(url: str, progress: Progress) -> Path:
    tmp = Path(tempfile.mkdtemp(prefix=".stackyard_dl_", dir=core.BASE_DIR)) / "download.zip"
    download(url, tmp, progress)
    return tmp


def _cleanup(zip_path: Path) -> None:
    shutil.rmtree(zip_path.parent, ignore_errors=True)


# ------------------------------------------------------------------ phpMyAdmin
def install_phpmyadmin(cfg: core.Config, log, progress: Progress = None) -> None:
    target = core.WWW_DIR / "phpmyadmin"
    old_cfg = None
    if (target / "config.inc.php").exists():
        old_cfg = (target / "config.inc.php").read_bytes()
    log("Downloading phpMyAdmin (latest)...")
    z = _download_zip(PHPMYADMIN_URL, progress)
    try:
        log("Extracting...")
        extract_to(z, target, replace=True)
    finally:
        _cleanup(z)
    if old_cfg:
        (target / "config.inc.php").write_bytes(old_cfg)
        log("Kept your existing config.inc.php")
    else:
        secret = secrets.token_hex(16)  # exactly 32 characters, as phpMyAdmin requires
        (target / "config.inc.php").write_text(
            "<?php\n"
            f"$cfg['blowfish_secret'] = '{secret}';\n"
            "$i = 0;\n$i++;\n"
            "$cfg['Servers'][$i]['auth_type'] = 'cookie';\n"
            "$cfg['Servers'][$i]['host'] = '127.0.0.1';\n"
            "$cfg['Servers'][$i]['compress'] = false;\n"
            "$cfg['Servers'][$i]['AllowNoPassword'] = true;\n"
            "$cfg['TempDir'] = __DIR__ . '/tmp';\n",
            encoding="utf-8",
        )
    (target / "tmp").mkdir(exist_ok=True)
    php = cfg.active_dir("php")
    if php:
        enabled = core.enable_php_extensions(php, ["mysqli", "mbstring", "openssl", "curl", "zip", "gd"])
        if enabled:
            log("Enabled PHP extensions for phpMyAdmin: " + ", ".join(enabled) + " (restart Apache to apply)")
    log("phpMyAdmin installed -> http://localhost/phpmyadmin/  (user: root, empty password)")


# ------------------------------------------------------------------ Composer
def install_composer(cfg: core.Config, log, progress: Progress = None) -> None:
    folder = core.composer_dir()
    folder.mkdir(parents=True, exist_ok=True)
    log("Downloading composer.phar...")
    download(COMPOSER_URL, folder / "composer.phar", progress)
    # The wrapper uses the ACTIVE php through the 'current' junction, so it follows version switches.
    core.write_composer_wrapper(folder)
    php = cfg.active_dir("php")
    if php:
        enabled = core.enable_php_extensions(php, ["openssl", "curl", "mbstring", "fileinfo", "zip"])
        if enabled:
            log("Enabled PHP extensions for Composer: " + ", ".join(enabled))
    log(f"Composer installed in {folder}. Use 'Add to PATH' on the Versions tab, then run: composer --version")


# ------------------------------------------------------------------ Node.js
def node_versions() -> list[tuple[str, str]]:
    """[(version, lts-name-or-'')] newest first, only builds that have a Windows zip."""
    arch = "win-arm64-zip" if "ARM" in platform.machine().upper() else "win-x64-zip"
    try:
        with urllib.request.urlopen(urllib.request.Request(NODE_INDEX_URL, headers=UA), timeout=30) as r:
            data = json.load(r)
    except OSError as e:
        raise core.StackyardError(f"Cannot fetch the Node.js version list: {e}")
    out = []
    for v in data:
        if arch in v.get("files", []):
            out.append((v["version"], v["lts"] if isinstance(v.get("lts"), str) else ""))
    return out


def install_node(cfg: core.Config, log, progress: Progress, version: str) -> None:
    arch = "win-arm64" if "ARM" in platform.machine().upper() else "win-x64"
    target = core.tools_dir() / f"nodejs-{version.lstrip('v')}"
    if target.exists():
        raise core.StackyardError(f"{target.name} is already installed.")
    url = f"https://nodejs.org/dist/{version}/node-{version}-{arch}.zip"
    log(f"Downloading Node.js {version}...")
    z = _download_zip(url, progress)
    try:
        log("Extracting...")
        extract_to(z, target)
    finally:
        _cleanup(z)
    if not cfg.data["active"].get("nodejs"):
        core.activate(cfg, "nodejs", target.name)
    log(f"Node.js {version} installed in {target.name}. Activate it on the Versions tab.")


# ------------------------------------------------------------------ generic
def install_from_url(cfg: core.Config, log, progress: Progress, name: str, url: str) -> None:
    """Download a zip and unpack it to BASE/<name>. Use e.g. 'php-8.4.1' to add another PHP version."""
    rel = Path(name)
    if rel.is_absolute() or ".." in rel.parts:
        raise core.StackyardError("The target folder must be a simple relative name.")
    target = core.tools_dir() / rel
    log(f"Downloading {url} ...")
    z = _download_zip(url, progress)
    try:
        log(f"Extracting to {target} ...")
        extract_to(z, target)
    finally:
        _cleanup(z)
    log(f"Installed to {target}. If it is a tool version (httpd-*, php-*, mysql-*, nodejs-*) rescan on the Versions tab.")
