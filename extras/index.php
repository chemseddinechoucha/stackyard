<?php
declare(strict_types=1);

/*
 * Stackyard landing page.
 * Put this file in your document root (for example D:\dev\www\index.php).
 * It needs no internet connection. Replace it with your own site, or delete it.
 */

$local = in_array($_SERVER['REMOTE_ADDR'] ?? '', ['127.0.0.1', '::1'], true);

if ($local && isset($_GET['phpinfo'])) {
    phpinfo();
    exit;
}

function h(?string $s): string
{
    return htmlspecialchars((string) $s, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8');
}

/** Checks the local database server without ever showing an error to the visitor. */
function mysql_status(): array
{
    if (!extension_loaded('mysqli')) {
        return ['state' => 'missing', 'label' => 'MySQL', 'version' => ''];
    }
    mysqli_report(MYSQLI_REPORT_OFF);
    $c = mysqli_init();
    $c->options(MYSQLI_OPT_CONNECT_TIMEOUT, 1);
    $ok = @$c->real_connect('127.0.0.1', 'root', '', '', 3306);
    if ($ok) {
        $v = (string) $c->server_info;
        $c->close();
    } elseif (in_array($c->connect_errno, [1044, 1045, 1130, 1698, 1251], true)) {
        $v = ''; // the server answered but root needs a password: it is running
    } else {
        return ['state' => 'down', 'label' => 'MySQL', 'version' => ''];
    }
    $label = stripos($v, 'mariadb') !== false ? 'MariaDB' : 'MySQL';
    preg_match('~\d+(?:\.\d+)+~', $v, $m);
    return ['state' => 'up', 'label' => $label, 'version' => $m[0] ?? ''];
}

$sw = (string) ($_SERVER['SERVER_SOFTWARE'] ?? '');
if (preg_match('~^([A-Za-z][\w.-]*)/([\d.]+)~', $sw, $m) && $m[1] !== 'PHP') {
    $srvName = $m[1];
    $srvVer = $m[2];
} else {
    $srvName = $sw === '' ? 'Web server' : 'Built-in server';
    $srvVer = '';
}
$server = $srvName . ($srvVer !== '' ? ' ' . $srvVer : '');
$port = (string) ($_SERVER['SERVER_PORT'] ?? '80');
$docroot = (string) ($_SERVER['DOCUMENT_ROOT'] ?? __DIR__);
if (PHP_OS_FAMILY === 'Windows') {
    $docroot = str_replace('/', '\\', $docroot);
}
$sapiNames = ['apache2handler' => 'Apache module', 'fpm-fcgi' => 'PHP-FPM', 'cgi-fcgi' => 'FastCGI', 'cli-server' => 'built-in server'];
$sapi = $sapiNames[PHP_SAPI] ?? PHP_SAPI;
$ini = php_ini_loaded_file() ?: '';

$mysql = $local ? mysql_status() : ['state' => 'hidden', 'label' => 'MySQL', 'version' => ''];

$wanted = ['mysqli', 'pdo_mysql', 'mbstring', 'curl', 'openssl', 'gd', 'intl', 'zip', 'fileinfo', 'opcache'];
$exts = [];
foreach ($wanted as $e) {
    $exts[$e] = extension_loaded($e === 'opcache' ? 'Zend OPcache' : $e);
}
$missing = array_keys(array_filter($exts, fn (bool $on): bool => !$on));

$phpmyadmin = is_file($docroot . DIRECTORY_SEPARATOR . 'phpmyadmin' . DIRECTORY_SEPARATOR . 'index.php');

$projects = [];
if ($local) {
    foreach (@scandir($docroot) ?: [] as $f) {
        if ($f[0] === '.' || strtolower($f) === 'phpmyadmin') {
            continue;
        }
        $p = $docroot . DIRECTORY_SEPARATOR . $f;
        if (!is_dir($p)) {
            continue;
        }
        $type = is_file("$p/artisan") ? 'Laravel'
            : (is_file("$p/composer.json") ? 'Composer'
            : (is_file("$p/package.json") ? 'Node.js'
            : (is_file("$p/index.php") ? 'PHP'
            : (is_file("$p/index.html") ? 'Static site' : 'Folder'))));
        $projects[] = [
            'name' => $f,
            'type' => $type,
            'href' => rawurlencode($f) . '/' . (is_dir("$p/public") ? 'public/' : ''),
        ];
        if (count($projects) >= 200) {
            break;
        }
    }
    usort($projects, fn (array $a, array $b): int => strcasecmp($a['name'], $b['name']));
}

// What the headline period shows: green when everything is in place, amber when something needs attention.
$attention = $local && ($mysql['state'] !== 'up' || $missing || $ini === '');
$health = $attention ? 'warn' : 'ok';

$check = '<svg viewBox="0 0 16 16" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 8.5l3.2 3.2L13 5"/></svg>';
$cross = '<svg viewBox="0 0 16 16" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 4l8 8M12 4l-8 8"/></svg>';
$folder = '<svg viewBox="0 0 20 20" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round" aria-hidden="true"><path d="M2.5 5.5a1 1 0 0 1 1-1h4l1.6 1.8h7.4a1 1 0 0 1 1 1v7.7a1 1 0 0 1-1 1h-13a1 1 0 0 1-1-1z"/></svg>';
?>
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light dark">
<title>It works – Stackyard</title>
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 512 512'%3E%3Crect width='512' height='512' rx='112' fill='%2310282C'/%3E%3Crect x='106.0' y='106.0' width='89.7' height='89.7' rx='18.6' fill='%238FA6FF'/%3E%3Crect x='316.3' y='106.0' width='89.7' height='89.7' rx='18.6' fill='%238FA6FF'/%3E%3Crect x='211.2' y='211.2' width='89.7' height='89.7' rx='18.6' fill='%238FA6FF'/%3E%3Crect x='211.2' y='316.3' width='89.7' height='89.7' rx='18.6' fill='%23E4EFEC'/%3E%3C/svg%3E">
<script>try{var t=localStorage.getItem('stackyard-theme')||localStorage.getItem('devstack-theme');if(t)document.documentElement.setAttribute('data-theme',t);}catch(e){}</script>
<style>
:root {
  color-scheme: light;
  --bg: #ECF2EF; --ink: #10282C; --muted: #4D676B; --line: #C3D2CE; --hover: #E1EBE7;
  --accent: #2A44E8; --on-accent: #FFFFFF;
  --ok: #12805A; --warn: #995900; --bad: #B3261E;
  --display: "Bahnschrift", "DIN Alternate", "Arial Nova Condensed", "Roboto Condensed", "Helvetica Neue", Arial, sans-serif;
  --text: "Segoe UI Variable Text", "Segoe UI", system-ui, -apple-system, "Helvetica Neue", Arial, sans-serif;
  --code: "Cascadia Mono", Consolas, ui-monospace, SFMono-Regular, Menlo, monospace;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    color-scheme: dark;
    --bg: #0C1A1D; --ink: #E4EFEC; --muted: #93AAAD; --line: #23393D; --hover: #132528;
    --accent: #8FA6FF; --on-accent: #0C1A1D;
    --ok: #4FD1A0; --warn: #F0B35A; --bad: #FF8A80;
  }
}
:root[data-theme="dark"] {
  color-scheme: dark;
  --bg: #0C1A1D; --ink: #E4EFEC; --muted: #93AAAD; --line: #23393D; --hover: #132528;
  --accent: #8FA6FF; --on-accent: #0C1A1D;
  --ok: #4FD1A0; --warn: #F0B35A; --bad: #FF8A80;
}

* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--ink); font: 1rem/1.6 var(--text); -webkit-font-smoothing: antialiased; }
a { color: inherit; }
:focus-visible { outline: 3px solid var(--accent); outline-offset: 3px; }
.wrap { max-width: 64rem; margin: 0 auto; padding: 0 clamp(1.25rem, 5vw, 3rem); }

.top { display: flex; justify-content: space-between; align-items: center; padding: 1.25rem 0; }
.brand { display: flex; align-items: center; gap: .6rem; font: 600 1.1rem var(--display); letter-spacing: .01em; }
.brand svg .a { fill: var(--accent); }
.brand svg .s { fill: var(--ink); }
.theme { font: inherit; font-size: .9rem; color: var(--ink); background: none; border: 1px solid var(--line); padding: .4rem .85rem; border-radius: 8px; cursor: pointer; }
.theme:hover { background: var(--hover); }

.hero { padding: clamp(2.5rem, 9vw, 6rem) 0 clamp(1rem, 3vw, 2rem); }
.hero h1 { margin: 0; font: 700 clamp(4.5rem, 18vw, 11.5rem)/.86 var(--display); letter-spacing: -.025em; font-variation-settings: "wdth" 85; }
.dot { display: inline-block; animation: stamp 1.1s cubic-bezier(.2, .9, .3, 1.25) .15s both; }
.dot.ok { color: var(--ok); }
.dot.warn { color: var(--warn); }
@keyframes stamp { from { transform: translateY(-.3em) scale(1.6); opacity: 0; } to { transform: none; opacity: 1; } }
@media (prefers-reduced-motion: reduce) { .dot { animation: none; } }

