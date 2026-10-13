"""Stackyard core logic (no GUI).

Layout it expects (the folder that contains the 'stackyard' folder is BASE_DIR):

    D:\\apps\\
        stackyard\\        <- this application
        httpd-2.4.68\\    <- Apache      (any folder named httpd-*)
        php-8.5.11\\      <- PHP         (any folder named php-*)
        mysql-26.7.0\\    <- MySQL       (mysql-* or mariadb-*)
        nodejs-22.11.0\\  <- Node.js     (nodejs-* or node-*)
        www\\             <- document root
        current\\         <- junctions to the ACTIVE version of each tool (created by Stackyard)
"""
from __future__ import annotations

import codecs
import ctypes
import json
import os
import re
import secrets
import shutil
import socket
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

IS_WIN = os.name == "nt"
NO_WINDOW = 0x08000000 if IS_WIN else 0

APP_DIR = Path(__file__).resolve().parent
SETTINGS_FILE = APP_DIR / "settings.json"   # remembers the chosen root folder
CONFIG_FILE = APP_DIR / "stackyard.json"    # active versions, virtual hosts, custom services


def _migrate_legacy() -> None:
    """The app used to be called DevStack. On the first start, import its saved settings from the
    old folder (a sibling named 'devstack') so versions, virtual hosts and the root folder survive."""
    legacy = APP_DIR.parent / "devstack"
    for dest, sources in ((CONFIG_FILE, (APP_DIR / "devstack.json", legacy / "devstack.json")),
                          (SETTINGS_FILE, (legacy / "settings.json",))):
        if dest.exists():
            continue
        for src in sources:
            if src.is_file() and src.resolve() != dest.resolve():
                try:
                    shutil.copyfile(src, dest)
                except OSError:
                    pass
                break


_migrate_legacy()


def _read_settings() -> dict:
    try:
        data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def saved_base_dir() -> Optional[str]:
    """Root folder chosen by the user in the app (None if never changed)."""
    v = _read_settings().get("base_dir")
    return v if isinstance(v, str) and v else None


def _initial_base():
    """Order: STACKYARD_BASE env var, saved choice, then the folder that contains Stackyard."""
    env = os.environ.get("STACKYARD_BASE")
    if env and Path(env).is_dir():
        return Path(env).resolve(), None
    saved = saved_base_dir()
    if saved:
        if Path(saved).is_dir():
            return Path(saved).resolve(), None
        return APP_DIR.parent.resolve(), (
            f"The saved root folder {saved} is not available (drive disconnected?). "
            f"Using {APP_DIR.parent} for now; your saved choice is kept.")
    return APP_DIR.parent.resolve(), None


BASE_DIR, BASE_WARNING = _initial_base()
WWW_DIR = BASE_DIR / "www"
CURRENT_DIR = BASE_DIR / "current"
RUN_DIR = APP_DIR / "run"
LOG_DIR = APP_DIR / "logs"
HOSTS_FILE = Path(
    os.environ.get("STACKYARD_HOSTS")
    or (Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "drivers" / "etc" / "hosts")
)

MARK_BEGIN = "# >>> Stackyard managed >>>"
MARK_END = "# <<< Stackyard managed <<<"
HOSTS_BEGIN = "# >>> Stackyard hosts >>>"
HOSTS_END = "# <<< Stackyard hosts <<<"

# Names written by the first version (DevStack). Still recognised so an upgrade replaces them cleanly.
OLD_MARK_BEGIN = "# >>> DevStack managed >>>"
OLD_MARK_END = "# <<< DevStack managed <<<"
OLD_HOSTS_BEGIN = "# >>> DevStack hosts >>>"
OLD_HOSTS_END = "# <<< DevStack hosts <<<"
OLD_INCLUDE = "Include conf/extra/devstack.conf"
OLD_BACKUP = "httpd.conf.devstack.bak"

# Tools whose versions live in sibling folders of this application.
TOOLS = {
    "httpd": {"label": "Apache", "prefixes": ("httpd-",), "exe": "bin/httpd.exe", "path": "bin"},
    "php": {"label": "PHP", "prefixes": ("php-",), "exe": "php.exe", "path": ""},
    "mysql": {"label": "MySQL / MariaDB", "prefixes": ("mysql-", "mariadb-"), "exe": "bin/mysqld.exe", "path": "bin"},
    "nodejs": {"label": "Node.js", "prefixes": ("nodejs-", "node-"), "exe": "node.exe", "path": ""},
}

DEFAULT_PHP_EXTENSIONS = [
    "curl", "fileinfo", "gd", "intl", "mbstring", "exif", "mysqli", "openssl", "pdo_mysql", "zip", "sodium",
]


class StackyardError(Exception):
    """An error whose message is meant to be shown to the user."""


# --------------------------------------------------------------------------- helpers
def fwd(p) -> str:
    return str(p).replace("\\", "/")


def natural_key(s: str):
    return [int(p) if i % 2 else p.lower() for i, p in enumerate(re.split(r"(\d+)", s))]


def read_text(path) -> str:
    """Read a text file, tolerating UTF-16 and UTF-8 BOMs (a classic Windows editor trap)."""
    data = Path(path).read_bytes()
    if data.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
        return data.decode("utf-16")
    return data.decode("utf-8-sig", errors="surrogateescape")


def write_text(path, text: str, backup: bool = False) -> None:
    """Always writes UTF-8 *without* BOM, keeping line endings exactly as given."""
    path = Path(path)
    if backup and path.exists():
        shutil.copyfile(path, path.with_name(path.name + ".bak"))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8", errors="surrogateescape"))


def run(cmd, timeout: int = 30, cwd=None, env=None):
    return subprocess.run(
        [str(c) for c in cmd], cwd=str(cwd) if cwd else None, env=env, stdin=subprocess.DEVNULL,
        capture_output=True, text=True, errors="replace", timeout=timeout, creationflags=NO_WINDOW,
    )


