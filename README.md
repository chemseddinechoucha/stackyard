# Stackyard — User Manual

Stackyard is a small Windows application for running a local PHP development environment. From one window you can
start and stop **Apache** and **MySQL**, switch between versions of **Apache, PHP, MySQL and Node.js**, edit their
configuration files, create **virtual hosts**, and install **phpMyAdmin, Composer and Node.js**.

It is written in Python with Tkinter and needs no extra packages. It does not install Apache, PHP or MySQL for you:
you download them (as zip files) and Stackyard manages the folders.

Paths in this manual use `D:\dev` as the root folder. Yours can be anywhere (see [Change root folder](#5-the-main-window)).

---

## Contents

1. [Quick start](#1-quick-start)
2. [How Stackyard works](#2-how-stackyard-works)
3. [Requirements](#3-requirements)
4. [Installation and folder layout](#4-installation-and-folder-layout)
5. [The main window](#5-the-main-window)
6. [Services tab](#6-services-tab)
7. [Versions tab](#7-versions-tab)
8. [Configuration tab](#8-configuration-tab)
9. [Virtual hosts tab](#9-virtual-hosts-tab)
10. [Apps tab](#10-apps-tab)
11. [The landing page](#11-the-landing-page)
12. [Security notes](#12-security-notes)
13. [Files and what Stackyard changes](#13-files-and-what-stackyard-changes)
14. [Upgrading from DevStack](#14-upgrading-from-devstack)
15. [Troubleshooting](#15-troubleshooting)
16. [Uninstalling](#16-uninstalling)
17. [Quick reference](#17-quick-reference)

---

## 1. Quick start

1. Arrange your folders like this (details in [section 4](#4-installation-and-folder-layout)):
   `D:\dev\bin\httpd-2.4.68`, `D:\dev\bin\php-8.5.11`, `D:\dev\bin\mysql-26.7.0`, `D:\dev\www`, and Stackyard in `D:\dev\stackyard`.
2. Double-click `stackyard.pyw`.
3. Open the **Versions** tab and check that Apache, PHP and MySQL each show an active version.
4. Open the **Services** tab and press **Start all**, then **localhost**. A page opens in your browser.
5. Open the **Apps** tab and press **Install / update** next to phpMyAdmin. Then open
   `http://localhost/phpmyadmin/` (user `root`, empty password).

---

## 2. How Stackyard works

Understanding four ideas explains almost everything the application does.

- **Versions are folders.** Any folder named `php-<version>`, `httpd-<version>`, `mysql-<version>` (or `mariadb-<version>`)
  or `nodejs-<version>` is a version. You can keep several side by side.
- **One active version per tool.** Stackyard keeps a link (a Windows *junction*) at `D:\dev\current\php`,
  `D:\dev\current\httpd`, and so on. It always points to the version you activated. Put those links on your PATH once,
  and `php`, `node` or `composer` in any terminal follow your choice.
- **A generated Apache file.** Stackyard writes `conf\extra\stackyard.conf` inside the Apache folder and adds one
  `Include` line for it to `httpd.conf`. That file contains the PHP module, the default site and your virtual hosts.
  You change settings in the application and it regenerates the file; you do not edit it by hand.
- **Processes are tracked.** When Stackyard starts a service it remembers its process, so it can show the status and
  stop it later. A service started by some other means is shown as *Running (external)*.

Stackyard runs PHP inside Apache as a module (`php8apache2_4.dll`). That requires a **Thread Safe** PHP build.
Other PHP builds are still listed and work on the command line, but Apache will not run PHP with them.

---

## 3. Requirements

| Item | Details |
|---|---|
| Operating system | Windows 10 or 11 |
| Python | 3.9 or newer with Tk. The installer from python.org includes Tk. |
| Apache | Windows build, for example from Apache Lounge, unzipped to a folder named `httpd-<version>` |
| PHP | Thread Safe zip, unzipped to `php-<version>`; it must contain `php.exe` and `php8apache2_4.dll` |
| MySQL or MariaDB | Windows zip, unzipped to `mysql-<version>` or `mariadb-<version>` |
| Internet | Only for the **Apps** tab downloads |
| Administrator rights | Only to edit the Windows hosts file (see [section 9](#9-virtual-hosts-tab)) |

---

## 4. Installation and folder layout

1. Unzip Stackyard so that its folder sits inside your root folder, for example `D:\dev\stackyard`.
2. Put the tools and your sites in the root folder like this:

```
D:\dev\                      <- root folder
├── bin\                     <- tools (optional: without this folder, tools sit directly in the root)
│   ├── httpd-2.4.68\        Apache    must contain bin\httpd.exe
│   ├── php-8.5.11\          PHP       must contain php.exe
│   ├── mysql-26.7.0\        MySQL     must contain bin\mysqld.exe   (or mariadb-<version>)
│   ├── nodejs-22.11.0\      Node.js   must contain node.exe         (or node-<version>)
│   └── composer\            created by the Apps tab
├── www\                     your web sites (the document root)
├── current\                 created by Stackyard: links to the active version of each tool
└── stackyard\               this application
```

3. Start it with `stackyard.pyw` (no console window) or `start-stackyard.bat` (keeps a console open, useful if
   something fails to start and you want to read the Python error).

**Rules for version folders**

- The name must start with `httpd-`, `php-`, `mysql-`, `mariadb-`, `nodejs-` or `node-`.
- A folder is listed only if it contains the tool's main program (see the tree above).
- Stackyard looks in `bin` first, then in the root folder.

**If your tools are elsewhere**, press **Change root folder...** in the header (see the next section). If Stackyard
finds no tools at all on its first start, it offers to do this for you.

---

## 5. The main window

```
┌─────────────────────────────────────────────────────────────────────────┐
│ [logo] Stackyard   D:\dev        Administrator   [Change root folder...] │
├─────────────────────────────────────────────────────────────────────────┤
│  Services | Versions | Configuration | Virtual hosts | Apps              │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │                         the selected tab                          │  │
│  └───────────────────────────────────────────────────────────────────┘  │
├─────────────────────────────────────────────────────────────────────────┤
│ Log                                                          [Clear]     │
│ [10:42:07] Apache started on port 80.                                    │
└─────────────────────────────────────────────────────────────────────────┘
```

**Header**

- The grey path is the current **root folder**.
- **Administrator** (green) means Stackyard runs with administrator rights. If it is not, a **Restart as
  administrator** button appears instead. You only need it to edit the Windows hosts file.
- **Change root folder...** lets you choose another root folder, for example `F:\` or `E:\tools`. Stop all services
  first. Stackyard asks for confirmation, offers to create a `www` folder if the new root has none, and moves virtual
  hosts that pointed into the old `www` folder to the new one. Nothing is copied or deleted. Press **Apply** on the
  Virtual hosts tab afterwards, and press **Add Stackyard tools to my PATH** again if you had used it.
  The choice is remembered. If the saved drive is missing at the next start, Stackyard warns you and uses its own
  parent folder until the drive returns.

**Log**

Everything Stackyard does is written here, with the time. Errors also appear in a dialog. **Clear** empties the pane.

---

## 6. Services tab

This tab starts and stops the servers.

### Top buttons

| Button | What it does |
|---|---|
| **Start all** | Starts MySQL, then Apache, then your custom services |
| **Stop all** | Stops them in the reverse order |
| **+ Custom service** | Adds your own service (see below) |
| **localhost** | Opens `http://localhost/` in your browser |
| **www folder** | Opens your document root in Explorer |
| **Open terminal** | Opens a command prompt in `www` with the active tools already on its PATH |

### Service rows

Each row shows the service name, the active version and port, a coloured dot and the state:

| Dot | State | Meaning |
|---|---|---|
| Green | Running | Started by Stackyard and answering on its port |
| Amber | Starting... | Started, port not answering yet |
| Blue | Running (external) | Something is listening on the port that Stackyard did not start |
| Grey | Stopped | Nothing running |

Buttons on each row: **Start**, **Stop**, **Restart**. They are enabled according to the state.

**Starting Apache.** Before launching, Stackyard makes sure `httpd.conf` includes its generated file, regenerates
that file, and runs Apache's own configuration test. If the test fails, Apache is not started and the error message
is shown so you can fix it.

**Starting MySQL for the first time.** Stackyard creates `my.ini` and initialises the data folder
(`--initialize-insecure`). This takes a moment. The `root` user is created **without a password**.

**Stopping.** Apache is stopped by ending its process. MySQL is asked to shut down cleanly with `mysqladmin`
and is forced to stop only after 20 seconds. If you have set a MySQL root password, add it as
`"mysql_root_password"` in `stackyard.json` (close Stackyard first) so the clean shutdown can log in; otherwise the
clean shutdown fails and Stackyard waits the 20 seconds before forcing the stop. A forced stop is safe, but MySQL
may run crash recovery at its next start.

**Running (external).** If you started Apache by hand earlier, Stackyard shows *Running (external)* and can still stop
it, but only when the program using the port is the expected one (`httpd.exe` or `mysqld.exe`). If another program
holds the port, Stackyard refuses and tells you which one. It never stops a process it does not recognise.

### Custom services

**+ Custom service** opens a form:

| Field | Meaning |
|---|---|
| Name | The label shown in the list |
| Command | The command to run, for example `npm run dev` |
| Working folder | The folder the command runs in (browse with `...`) |
| Port to watch (optional) | If set, the service shows *Running* only once this port answers |

Custom services are started by **Start all** and have a **x** button to remove them from the list. Removing does not
stop a process that is already running. Their output is saved to `stackyard\logs\`.

### Closing Stackyard

If services are still running when you close the window, Stackyard asks whether to stop them (**Yes**), leave them
running (**No**) or cancel. Tick **Stop services automatically when Stackyard closes** to skip the question.
Services left running are detected again at the next start.

---

## 7. Versions tab

This tab chooses which version of each tool is active.

### Top buttons

| Button | What it does |
|---|---|
| **Rescan** | Looks for version folders again (after you unzip a new one) |
| **Open base folder** | Opens the root folder in Explorer |
| **Add Stackyard tools to my PATH** | Adds the `current\...` folders to your user PATH (see below) |

### Switching a version

Each tool (Apache, PHP, MySQL / MariaDB, Node.js) has a list of the versions found, an **Activate** button and an
*Active:* label. A grey note under PHP says whether the selected build is Thread Safe (can run as an Apache module)
or not, and under MySQL whether it is MySQL or MariaDB.

Choose a version and press **Activate**. Stackyard then:

1. saves your choice,
2. points `current\<tool>` at that version,
3. for PHP: creates `php.ini` if needed, turns on common extensions and fixes `extension_dir`,
4. for PHP and Apache: regenerates the Apache configuration.

Rules:

- **MySQL** must be stopped before you switch its version.
- **Apache** that is running is stopped first (Stackyard asks).
- After switching **PHP** while Apache runs, Stackyard offers to restart Apache so the new PHP is used.
- Each MySQL version keeps its own `data` folder. Databases are not shared between versions. To move them, export
  with `mysqldump` (or phpMyAdmin) and import into the other version.

### Adding a version

Unzip the new folder next to the others, for example `D:\dev\bin\php-8.4.1`, and press **Rescan**. You can also use
**Install from URL (zip)...** on the Apps tab.

### Using the tools in a terminal

Press **Add Stackyard tools to my PATH** once. It shows the folders it will add:

```
D:\dev\current\httpd\bin
D:\dev\current\php
D:\dev\current\mysql\bin
D:\dev\current\nodejs
D:\dev\bin\composer
```

Confirm, then open a **new** terminal (already open ones do not see the change) and try:

```
php -v
node -v
composer --version
mysql --version
```

Because the entries point to the *active* version, you never have to touch the PATH again when you switch. It is safe
to press the button again: it only adds entries that are missing.

---

## 8. Configuration tab

A simple editor for the files that control your environment.

The list on the left contains:

| File | Notes |
|---|---|
| Apache - httpd.conf | The main Apache file |
| Apache - Stackyard generated (read-only) | The generated file; shown for reading only |
| PHP - php.ini | Created from `php.ini-development` if missing |
| MySQL - my.ini | Created with sensible defaults if missing |
| Windows hosts file | Saving requires administrator rights |

### Buttons

| Button | What it does |
|---|---|
| **Save** | Saves the file. The previous version is kept next to it as `<name>.bak` |
| **Reload** | Reads the file from disk again |
| **Open in Notepad** | Opens the file in Notepad |
| **PHP extensions...** | Opens the extension list (below) |
| **Test Apache config** | Regenerates the Apache file and runs Apache's configuration test, then shows the result |
| **Restart Apache** | Restarts Apache |

If you pick another file while the current one has unsaved changes, Stackyard asks whether to save first.

After saving `httpd.conf` or `php.ini` while Apache is running, Stackyard offers to restart Apache.
**Changes to `php.ini` only take effect after Apache restarts.**

### PHP extensions

The dialog lists the extensions available in the PHP `ext` folder. **Double-click** an extension (or press Space) to
toggle it, then **Save**. Typical extensions for web development are `mysqli`, `pdo_mysql`, `mbstring`, `curl`,
`openssl`, `gd`, `intl`, `zip` and `fileinfo`.

### About file encoding

Stackyard reads files saved as UTF-8 or UTF-16 and always saves **UTF-8 without BOM**, keeping your line endings.
This matters: Apache and PHP cannot read a configuration or script saved as UTF-16 (a common result of choosing
"Unicode" in Notepad). The symptom is a blank page or PHP code shown as text. Use VS Code or Notepad++ for your own
code and keep the encoding on UTF-8 without BOM.

---

## 9. Virtual hosts tab

A virtual host gives a site its own address, for example `blog.localhost`, instead of `localhost/blog/`.

### Buttons

| Button | What it does |
|---|---|
| **Add** | Creates a virtual host |
| **Edit** | Edits the selected one (double-clicking a row also works) |
| **Remove** | Deletes the selected one from the list |
| **Scan www folder** | Creates a virtual host for each folder in `www` that has none |
| **Open in browser** | Opens the selected site |
| **Apply (hosts file + Apache)** | Writes everything and restarts Apache if it is running |

### Fields

| Field | Meaning |
|---|---|
| Domain | The name, for example `blog.localhost` |
| Document root | The folder served (browse with `...`). For Laravel, choose the `public` subfolder |
| Port | Normally 80. Another port is added to Apache as a `Listen` line automatically |
| Aliases | More names for the same site, separated by spaces |

### The workflow

1. Add or edit virtual hosts. The status line reminds you that changes are *not applied yet*.
2. Press **Apply (hosts file + Apache)**. Stackyard regenerates the Apache file, updates the hosts file when needed,
   runs the configuration test, and restarts Apache if it is running.

`http://localhost/` and `http://127.0.0.1/` always serve the `www` folder.

### Choosing a domain: `.localhost` or `.test`

| | `.localhost` (recommended) | `.test` |
|---|---|---|
| Needs a hosts-file entry | No | Yes |
| Needs administrator rights | No | Yes |
| Works in Chrome, Edge, Firefox | Yes | Yes |
| Works in every command-line tool | Not always | Yes |

Names ending in `.localhost` resolve to your own computer in browsers, so Stackyard does not touch the hosts file
for them. Some command-line tools, and PHP's own outgoing HTTP requests, may not resolve them; use `.test` if you need
that.

**Scan www folder** creates names ending in `.test`. Rename them to `.localhost` if you prefer. It uses a `public`
subfolder as the document root when one exists, and skips `phpmyadmin` and hidden folders.

### If the hosts file cannot be updated

- If Stackyard is not running as administrator, it offers to restart itself as administrator. Press **Apply** again.
- If it is already administrator and Windows still refuses, the dialog shows the real error. This is usually
  antivirus "hosts file protection" (Kaspersky, Bitdefender and others). Stackyard then offers to copy the needed
  lines to the clipboard and open the hosts file in Notepad so you can paste them.
- The simplest fix is to use `.localhost` names.

Each site writes its own logs to the Apache `logs` folder as `<domain>-error.log` and `<domain>-access.log`.

---

## 10. Apps tab

Install helper applications with one button. These downloads need an internet connection.

### phpMyAdmin

**Install / update** downloads the latest phpMyAdmin into `www\phpmyadmin`, creates its configuration (with a random
secret) and turns on the PHP extensions it needs. Restart Apache afterwards. **Open** goes to
`http://localhost/phpmyadmin/`. Log in as `root` with an empty password (the MySQL default created by Stackyard).
Updating keeps your existing `config.inc.php`.

### Composer

**Install / update** downloads `composer.phar` into the `composer` folder and creates `composer.bat`, which always
runs Composer with the **active** PHP. After adding the tools to your PATH, run `composer --version`.

### Node.js

**Install / update** fetches the official list of Node.js versions (the 60 newest, long-term-support versions first). Pick one
and it is installed as `nodejs-<version>`. The first Node.js you install is activated automatically; later ones are
activated on the **Versions** tab. `npm` is included.

### Install from URL (zip)...

Downloads any zip and unpacks it into your tools folder. Enter a **Folder name** and the **Zip URL**. If the zip
contains a single top-level folder, it is flattened. To add another PHP version, use a name such as `php-8.4.1`
with the URL of that PHP zip, then press **Rescan** on the Versions tab.

**Open apps folder** opens the root folder. A progress bar shows the download.

---

## 11. The landing page

`extras\index.php` is an optional start page, similar to the default page of Apache or nginx. Copy it to
`D:\dev\www\index.php`. It shows:

- the headline **It works.** whose full stop is green when everything is in place and amber when something needs attention,
- the status of the web server, PHP and MySQL,
- a clickable list of the project folders in `www`, tagged Laravel, Composer, Node.js, PHP or Static site,
- a checklist of the PHP extensions you most often need,
- buttons for phpMyAdmin and `phpinfo()`.

It works offline and follows your light or dark system theme. Visitors from other computers only see a short
"This web server is running." message; the details are shown only on your own machine. Replace the file with your
own site, or delete it, whenever you like. If you edit it, save it as UTF-8 without BOM.

---

## 12. Security notes

Stackyard is meant for development on your own computer.

- **Network exposure.** Apache's default setting `Listen 80` accepts connections from every network interface. When
  Apache first runs, Windows Firewall asks which networks to allow. Choose **Private networks** only, or block it, if
  you do not want other devices to reach your sites. To restrict Apache to your own computer, change `Listen 80` to
  `Listen 127.0.0.1:80` in `httpd.conf` on the Configuration tab. Stackyard understands this form.
- **MySQL.** The `my.ini` that Stackyard creates makes MySQL listen on `127.0.0.1` only. The `root` user has no password
  by default, which is acceptable only because of that. If you use your own `my.ini`, keep `bind-address=127.0.0.1`. If you set a password, add it as `mysql_root_password` (see
  [section 6](#6-services-tab)).
- **Your processes.** Stackyard never stops a program it does not recognise.
- **Hosts file.** Stackyard only edits the block between its own marker lines.
- **phpinfo.** Do not leave `phpinfo()` pages on a computer that others can reach.

---

## 13. Files and what Stackyard changes

Everything Stackyard changes is listed here, and all of it can be undone (see [section 16](#16-uninstalling)).

| Location | What happens |
|---|---|
| `stackyard\stackyard.json` | Your active versions, virtual hosts, custom services, options and optional `mysql_root_password` |
| `stackyard\settings.json` | The root folder you chose |
| `stackyard\run\` | Process-id files of the services it started |
| `stackyard\logs\` | Start-up output of the services (`httpd.log`, `mysql.log`, custom services) |
| `<root>\current\<tool>` | Links to the active version of each tool |
| Apache `conf\httpd.conf` | One backup is made once (`httpd.conf.stackyard.bak`). Old PHP and proxy lines are commented out with `# [Stackyard disabled]`. A block between `# >>> Stackyard managed >>>` and `# <<< Stackyard managed <<<` is added at the end |
| Apache `conf\extra\stackyard.conf` | Generated file: PHP module, default site, virtual hosts |
| PHP `php.ini` | Created if missing; `extension_dir` is set to the absolute path of the `ext` folder |
| MySQL `my.ini` | Created if missing |
| Windows hosts file | Only the block between `# >>> Stackyard hosts >>>` and `# <<< Stackyard hosts <<<`, and only for names that need it |
| Your user PATH | Only when you press **Add Stackyard tools to my PATH** |

**Self-repair.** If you move a tool folder, Stackyard fixes the paths that were written inside it: PHP's
`extension_dir` and `composer.bat` when Stackyard starts, Apache's `SRVROOT` when you start or apply Apache, and
MySQL's `basedir` and `datadir` when you start MySQL. A data folder that still exists, for example on another drive,
is left alone.

**Advanced.** The environment variable `STACKYARD_BASE` overrides the root folder for one launch.

---

## 14. Upgrading from DevStack

Stackyard is the new name of DevStack.

1. Unzip the `stackyard` folder next to your old `devstack` folder.
2. Close DevStack and start Stackyard.

On its first start Stackyard imports the old `devstack.json` and `settings.json` (versions, virtual hosts, root
folder and options). It also upgrades the markers it finds:

- In `httpd.conf`, the old *DevStack managed* block becomes a *Stackyard managed* block that includes
  `conf\extra\stackyard.conf`. The generated `devstack.conf` is deleted (a file of that name that you wrote yourself
  is kept).
- In the hosts file, the old *DevStack hosts* block is replaced by a *Stackyard hosts* block.
- An existing `httpd.conf.devstack.bak` is kept, and no second backup is made.

Nothing is deleted from the old folder. If Apache is still running from DevStack, Stackyard shows it as *Running
(external)* and can stop it. Once everything works, you can remove the old folder.

---

## 15. Troubleshooting

| Problem | Likely cause | What to do |
|---|---|---|
| **Forbidden** (403) on a site | The document root points to a folder that does not exist, often because the root folder is wrong | Check the grey root path in the header. It must be the folder that *contains* `bin` and `www`, for example `D:\dev`, not `D:\dev\bin`. Fix it with **Change root folder...**, then press **Apply** |
| Apache does not start | Another program uses port 80 (IIS, Skype, another Apache), or the configuration has an error | The error and the last log lines appear in a dialog. Find the other program with `netstat -ano \| findstr ":80 "` then `tasklist /fi "PID eq <pid>"`. Or change `Listen` in `httpd.conf`. Use **Test Apache config** to see configuration errors |
| PHP code appears as text, or the page is blank | PHP is not handled, or the file is saved as UTF-16 | On the Versions tab, PHP must say *Thread Safe*. Restart Apache. Re-save the PHP file as UTF-8 without BOM. A telltale sign: `php file.php` prints strange characters before the code |
| phpMyAdmin says **mysqli extension is missing** | The extension is off, or PHP cannot find its `ext` folder | Turn on `mysqli` in **PHP extensions...**, restart Apache. Stackyard writes an absolute `extension_dir` at start. Check with `php --ini` and `php -m` |
| Hosts file could not be updated | Not administrator, or antivirus protection | Use `.localhost` names, or follow [section 9](#if-the-hosts-file-cannot-be-updated) |
| A change in `httpd.conf` or `php.ini` has no effect | Apache has not been restarted | Press **Restart Apache** |
| MySQL does not start | Another MySQL uses port 3306, a leftover process, or an initialisation error | A dialog shows the last log lines; see also `stackyard\logs\mysql.log`. A blue dot means something else already listens on 3306 |
| `error.log` does not exist | Apache's `logs` folder is missing | Create an empty `logs` folder inside the Apache folder |
| A tool is not listed on the Versions tab | Wrong folder name, or the main program is missing | Check the name prefix and the contents ([section 4](#4-installation-and-folder-layout)), then **Rescan**. Also check the root folder in the header |
| `php` or `composer` is not found in a terminal | PATH not set up, or the terminal was already open | Press **Add Stackyard tools to my PATH**, then open a new terminal |
| Warning that the saved root folder is not available | The drive is disconnected | Reconnect it and restart, or choose another root with **Change root folder...** |
| Nothing happens on the first start | Python or Tk problem | Start with `start-stackyard.bat` to see the error in the console |

---

## 16. Uninstalling

Your tools and your `www` folder are never touched. To remove Stackyard's changes:

1. Press **Stop all**.
2. In Apache's `conf\httpd.conf`, delete the block between `# >>> Stackyard managed >>>` and
   `# <<< Stackyard managed <<<`, or restore `httpd.conf.stackyard.bak`. Then delete `conf\extra\stackyard.conf`.
   Remove the `# [Stackyard disabled] ` prefix from any lines you want back.
3. Delete the block between `# >>> Stackyard hosts >>>` and `# <<< Stackyard hosts <<<` from the hosts file.
4. Remove the `current\...` and `composer` entries from your user PATH (Windows search: *Edit environment variables
   for your account*).
5. Remove the links. In a command prompt (each `rmdir` removes only the link, not the tool):

```
rmdir "D:\dev\current\httpd"
rmdir "D:\dev\current\php"
rmdir "D:\dev\current\mysql"
rmdir "D:\dev\current\nodejs"
rmdir "D:\dev\current"
```

6. Delete the `stackyard` folder.

---

## 17. Quick reference

| I want to... | Do this |
|---|---|
| Start everything | **Services** → **Start all** |
| Use another PHP version | Unzip it to `bin\php-<version>` → **Versions** → **Rescan** → choose it → **Activate** |
| Give a project its own address | **Virtual hosts** → **Add** (for example `shop.localhost`) → **Apply** |
| Create addresses for all my projects | **Virtual hosts** → **Scan www folder** → **Apply** |
| Turn a PHP extension on | **Configuration** → **PHP extensions...** → double-click → **Save** → restart Apache |
| Use a different drive | Header → **Change root folder...** |
| Use `php` or `composer` in any terminal | **Versions** → **Add Stackyard tools to my PATH**, then open a new terminal |
| Run `npm run dev` with the other services | **Services** → **+ Custom service** |
| See what went wrong | Read the **Log** pane, then `stackyard\logs\` |
| Check my Apache settings are valid | **Configuration** → **Test Apache config** |

| Command | Shows |
|---|---|
| `php -v` | The active PHP version |
| `where php` | The path, which should be `...\current\php\php.exe` |
| `php --ini` | Which `php.ini` PHP loads |
| `php -m` | The loaded extensions |
| `httpd -S` | The virtual hosts Apache has loaded (run from the Apache `bin` folder) |