.lede { max-width: 44ch; margin: 1.75rem 0 0; font-size: clamp(1.1rem, 2.3vw, 1.4rem); line-height: 1.5; }
.lede code { font: .8em var(--code); background: var(--hover); padding: .1em .4em; border-radius: 4px; overflow-wrap: anywhere; }
.lede .note { display: block; margin-top: .5rem; }
.actions { display: flex; flex-wrap: wrap; align-items: center; gap: .75rem; margin-top: 1.75rem; }
.btn { display: inline-block; font: 600 .95rem var(--text); padding: .7rem 1.15rem; border-radius: 10px; text-decoration: none; border: 1px solid transparent; }
.btn.primary { background: var(--accent); color: var(--on-accent); }
.btn.primary:hover { filter: brightness(1.1); }
.btn.plain { border-color: var(--line); }
.btn.plain:hover { background: var(--hover); }
.hint { color: var(--muted); font-size: .95rem; }

section { margin-top: clamp(2.5rem, 6vw, 4rem); }
.sec-head { display: flex; justify-content: space-between; align-items: baseline; gap: 1rem; padding-bottom: .55rem; border-bottom: 2px solid var(--ink); }
h2 { margin: 0; font: 600 1.6rem/1.1 var(--display); letter-spacing: .005em; }
.count { color: var(--muted); font-size: .95rem; }

.rows { list-style: none; margin: 0; padding: 0; }
.rows > li { display: grid; grid-template-columns: 10rem 1fr auto; gap: .25rem 1.25rem; align-items: baseline; padding: 1rem .25rem; border-bottom: 1px solid var(--line); }
.rows .name { font: 600 1.3rem var(--display); }
.rows .detail { min-width: 0; color: var(--muted); overflow-wrap: anywhere; }
.rows .detail code { font: .85em var(--code); }
.state { display: inline-flex; align-items: center; gap: .5rem; font-weight: 600; white-space: nowrap; }
.state i { display: inline-block; width: .7rem; height: .7rem; border-radius: 50%; background: currentColor; }
.state.ok { color: var(--ok); }
.state.warn { color: var(--warn); }
.state.warn i { border-radius: 2px; transform: rotate(45deg); }
.state.bad { color: var(--bad); }
.state.bad i { background: none; box-shadow: inset 0 0 0 2px currentColor; }

.projects > li { position: relative; grid-template-columns: 1.6rem 1fr auto; align-items: center; }
.projects > li:hover { background: var(--hover); }
.projects > li:has(a:focus-visible) { outline: 3px solid var(--accent); outline-offset: -3px; }
.projects a { text-decoration: none; font: 600 1.2rem var(--display); }
.projects a:focus-visible { outline: none; }
.projects a::after { content: ""; position: absolute; inset: 0; }
.projects svg { color: var(--muted); }
.tag { color: var(--muted); font-size: .92rem; }
.empty { display: block !important; color: var(--muted); }
.empty strong { color: var(--ink); }

.exts { list-style: none; display: flex; flex-wrap: wrap; gap: .6rem 1.75rem; margin: 0; padding: 1.25rem .25rem 0; }
.exts li { display: inline-flex; align-items: center; gap: .45rem; }
.exts .on { color: var(--ok); }
.exts .off { color: var(--bad); font-weight: 600; }
.exts .off span { color: var(--bad); }
.fix { margin: 1rem .25rem 0; color: var(--muted); }

footer { margin-top: clamp(3rem, 7vw, 5rem); padding: 1.5rem 0 3rem; border-top: 1px solid var(--line); color: var(--muted); font-size: .92rem; }
footer code { font: .9em var(--code); overflow-wrap: anywhere; }

@media (max-width: 40rem) {
  .rows > li { grid-template-columns: 1fr auto; }
  .rows .detail { grid-column: 1 / -1; order: 3; }
  .projects > li { grid-template-columns: 1.6rem 1fr auto; }
}
</style>
</head>
<body>
<div class="wrap">
  <header class="top">
    <div class="brand">
      <svg viewBox="0 0 97 97" width="28" height="28" aria-hidden="true"><rect class="a" x="0" y="0" width="29" height="29" rx="6"/><rect class="a" x="68" y="0" width="29" height="29" rx="6"/><rect class="a" x="34" y="34" width="29" height="29" rx="6"/><rect class="s" x="34" y="68" width="29" height="29" rx="6"/></svg>
      Stackyard
    </div>
    <button class="theme" id="theme" type="button">Dark theme</button>
  </header>

  <main>
    <div class="hero">
      <h1>It works<span class="dot <?= $health ?>">.</span></h1>
<?php if ($local): ?>
      <p class="lede">
        <?= h($server) ?> is serving PHP <?= h(PHP_VERSION) ?> from <code><?= h($docroot) ?></code>.
<?php if ($mysql['state'] === 'up'): ?>
        <?= h($mysql['label']) ?><?= $mysql['version'] !== '' ? ' ' . h($mysql['version']) : '' ?> is running.