def tail_file(path, lines: int = 15) -> str:
    try:
        data = Path(path).read_bytes()[-6000:].decode("utf-8", errors="replace")
        return "\n".join(data.splitlines()[-lines:])
    except OSError:
        return ""


def is_admin() -> bool:
    try:
        if IS_WIN:
            return bool(ctypes.windll.shell32.IsUserAnAdmin())
        return os.geteuid() == 0
    except Exception:
        return False


def set_app_user_model_id(app_id: str = "Stackyard.Manager") -> None:
    """Give the process its own Windows taskbar identity (otherwise it is grouped under python.exe)."""
    if IS_WIN:
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
        except Exception:
            pass


def set_dpi_awareness() -> None:
    """Render text crisply on high-DPI displays. Must run before the first Tk window is created."""
    if not IS_WIN:
        return
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)   # system DPI aware (Windows 8.1+)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()      # older Windows
        except Exception:
            pass


def relaunch_as_admin() -> None:
    script = str(Path(sys.argv[0]).resolve())
    params = " ".join(f'"{a}"' for a in [script] + sys.argv[1:])
    ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, params, None, 1)


def open_path(p) -> None:
    p = str(p)
    if IS_WIN:
        os.startfile(p)  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.Popen(["open", p])
    else:
        subprocess.Popen(["xdg-open", p])


def open_in_editor(p) -> None:
    if IS_WIN:
        subprocess.Popen(["notepad.exe", str(p)])
    else:
        open_path(p)


def port_open(port: int, host: str = "127.0.0.1", timeout: float = 0.25) -> bool:
    try:
        with socket.create_connection((host, int(port)), timeout):
            return True
    except OSError:
        return False


