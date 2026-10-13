# Changelog

All notable changes to Stackyard are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project aims to follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.1] - 2026-10-13

### Changed

- Redesigned the interface for readability and clarity: larger, consistent type
  across the whole app, more generous spacing, and a calm blue/grey palette.
- Added a hand-tuned ttk theme (`theme.py`) that centralises colours, fonts and
  widget styles, with card-style panels, accent and danger buttons, hover
  highlights on service rows, and a cleaner tab strip.
- Reworked the header: the title now sits above a root-folder subtitle, with the
  administrator state shown as a coloured badge.
- Restyled the Log, Versions, Virtual hosts, Configuration and Apps tabs with
  card layouts; the version pickers, app cards and progress bar use the new theme.
- Increased the default window size and minimum size to fit the larger type.
- Enabled Windows per-display DPI awareness (`core.set_dpi_awareness()`) and set
  Tk's scaling from the real display DPI, so text stays sharp on high-DPI screens.
- Added a hand cursor to action buttons so clickable controls are obvious.

## [0.1.0] - 2026-10-13

Initial release. Stackyard is a Windows application (Python + Tkinter, no extra packages) for
running a local PHP development environment from a single window.

### Added

- **Services tab** - start/stop/restart Apache and MySQL, plus user-defined custom services with
  an optional watched port. *Start all* / *Stop all*, status dots (running, starting, external,
  stopped), a *localhost* opener, an *Open terminal* button, and process tracking with pid files.
- **Versions tab** - detect `httpd-*`, `php-*`, `mysql-*`/`mariadb-*` and `nodejs-*` folders,
  activate one version per tool via `current\<tool>` junctions, and add the active tools to the
  user PATH.
- **Configuration tab** - editor for `httpd.conf`, the generated Stackyard Apache file (read-only),
  `php.ini`, `my.ini` and the Windows hosts file, with backup on save, an Apache config test, a
  PHP extension toggler, and UTF-8 (no BOM) normalization.
- **Virtual hosts tab** - add/edit/remove vhosts, scan the `www` folder, apply to the hosts file
  and Apache, and open sites in the browser. Supports `.localhost` and `.test` domains.
- **Apps tab** - one-click install/update of phpMyAdmin, Composer and Node.js, plus
  *Install from URL (zip)* for arbitrary tools and versions.
- **Landing page** - optional `extras\index.php` start page showing server/PHP/MySQL status,
  project list, extension checklist and phpinfo/phpMyAdmin links, with light/dark theme support.
- **DevStack upgrade** - on first start, imports the old `devstack.json` / `settings.json` and
  migrates the managed Apache and hosts-file blocks.
- Self-repair of written paths (`php.ini` `extension_dir`, `composer.bat`, Apache `SRVROOT`,
  MySQL `basedir`/`datadir`) when tool folders move.
- `STACKYARD_BASE` environment variable to override the root folder for a single launch.
- Full user manual in `README.md`.

[Unreleased]: https://example.com/compare/v0.1.0...HEAD
[0.1.0]: https://example.com/releases/tag/v0.1.0