<?php elseif ($mysql['state'] === 'down'): ?>
        <span class="note">MySQL isn't running. Start it from the Services tab in Stackyard.</span>
<?php else: ?>
        <span class="note">PHP can't reach MySQL because the mysqli extension is missing.</span>
<?php endif; ?>
      </p>
      <div class="actions">
<?php if ($phpmyadmin): ?>
        <a class="btn primary" href="/phpmyadmin/">Open phpMyAdmin</a>
<?php endif; ?>
        <a class="btn plain" href="?phpinfo=1">PHP information</a>
<?php if (!$phpmyadmin): ?>
        <span class="hint">phpMyAdmin isn't installed. Add it from the Apps tab in Stackyard.</span>
<?php endif; ?>
      </div>
<?php else: ?>
      <p class="lede">This web server is running.</p>
<?php endif; ?>
    </div>

<?php if ($local): ?>
    <section aria-labelledby="stack">
      <div class="sec-head"><h2 id="stack">Stack</h2></div>
      <ul class="rows">
        <li>
          <span class="name"><?= h($srvName) ?></span>
          <span class="detail"><?= $srvVer !== '' ? h($srvVer) . ', ' : '' ?>port <?= h($port) ?></span>
          <span class="state ok"><i></i>Running</span>
        </li>
        <li>
          <span class="name">PHP</span>
          <span class="detail"><?= h(PHP_VERSION) ?>, <?= h($sapi) ?>.
            <?php if ($ini !== ''): ?>Settings file: <code><?= h($ini) ?></code><?php else: ?>No php.ini is loaded, so PHP uses its built-in defaults.<?php endif; ?></span>
          <span class="state <?= $ini !== '' ? 'ok' : 'warn' ?>"><i></i><?= $ini !== '' ? 'Configured' : 'No php.ini' ?></span>
        </li>
        <li>
          <span class="name"><?= h($mysql['label']) ?></span>
          <span class="detail"><?= $mysql['version'] !== '' ? h($mysql['version']) . ', ' : '' ?>127.0.0.1 port 3306</span>
<?php if ($mysql['state'] === 'up'): ?>
          <span class="state ok"><i></i>Running</span>
<?php elseif ($mysql['state'] === 'down'): ?>
          <span class="state bad"><i></i>Not running</span>
<?php else: ?>
          <span class="state warn"><i></i>mysqli missing</span>
<?php endif; ?>
        </li>
      </ul>
    </section>

    <section aria-labelledby="projects">
      <div class="sec-head">
        <h2 id="projects">Projects</h2>
        <span class="count"><?= count($projects) ?> <?= count($projects) === 1 ? 'folder' : 'folders' ?> in your web root</span>
      </div>
      <ul class="rows projects">
<?php if (!$projects): ?>
        <li class="empty"><strong>No projects yet.</strong> Create a folder in <code><?= h($docroot) ?></code> and it appears here.</li>
<?php endif; ?>
<?php foreach ($projects as $p): ?>
        <li>
          <?= $folder ?>
          <a href="<?= h($p['href']) ?>"><?= h($p['name']) ?></a>
          <span class="tag"><?= h($p['type']) ?></span>
        </li>
<?php endforeach; ?>
      </ul>
    </section>

    <section aria-labelledby="exts">
      <div class="sec-head"><h2 id="exts">PHP extensions</h2><span class="count"><?= count($exts) - count($missing) ?> of <?= count($exts) ?> loaded</span></div>
      <ul class="exts">
<?php foreach ($exts as $name => $on): ?>
        <li class="<?= $on ? 'on' : 'off' ?>"><?= $on ? $check : $cross ?><span><?= h($name) ?><?= $on ? '' : ' (missing)' ?></span></li>
<?php endforeach; ?>
      </ul>
<?php if ($missing): ?>
      <p class="fix">Turn extensions on with PHP extensions on the Configuration tab in Stackyard, then restart Apache.</p>
<?php endif; ?>
    </section>
<?php endif; ?>
  </main>

  <footer>
    <?php if ($local): ?>
    This page is <code><?= h($docroot . DIRECTORY_SEPARATOR . basename(__FILE__)) ?></code>. Replace it with your own site, or delete it.
    <?php else: ?>
    Served by Stackyard.
    <?php endif; ?>
  </footer>
</div>
<script>
(function () {
  var root = document.documentElement, btn = document.getElementById('theme');
  function current() {
    var t = root.getAttribute('data-theme');
    return t || (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
  }
  function label() { btn.textContent = current() === 'dark' ? 'Light theme' : 'Dark theme'; }
  btn.addEventListener('click', function () {
    var next = current() === 'dark' ? 'light' : 'dark';
    root.setAttribute('data-theme', next);
    try { localStorage.setItem('stackyard-theme', next); } catch (e) {}
    label();
  });
  label();
})();
</script>
</body>
</html>