def pid_alive(pid: int) -> bool:
    if IS_WIN:
        k = ctypes.windll.kernel32
        k.OpenProcess.argtypes = [ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong]
        k.OpenProcess.restype = ctypes.c_void_p
        k.GetExitCodeProcess.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_ulong)]
        k.CloseHandle.argtypes = [ctypes.c_void_p]
        h = k.OpenProcess(0x1000, 0, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not h:
            return False
        code = ctypes.c_ulong()
        ok = k.GetExitCodeProcess(h, ctypes.byref(code))
        k.CloseHandle(h)
        return bool(ok) and code.value == 259  # STILL_ACTIVE
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def pid_on_port(port: int) -> Optional[int]:
    """PID listening on a TCP port. Language independent (matches the 0.0.0.0:0 foreign address)."""
    if not IS_WIN:
        return None
    try:
        out = run(["netstat", "-ano", "-p", "TCP"], timeout=15).stdout
    except Exception:
        return None
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 5 and parts[2] in ("0.0.0.0:0", "[::]:0", "*:*"):
            if parts[1].rsplit(":", 1)[-1] == str(port) and parts[-1].isdigit():
                return int(parts[-1])
    return None


def process_name(pid: int) -> Optional[str]:
    if not IS_WIN:
        return None
    try:
        out = run(["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"], timeout=15).stdout.strip()
        if out.startswith('"'):
            return out.split('","')[0].strip('"')
    except Exception:
        pass
    return None


def kill_tree(pid: int) -> None:
    if IS_WIN:
        run(["taskkill", "/PID", str(pid), "/T", "/F"], timeout=20)
    else:
        try:
            os.kill(pid, 15)
        except OSError:
            pass


def kill_image(name: str) -> None:
    if IS_WIN:
        run(["taskkill", "/IM", name, "/T", "/F"], timeout=20)


# --------------------------------------------------------------------------- root folder
def set_base_dir(path) -> Path:
    """Switch the root folder (e.g. D:\\apps -> F:\\) and remember it for the next start."""
    global BASE_DIR, WWW_DIR, CURRENT_DIR, BASE_WARNING
    p = Path(path)
    if not p.is_dir():
        raise StackyardError(f"{p} is not a folder.")
    p = p.resolve()
    settings = _read_settings()
    settings["base_dir"] = str(p)
    try:
        SETTINGS_FILE.write_text(json.dumps(settings, indent=2), encoding="utf-8")
    except OSError as e:
        raise StackyardError(f"Cannot save the setting in {SETTINGS_FILE}: {e}")
    BASE_DIR, WWW_DIR, CURRENT_DIR, BASE_WARNING = p, p / "www", p / "current", None
    return p


def remap_vhosts(cfg: "Config", old_www: Path, new_www: Path) -> int:
    """Move virtual-host folders that lived inside the old www folder to the new one."""
    old = os.path.normcase(os.path.normpath(str(old_www)))
    moved = 0
    for v in cfg.vhosts:
        cur = os.path.normcase(os.path.normpath(v["path"]))
        if cur == old or cur.startswith(old + os.sep):
            rel = os.path.relpath(v["path"], str(old_www))
            v["path"] = str(new_www if rel == "." else new_www / rel)
            moved += 1
    if moved:
        cfg.save()
    return moved


# --------------------------------------------------------------------------- versions
def tools_dir() -> Path:
    """Where tools live and where new ones are installed: <root>\\bin when it exists, else <root>."""
    b = BASE_DIR / "bin"
    return b if b.is_dir() else BASE_DIR


def search_dirs() -> list[Path]:
    """Folders scanned for tool versions (tools folder first, then the root itself)."""
    dirs = [tools_dir()]
    if BASE_DIR not in dirs:
        dirs.append(BASE_DIR)
    return dirs


def locate(name: str) -> Optional[Path]:
    for base in search_dirs():
        p = base / name
        if p.is_dir():
            return p
    return None


def composer_dir() -> Path:
    for base in search_dirs():
        if (base / "composer" / "composer.phar").exists():
            return base / "composer"
    return tools_dir() / "composer"


def write_composer_wrapper(folder: Path) -> bool:
    """composer.bat that runs the ACTIVE php via the 'current' junction (absolute path, so moving
    the composer folder cannot break it). Returns True when the file was (re)written."""
    bat = folder / "composer.bat"
    content = f'@echo off\r\n"{CURRENT_DIR / "php" / "php.exe"}" "%~dp0composer.phar" %*\r\n'
    try:
        if bat.exists() and bat.read_bytes() == content.encode("ascii", "replace"):
            return False
        bat.write_bytes(content.encode("ascii", "replace"))
        return True
    except OSError:
        return False


def list_versions(tool: str) -> list[Path]:
    meta = TOOLS[tool]
    found: dict[str, Path] = {}
    for base in search_dirs():
        if not base.is_dir():
            continue
        for d in base.iterdir():
            if (d.is_dir() and d.name not in found and d.name.lower().startswith(meta["prefixes"])
                    and (d / meta["exe"]).exists()):
                found[d.name] = d
    return sorted(found.values(), key=lambda p: natural_key(p.name), reverse=True)


def php_apache_module(php_dir: Path):
    """(dll, module_symbol) when this PHP build ships an Apache module (Thread Safe builds), else None."""
    for f in sorted(Path(php_dir).glob("php*apache2_*.dll")):
        m = re.match(r"php(\d+)apache2_\d+\.dll$", f.name, re.I)
        if m:
            major = int(m.group(1))
            return f, ("php_module" if major >= 8 else f"php{major}_module")
    return None


def version_note(tool: str, d: Path) -> str:
    if tool == "php":
        if php_apache_module(d):
            return "Thread Safe build - can run as an Apache module."
        return "Non-Thread-Safe build - no Apache module in this folder (CLI / FastCGI only)."
    if tool == "mysql":
        return "MariaDB" if (d / "bin" / "mysql_install_db.exe").exists() else "MySQL"
    return ""


class Config:
    def __init__(self) -> None:
        self.data: dict = {
            "active": {}, "vhosts": [], "services": [], "stop_on_exit": False, "mysql_root_password": "",
        }
        try:
            if CONFIG_FILE.exists():
                self.data.update(json.loads(CONFIG_FILE.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            pass

    def save(self) -> None:
        CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        CONFIG_FILE.write_text(json.dumps(self.data, indent=2), encoding="utf-8")

    @property
    def vhosts(self) -> list:
        return self.data["vhosts"]

    def active_dir(self, tool: str) -> Optional[Path]:
        wanted = self.data["active"].get(tool)
        versions = list_versions(tool)
        for v in versions:
            if v.name == wanted:
                return v
        return versions[0] if versions else None


# --------------------------------------------------------------------------- "current" junctions + PATH
def link_current(tool: str, target: Path) -> None:
    CURRENT_DIR.mkdir(parents=True, exist_ok=True)
    link = CURRENT_DIR / tool
    if os.path.lexists(link):
        try:
            os.rmdir(link) if IS_WIN else os.unlink(link)
        except OSError as e:
            raise StackyardError(f"Cannot replace {link}: {e}")
    if IS_WIN:
        r = run(["cmd.exe", "/c", "mklink", "/J", str(link), str(target)])
        if r.returncode != 0:
            raise StackyardError(f"mklink failed: {(r.stdout + r.stderr).strip()}")
    else:
        link.symlink_to(target, target_is_directory=True)


def apply_active_links(cfg: Config) -> list[str]:
    notes = []
    for tool in TOOLS:
        d = cfg.active_dir(tool)
        if d:
            try:
                link_current(tool, d)
            except StackyardError as e:
                notes.append(str(e))
    return notes


def path_entries() -> list[Path]:
    entries = []
    for tool, meta in TOOLS.items():
        p = CURRENT_DIR / tool
        entries.append(p / meta["path"] if meta["path"] else p)
    entries.append(composer_dir())
    return entries


def env_with_path() -> dict:
    env = os.environ.copy()
    extra = os.pathsep.join(str(p) for p in path_entries() if p.exists())
    env["PATH"] = extra + os.pathsep + env.get("PATH", "")
    return env


def add_to_user_path(entries: list[Path]) -> list[str]:
    if not IS_WIN:
        raise StackyardError("Editing the user PATH is only supported on Windows.")
    import winreg

    added: list[str] = []
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0, winreg.KEY_READ | winreg.KEY_WRITE) as k:
        try:
            cur, typ = winreg.QueryValueEx(k, "Path")
        except FileNotFoundError:
            cur, typ = "", winreg.REG_EXPAND_SZ
        parts = [p for p in cur.split(";") if p]
        seen = {p.lower().rstrip("\\") for p in parts}
        for e in entries:
            s = str(e)
            if s.lower().rstrip("\\") not in seen:
                parts.append(s)
                added.append(s)
        if added:
            if typ not in (winreg.REG_SZ, winreg.REG_EXPAND_SZ):
                typ = winreg.REG_EXPAND_SZ
            winreg.SetValueEx(k, "Path", 0, typ, ";".join(parts))
    if added:
        try:  # tell running programs to reload their environment
            ctypes.windll.user32.SendMessageTimeoutW(0xFFFF, 0x001A, 0, "Environment", 0x0002, 5000, None)
        except Exception:
            pass
    return added


def open_terminal(cwd=None) -> None:
    if not IS_WIN:
        raise StackyardError("Terminal launcher is only implemented for Windows.")
    start_dir = Path(cwd) if cwd else (WWW_DIR if WWW_DIR.exists() else BASE_DIR)
    subprocess.Popen(
        ["cmd.exe", "/k"], cwd=str(start_dir),
        env=env_with_path(), creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0x10),
    )


# --------------------------------------------------------------------------- PHP
def ensure_php_ini(php_dir: Path) -> bool:
    """Create php.ini from php.ini-development when missing. Returns True if it was created."""
    ini = php_dir / "php.ini"
    created = False
    if not ini.exists():
        for name in ("php.ini-development", "php.ini-production"):
            src = php_dir / name
            if src.exists():
                shutil.copyfile(src, ini)
                created = True
                break
        else:
            write_text(ini, "")
            created = True
    text = read_text(ini)
    # Use an ABSOLUTE extension_dir: the relative "ext" often fails when PHP runs inside Apache.
    abs_line = f'extension_dir = "{fwd(php_dir / "ext")}"'
    cur_re = re.compile(r'(?m)^[ \t]*extension_dir[ \t]*=[ \t]*"?([^"\r\n]*?)"?[ \t]*(\r?)$')
    rel_commented = r'(?m)^;[ \t]*extension_dir[ \t]*=[ \t]*"ext"[ \t]*(\r?)$'
    m = cur_re.search(text)
    if m:
        cur = m.group(1).strip()
        # rewrite when relative, or when it points to a folder that no longer exists (PHP was moved)
        stale = bool(re.fullmatch(r'\.?[\\/]?ext', cur)) or not Path(cur).is_dir()
        new = (text[:m.start()] + abs_line + m.group(2) + text[m.end():]) if stale else text
    else:
        new = re.sub(rel_commented, lambda mm: abs_line + mm.group(1), text, count=1)
        if new == text:
            nl = "\r\n" if "\r\n" in text else "\n"
            new = text.rstrip("\r\n") + nl + abs_line + nl
    if new != text:
        write_text(ini, new)
    if created:
        enable_php_extensions(php_dir, DEFAULT_PHP_EXTENSIONS)
    return created


def _ext_available(php_dir: Path, name: str) -> bool:
    ext = php_dir / "ext"
    if not ext.is_dir():
        return True
    return (ext / f"php_{name}.dll").exists()


def list_php_extensions(php_dir: Path) -> list[tuple[str, bool]]:
    ini = php_dir / "php.ini"
    if not ini.exists():
        ensure_php_ini(php_dir)
    text = read_text(ini)
    out: dict[str, bool] = {}
    for m in re.finditer(r'(?m)^[ \t]*(;?)[ \t]*(?:zend_)?extension[ \t]*=[ \t]*"?([A-Za-z0-9_]+)(?:\.dll)?"?[ \t\r]*$', text):
        name = m.group(2)
        if name.startswith("php_"):
            name = name[4:]
        if not _ext_available(php_dir, name):
            continue
        enabled = m.group(1) == ""
        out[name] = out.get(name, False) or enabled
    return sorted(out.items())


def set_php_extensions(php_dir: Path, states: dict[str, bool]) -> None:
    ini = php_dir / "php.ini"
    text = read_text(ini)
    for name, enable in states.items():
        pat = re.compile(
            r'(?m)^([ \t]*);?[ \t]*((?:zend_)?extension[ \t]*=[ \t]*"?(?:php_)?%s(?:\.dll)?"?[ \t\r]*)$' % re.escape(name)
        )
        if pat.search(text):
            text = pat.sub(lambda m: (m.group(2) if enable else ";" + m.group(2)), text)
        elif enable:
            text = text.rstrip("\n") + f"\nextension={name}\n"
    write_text(ini, text, backup=True)


def enable_php_extensions(php_dir: Path, names: list[str]) -> list[str]:
    ini = php_dir / "php.ini"
    if not ini.exists():
        return []
    names = [n for n in names if _ext_available(php_dir, n)]
    if names:
        set_php_extensions(php_dir, {n: True for n in names})
    return names


# --------------------------------------------------------------------------- Apache
def managed_conf_path(httpd_dir: Path) -> Path:
    return httpd_dir / "conf" / "extra" / "stackyard.conf"


def parse_listen_ports(httpd_dir: Path) -> list[int]:
    conf = httpd_dir / "conf" / "httpd.conf"
    if not conf.exists():
        return []
    text = read_text(conf)
    return [int(m.group(1)) for m in re.finditer(
        r"(?m)^[ \t]*Listen[ \t]+(?:\[[^\]]+\]:|[^\s:]+:)?(\d+)", text)]


def main_port(httpd_dir: Path) -> int:
    ports = parse_listen_ports(httpd_dir)
    return ports[0] if ports else 80


_PHP_DIRECTIVES = re.compile(
    r'^[ \t]*(LoadModule[ \t]+php\w*_module|PHPIniDir|AddType[ \t]+application/x-httpd-php|'
    r'AddHandler[ \t]+application/x-httpd-php|SetHandler[ \t]+"?proxy:fcgi)', re.I)


def integrate_httpd(httpd_dir: Path) -> list[str]:
    """Idempotently hook Stackyard into httpd.conf (backup made once)."""
    conf = httpd_dir / "conf" / "httpd.conf"
    if not conf.exists():
        raise StackyardError(f"{conf} not found")
    notes: list[str] = []
    text = read_text(conf)
    original = text
    bak = conf.with_name("httpd.conf.stackyard.bak")
    if not bak.exists() and not conf.with_name(OLD_BACKUP).exists():
        shutil.copyfile(conf, bak)
        notes.append(f"Backup saved as {bak.name}")
    lines = text.splitlines(keepends=True)
    disabled = 0
    for i, ln in enumerate(lines):
        if _PHP_DIRECTIVES.match(ln):
            lines[i] = "# [Stackyard disabled] " + ln.lstrip()
            disabled += 1
    text = "".join(lines)
    # A moved Apache folder keeps its old hard-coded SRVROOT; point it at where Apache really is.
    srv = fwd(httpd_dir)
    m = re.search(r'(?m)^([ \t]*Define[ \t]+SRVROOT[ \t]+)"([^"]*)"', text)
    if m and m.group(2).replace("\\", "/").rstrip("/").lower() != srv.rstrip("/").lower():
        text = text[:m.start()] + f'{m.group(1)}"{srv}"' + text[m.end():]
        notes.append(f"SRVROOT in httpd.conf updated to {srv} (the folder was moved)")
    if OLD_MARK_BEGIN in text or OLD_INCLUDE in text:
        text = (text.replace(OLD_MARK_BEGIN, MARK_BEGIN).replace(OLD_MARK_END, MARK_END)
                .replace(OLD_INCLUDE, "Include conf/extra/stackyard.conf"))
        notes.append("Upgraded the DevStack include in httpd.conf to Stackyard")
    if MARK_BEGIN not in text:
        nl = "\r\n" if "\r\n" in text else "\n"
        block = nl.join(["", MARK_BEGIN, "Include conf/extra/stackyard.conf", MARK_END, ""])
        text = text.rstrip("\r\n") + nl + block
        notes.append("Added the Stackyard include to httpd.conf")
    if disabled:
        notes.append(f"Disabled {disabled} old PHP/proxy directive(s) in httpd.conf (replaced by Stackyard's)")
    if text != original:
        write_text(conf, text)
    return notes


def split_aliases(s: str) -> list[str]:
    return [a for a in re.split(r"[,\s]+", s or "") if a]


def _directory_block(root: str) -> list[str]:
    return [
        f'    <Directory "{root}">',
        "        Options Indexes FollowSymLinks",
        "        AllowOverride All",
        "        Require all granted",
        "    </Directory>",
    ]


def build_managed_conf(cfg: Config) -> str:
    httpd = cfg.active_dir("httpd")
    if not httpd:
        raise StackyardError("No Apache version found (folder httpd-* with bin\\httpd.exe).")
    php = cfg.active_dir("php")
    L = [
        "# Generated by Stackyard - manual edits will be overwritten.",
        f"# {datetime.now():%Y-%m-%d %H:%M:%S}",
        "ServerName localhost",
        "",
    ]
    mod = php_apache_module(php) if php else None
    if mod:
        dll, symbol = mod
        L += [
            f'LoadModule {symbol} "{fwd(dll)}"',
            f'PHPIniDir "{fwd(php)}"',
            '<FilesMatch "\\.php$">',
            "    SetHandler application/x-httpd-php",
            "</FilesMatch>",
            "DirectoryIndex index.php index.html",
            "",
        ]
    elif php:
        L += [f"# {php.name} has no Apache module (non-thread-safe build): PHP is NOT enabled in Apache.", ""]
    existing = set(parse_listen_ports(httpd))
    for p in sorted({int(v["port"]) for v in cfg.vhosts} - existing):
        L.append(f"Listen {p}")
    port = main_port(httpd)
    www = fwd(WWW_DIR)
    L += [
        "", f"<VirtualHost *:{port}>",
        "    ServerName localhost", "    ServerAlias 127.0.0.1", f'    DocumentRoot "{www}"',
        *_directory_block(www), "</VirtualHost>",
    ]
    for v in cfg.vhosts:
        root = fwd(v["path"])
        L += ["", f'<VirtualHost *:{int(v["port"])}>', f'    ServerName {v["domain"]}']
        aliases = split_aliases(v.get("aliases", ""))
        if aliases:
            L.append("    ServerAlias " + " ".join(aliases))
        L.append(f'    DocumentRoot "{root}"')
        L += _directory_block(root)
        L += [
            f'    ErrorLog "logs/{v["domain"]}-error.log"',
            f'    CustomLog "logs/{v["domain"]}-access.log" common',
            "</VirtualHost>",
        ]
    return "\n".join(L) + "\n"


def write_managed_conf(cfg: Config) -> Path:
    httpd = cfg.active_dir("httpd")
    if not httpd:
        raise StackyardError("No Apache version found (folder httpd-* with bin\\httpd.exe).")
    path = managed_conf_path(httpd)
    write_text(path, build_managed_conf(cfg))
    old = path.with_name("devstack.conf")   # generated by the first version
    if old.exists():
        try:
            # Remove it only when it is our generated file and httpd.conf no longer includes it.
            generated = read_text(old).lstrip().startswith("# Generated by DevStack")
            if generated and OLD_INCLUDE not in read_text(httpd / "conf" / "httpd.conf"):
                old.unlink()
        except OSError:
            pass
    return path


def test_httpd(httpd_dir: Path) -> tuple[bool, str]:
    exe = httpd_dir / "bin" / "httpd.exe"
    r = run([exe, "-t", "-f", httpd_dir / "conf" / "httpd.conf"], cwd=exe.parent)
    return r.returncode == 0, (r.stdout + r.stderr).strip()


# --------------------------------------------------------------------------- virtual hosts / hosts file
DOMAIN_RE = re.compile(r"^(?=.{1,253}$)[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?(\.[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?)*$")


def vhost_names(v: dict) -> list[str]:
    return [v["domain"]] + split_aliases(v.get("aliases", ""))


def hosts_names(cfg: Config) -> list[str]:
    names: list[str] = []
    for v in cfg.vhosts:
        for n in vhost_names(v):
            # *.localhost names resolve to 127.0.0.1 in browsers by themselves: no hosts entry needed
            if n not in names and n.lower() != "localhost" and not n.lower().endswith(".localhost"):
                names.append(n)
    return names


def hosts_block(cfg: Config) -> str:
    """The lines Stackyard wants in the hosts file (for manual copy/paste)."""
    return "\n".join([HOSTS_BEGIN] + [f"127.0.0.1\t{n}" for n in hosts_names(cfg)] + [HOSTS_END])


def _write_hosts(text: str) -> None:
    """Write the hosts file, clearing the read-only attribute for the write and restoring it afterwards."""
    import stat
    mode = None
    if HOSTS_FILE.exists():
        m = HOSTS_FILE.stat().st_mode
        if not m & stat.S_IWRITE:
            mode = m
            os.chmod(HOSTS_FILE, m | stat.S_IWRITE)
    try:
        write_text(HOSTS_FILE, text)
    finally:
        if mode is not None:
            try:
                os.chmod(HOSTS_FILE, mode)
            except OSError:
                pass


def sync_hosts(cfg: Config) -> None:
    """Rewrite the Stackyard block in the Windows hosts file. Raises PermissionError/OSError when refused."""
    names = hosts_names(cfg)
    text = read_text(HOSTS_FILE) if HOSTS_FILE.exists() else ""
    original = text
    nl = "\r\n" if "\r\n" in text or not text else "\n"
    for begin, end in ((HOSTS_BEGIN, HOSTS_END), (OLD_HOSTS_BEGIN, OLD_HOSTS_END)):  # current and old block
        text = re.sub(r"(?s)\r?\n?%s.*?%s\r?\n?" % (re.escape(begin), re.escape(end)), nl, text)
    text = text.rstrip("\r\n")
    if names:
        block = nl.join([HOSTS_BEGIN] + [f"127.0.0.1\t{n}" for n in names] + [HOSTS_END])
        text += nl + nl + block
    new = text + nl
    if new == original or (not names and HOSTS_BEGIN not in original and OLD_HOSTS_BEGIN not in original):
        return  # nothing to change: don't touch the file (antivirus tools may block writes)
    _write_hosts(new)


def scan_www(cfg: Config) -> list[dict]:
    """Create <folder>.test virtual hosts for every sub-folder of www that has none yet."""
    added = []
    known = {os.path.normcase(os.path.normpath(v["path"])) for v in cfg.vhosts}
    domains = {v["domain"] for v in cfg.vhosts}
    if not WWW_DIR.is_dir():
        return added
    for d in sorted(WWW_DIR.iterdir()):
        if not d.is_dir() or d.name.startswith(".") or d.name.lower() in ("phpmyadmin",):
            continue
        root = d / "public" if (d / "public").is_dir() else d
        domain = re.sub(r"[^a-z0-9-]", "-", d.name.lower()).strip("-") + ".test"
        if not DOMAIN_RE.match(domain) or domain in domains:
            continue
        if os.path.normcase(os.path.normpath(str(root))) in known:
            continue
        v = {"domain": domain, "path": str(root), "port": 80, "aliases": ""}
        cfg.vhosts.append(v)
        domains.add(domain)
        added.append(v)
    if added:
        cfg.save()
    return added


def apply_vhosts(cfg: Config) -> dict:
    httpd = cfg.active_dir("httpd")
    if not httpd:
        raise StackyardError("No Apache version found.")
    integrate_httpd(httpd)
    write_managed_conf(cfg)
    hosts_ok, hosts_error = True, ""
    try:
        sync_hosts(cfg)
    except OSError as e:  # PermissionError included
        hosts_ok, hosts_error = False, f"{e.__class__.__name__}: {e}"
    ok, out = test_httpd(httpd)
    return {"hosts_ok": hosts_ok, "hosts_error": hosts_error, "test_ok": ok, "output": out}


# --------------------------------------------------------------------------- MySQL helpers
def ensure_mysql_ini(home: Path, port: int = 3306) -> Path:
    ini = home / "my.ini"
    if not ini.exists():
        write_text(ini, "\n".join([
            "[client]", f"port={port}", "default-character-set=utf8mb4", "",
            "[mysqld]", f"basedir={fwd(home)}", f"datadir={fwd(home)}/data", f"port={port}",
            "bind-address=127.0.0.1", "character-set-server=utf8mb4", "",
        ]))
    return ini


def fix_mysql_ini_paths(home: Path) -> list[str]:
    """After moving the MySQL folder, point basedir/datadir in my.ini at the new location.
    Paths that still exist (e.g. a data folder you put on another drive) are left alone."""
    ini = home / "my.ini"
    if not ini.exists():
        return []
    text = read_text(ini)
    notes: list[str] = []

    def fix(key: str, target: Path, parent_must_be_gone: bool) -> None:
        nonlocal text
        m = re.search(r'(?m)^([ \t]*%s[ \t]*=[ \t]*)"?([^"\r\n]*?)"?([ \t]*\r?)$' % key, text)
        if not m:
            return
        cur = m.group(2).strip()
        if not cur or Path(cur).exists() or (parent_must_be_gone and Path(cur).parent.exists()):
            return
        text = text[:m.start()] + f"{m.group(1)}{fwd(target)}{m.group(3)}" + text[m.end():]
        notes.append(f"my.ini: {key} -> {fwd(target)}")

    fix("basedir", home, False)
    fix("datadir", home / "data", True)
    if notes:
        write_text(ini, text, backup=True)
    return notes


def prepare_config_file(cfg: Config, path: Path) -> None:
    """Create a config file from sensible defaults when the user opens one that doesn't exist yet."""
    path = Path(path)
    if path.exists():
        return
    php = cfg.active_dir("php")
    mysql = cfg.active_dir("mysql")
    httpd = cfg.active_dir("httpd")
    if php and path == php / "php.ini":
        ensure_php_ini(php)
    elif mysql and path == mysql / "my.ini":
        ensure_mysql_ini(mysql)
    elif httpd and path == managed_conf_path(httpd):
        write_managed_conf(cfg)


def config_files(cfg: Config) -> list[tuple[str, Path, bool]]:
    items: list[tuple[str, Path, bool]] = []
    httpd, php, mysql = cfg.active_dir("httpd"), cfg.active_dir("php"), cfg.active_dir("mysql")
    if httpd:
        items.append(("Apache - httpd.conf", httpd / "conf" / "httpd.conf", False))
        items.append(("Apache - Stackyard generated (read-only)", managed_conf_path(httpd), True))
    if php:
        items.append(("PHP - php.ini", php / "php.ini", False))
    if mysql:
        items.append(("MySQL - my.ini", mysql / "my.ini", False))
    items.append(("Windows hosts file", HOSTS_FILE, False))
    return items


# --------------------------------------------------------------------------- services
class Service:
    key = ""
    label = ""
    image: Optional[str] = None   # executable name; lets us safely stop an instance we didn't start
    shell = False
    stop_wait = 0                 # seconds to wait for a graceful stop before killing

    def __init__(self, cfg: Config, log: Callable[[str], None]) -> None:
        self.cfg = cfg
        self.log = log

    # ---- to override
    def port(self) -> Optional[int]:
        return None

    def command(self):
        raise NotImplementedError

    def prepare(self) -> None:
        pass

    def graceful_stop(self) -> None:
        pass

    def describe(self) -> str:
        return ""

    # ---- common
    @property
    def pidfile(self) -> Path:
        return RUN_DIR / f"{self.key}.pid"

    def port_safe(self) -> Optional[int]:
        try:
            return self.port()
        except Exception:
            return None

    def tracked_pid(self) -> Optional[int]:
        try:
            pid = int(self.pidfile.read_text().strip())
        except (OSError, ValueError):
            return None
        if pid_alive(pid):
            return pid
        try:
            self.pidfile.unlink()
        except OSError:
            pass
        return None

    def status(self) -> str:
        pid = self.tracked_pid()
        port = self.port_safe()
        is_open = bool(port) and port_open(port)
        if pid:
            return "running" if (is_open or not port) else "starting"
        return "external" if is_open else "stopped"

    def start(self) -> None:
        if self.status() != "stopped":
            self.log(f"{self.label} is already running.")
            return
        self.log(f"Starting {self.label}...")
        self.prepare()
        cmd, cwd = self.command()
        RUN_DIR.mkdir(parents=True, exist_ok=True)
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        logfile = LOG_DIR / f"{self.key}.log"
        if not self.shell:
            cmd = [str(c) for c in cmd]
        with open(logfile, "ab") as out:
            out.write(f"\n--- {datetime.now():%Y-%m-%d %H:%M:%S} start: {cmd}\n".encode("utf-8", "replace"))
            proc = subprocess.Popen(
                cmd, cwd=str(cwd), stdin=subprocess.DEVNULL, stdout=out, stderr=subprocess.STDOUT,
                shell=self.shell, env=env_with_path(), creationflags=NO_WINDOW,
            )
        self.pidfile.write_text(str(proc.pid))
        port = self.port_safe()
        deadline = time.time() + (12 if port else 1.5)
        while time.time() < deadline:
            time.sleep(0.25)
            if proc.poll() is not None or (port and port_open(port)):
                break
        if proc.poll() is not None:
            try:
                self.pidfile.unlink()
            except OSError:
                pass
            raise StackyardError(
                f"{self.label} exited immediately (code {proc.returncode}).\n\nLast log lines:\n{tail_file(logfile)}")
        self.log(f"{self.label} started" + (f" on port {port}." if port else "."))

    def _wait_gone(self, pid: int, seconds: float) -> bool:
        end = time.time() + seconds
        while time.time() < end:
            if not pid_alive(pid):
                return True
            time.sleep(0.2)
        return not pid_alive(pid)

    def stop(self) -> None:
        pid = self.tracked_pid()
        by_image = False
        port = self.port_safe()
        if pid is None:
            if not (port and port_open(port)):
                self.log(f"{self.label} is not running.")
                return
            ext = pid_on_port(port)
            name = process_name(ext) if ext else None
            if not (ext and ext not in (0, 4) and self.image and name and name.lower() == self.image.lower()):
                raise StackyardError(
                    f"Port {port} is used by {name or 'another program'} (PID {ext}). "
                    f"Stackyard will not stop a process it does not recognise.")
            pid, by_image = ext, True
        self.log(f"Stopping {self.label} (PID {pid})...")
        try:
            self.graceful_stop()
        except Exception as e:  # graceful stop is best effort
            self.log(f"Graceful stop failed: {e}")
        if not self._wait_gone(pid, self.stop_wait):
            if by_image and self.image:
                kill_image(self.image)
            else:
                kill_tree(pid)
            self._wait_gone(pid, 5)
        if port:
            end = time.time() + 5
            while time.time() < end and port_open(port):
                time.sleep(0.2)
        try:
            self.pidfile.unlink()
        except OSError:
            pass
        self.log(f"{self.label} stopped.")

    def restart(self) -> None:
        self.stop()
        self.start()


class ApacheService(Service):
    key = "httpd"
    label = "Apache"
    image = "httpd.exe"

    def home(self) -> Path:
        d = self.cfg.active_dir("httpd")
        if not d:
            raise StackyardError("No Apache found. Put it in a folder named httpd-<version> next to Stackyard.")
        return d

    def port(self) -> int:
        return main_port(self.home())

    def describe(self) -> str:
        try:
            return f"{self.home().name}  |  port {self.port()}"
        except StackyardError:
            return "not installed"

    def prepare(self) -> None:
        home = self.home()
        for n in integrate_httpd(home):
            self.log(n)
        write_managed_conf(self.cfg)
        ok, out = test_httpd(home)
        if not ok:
            raise StackyardError("Apache configuration test failed:\n\n" + out)

    def command(self):
        home = self.home()
        return [home / "bin" / "httpd.exe", "-f", home / "conf" / "httpd.conf"], home / "bin"


class MySQLService(Service):
    key = "mysql"
    label = "MySQL"
    image = "mysqld.exe"
    stop_wait = 20

    def home(self) -> Path:
        d = self.cfg.active_dir("mysql")
        if not d:
            raise StackyardError("No MySQL found. Put it in a folder named mysql-<version> next to Stackyard.")
        return d

    def port(self) -> int:
        ini = self.home() / "my.ini"
        if ini.exists():
            m = re.search(r"(?m)^[ \t]*port[ \t]*=[ \t]*(\d+)", read_text(ini))
            if m:
                return int(m.group(1))
        return 3306

    def describe(self) -> str:
        try:
            return f"{self.home().name}  |  port {self.port()}"
        except StackyardError:
            return "not installed"

    def prepare(self) -> None:
        home = self.home()
        ini = ensure_mysql_ini(home)
        for n in fix_mysql_ini_paths(home):
            self.log(n)
        data = home / "data"
        if not data.is_dir() or not any(data.iterdir()):
            self.log("Initialising the MySQL data directory (first start, root has no password)...")
            if (home / "bin" / "mysql_install_db.exe").exists():  # MariaDB
                cmd = [home / "bin" / "mysql_install_db.exe", f"--datadir={data}"]
            else:
                cmd = [home / "bin" / "mysqld.exe", f"--defaults-file={ini}", "--initialize-insecure", "--console"]
            r = run(cmd, timeout=300, cwd=home / "bin")
            if r.returncode != 0:
                raise StackyardError("MySQL initialisation failed:\n\n" + (r.stdout + r.stderr).strip()[-1500:])

    def command(self):
        home = self.home()
        return [home / "bin" / "mysqld.exe", f"--defaults-file={home / 'my.ini'}", "--console"], home / "bin"

    def graceful_stop(self) -> None:
        home = self.home()
        exe = home / "bin" / "mysqladmin.exe"
        if not exe.exists():
            return
        env = env_with_path()
        if self.cfg.data.get("mysql_root_password"):
            env["MYSQL_PWD"] = self.cfg.data["mysql_root_password"]
        r = run([exe, "--user=root", "--host=127.0.0.1", f"--port={self.port()}", "shutdown"], timeout=25, env=env)
        if r.returncode != 0:
            first = (r.stderr or r.stdout).strip().splitlines()[:1]
            self.log("mysqladmin shutdown failed (" + (first[0] if first else "unknown") + "); will force-stop.")


class CustomService(Service):
    shell = True

    def __init__(self, cfg: Config, log, entry: dict) -> None:
        super().__init__(cfg, log)
        self.entry = entry
        self.key = entry["id"]
        self.label = entry["label"]

    def port(self) -> Optional[int]:
        p = self.entry.get("port")
        return int(p) if p else None

    def describe(self) -> str:
        p = self.port()
        return f"custom  |  {self.entry['command'][:50]}" + (f"  |  port {p}" if p else "")

    def command(self):
        cwd = self.entry.get("cwd") or str(WWW_DIR if WWW_DIR.exists() else BASE_DIR)
        return self.entry["command"], Path(cwd)


def build_services(cfg: Config, log: Callable[[str], None]) -> dict[str, Service]:
    services: dict[str, Service] = {"httpd": ApacheService(cfg, log), "mysql": MySQLService(cfg, log)}
    for entry in cfg.data.get("services", []):
        services[entry["id"]] = CustomService(cfg, log, entry)
    return services


# --------------------------------------------------------------------------- activate a version
def activate(cfg: Config, tool: str, name: str) -> list[str]:
    target = locate(name)
    if not target:
        raise StackyardError(f"{name} was not found in {' or '.join(str(d) for d in search_dirs())}.")
    cfg.data["active"][tool] = name
    cfg.save()
    link_current(tool, target)
    notes = [f"{TOOLS[tool]['label']} -> {name}"]
    if tool == "php":
        if ensure_php_ini(target):
            notes.append("Created php.ini from php.ini-development and enabled common extensions.")
        if not php_apache_module(target):
            notes.append("WARNING: this PHP build has no Apache module (non-thread-safe). It works on the command "
                         "line, but Apache will not run PHP with it.")
    if tool in ("php", "httpd"):
        httpd = cfg.active_dir("httpd")
        if httpd:
            notes += integrate_httpd(httpd)
            write_managed_conf(cfg)
    if tool == "mysql":
        ensure_mysql_ini(target)
    return notes


def startup(cfg: Config) -> list[str]:
    notes = apply_active_links(cfg)
    php = cfg.active_dir("php")
    if php:
        try:
            ensure_php_ini(php)  # also fixes a relative extension_dir
        except OSError as e:
            notes.append(f"Could not check php.ini: {e}")
    cdir = composer_dir()
    if (cdir / "composer.phar").exists() and write_composer_wrapper(cdir):
        notes.append(f"Updated {cdir / 'composer.bat'} (uses the active PHP)")
    for tool in TOOLS:
        d = cfg.active_dir(tool)
        if d and cfg.data["active"].get(tool) != d.name:
            cfg.data["active"][tool] = d.name
    cfg.save()
    return notes


# --------------------------------------------------------------------------- apps (installed?)
def app_status(key: str) -> str:
    if key == "phpmyadmin":
        p = WWW_DIR / "phpmyadmin"
        if (p / "index.php").exists():
            ver = ""
            try:
                m = re.search(r'"version"\s*:\s*"([^"]+)"', (p / "composer.json").read_text(encoding="utf-8"))
                ver = f" {m.group(1)}" if m else ""
            except OSError:
                pass
            return f"Installed{ver}  -  http://localhost/phpmyadmin/"
    elif key == "composer":
        if (composer_dir() / "composer.phar").exists():
            return "Installed"
    elif key == "nodejs":
        vs = list_versions("nodejs")
        if vs:
            return "Installed: " + ", ".join(v.name for v in vs)
    return "Not installed"
