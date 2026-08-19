#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Rozcestník: jedna stránka so záložkami pre všetky tri reporty.

Reporty sa nemenia a zostávajú samostatné súbory — rozcestník ich len vkladá
cez <iframe>. Vďaka tomu sa dá ktorýkoľvek otvoriť aj priamo a regenerovať
nezávisle od ostatných.

Záložky sa načítavajú až pri prvom otvorení. Drill-in má takmer pol megabajtu,
takže načítať všetky tri naraz by otvorenie rozcestníka zbytočne spomalilo.

S prepínačom --build sa najprv prepočíta všetko ostatné: cache položiek
objednávok a všetky tri reporty. Každý krok beží vo vlastnom procese — prechod
4 GB súborom si vypýta pamäť a nie je dôvod držať ju až do konca buildu.

Použitie:
    python3 -m src.portal.main_portal
    python3 -m src.portal.main_portal --build
    python3 -m src.portal.main_portal --build --rebuild-items
"""

import argparse
import os
import subprocess
import sys
import time

from src.common import constants as C
from src.common import report

# Poradie krokov kompletného buildu. Cache položiek je prvá, stojí na nej
# drill-in aj report o produktoch. Krok označený rebuildable vie zahodiť
# existujúcu cache a prejsť zdrojový súbor znova.
BUILD_STEPS = [
    {"label": "cache položiek objednávok",
     "module": "src.drill_in.build_order_items", "rebuildable": True},
    {"label": "hlavný report", "module": "src.main_report.main"},
    {"label": "drill-in report", "module": "src.drill_in.main_drill_in"},
    {"label": "report o produktoch", "module": "src.products.main_products"},
]

STYLESHEET = """
:root{--ink:#141413;--ink2:#52514e;--mut:#898781;--bd:#e1e0d9;--bg:#faf9f5;--card:#fff}
*{box-sizing:border-box}
html,body{height:100%}
body{margin:0;background:var(--bg);color:var(--ink);display:flex;flex-direction:column;
 font:400 16px/1.7 -apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif}
.bar{display:flex;align-items:center;gap:4px;flex:none;padding:0 20px;
 background:var(--card);border-bottom:1px solid var(--bd)}
.bar .name{font-size:14px;font-weight:500;color:var(--mut);margin-right:18px;
 white-space:nowrap}
.bar button{font:inherit;font-size:14px;color:var(--ink2);background:none;border:0;
 border-bottom:2px solid transparent;padding:14px 14px 11px;cursor:pointer;
 white-space:nowrap}
.bar button:hover{color:var(--ink)}
.bar button[aria-selected="true"]{color:var(--ink);border-bottom-color:#eb6834}
.bar a{margin-left:auto;font-size:13px;color:var(--mut);text-decoration:none;
 padding:0 4px}
.bar a:hover{color:var(--ink)}
.panes{position:relative;flex:1;min-height:0}
iframe{position:absolute;inset:0;width:100%;height:100%;border:0;background:var(--bg)}
iframe[hidden]{display:none}
.missing{position:absolute;inset:0;display:flex;align-items:center;
 justify-content:center;padding:40px;text-align:center;color:var(--ink2)}
.missing code{background:#f3f2ec;border-radius:5px;padding:2px 6px;font-size:13px}
"""

SCRIPT = """
const BUTTONS = [...document.querySelectorAll('.bar button')];
const PANES = [...document.querySelectorAll('.panes > *')];

function show(index) {
  BUTTONS.forEach((button, position) => {
    button.setAttribute('aria-selected', String(position === index));
  });
  PANES.forEach((pane, position) => {
    pane.hidden = position !== index;
  });

  // Záložka sa načíta až keď ju niekto naozaj otvorí.
  const pane = PANES[index];
  if (pane.dataset.src && !pane.src) { pane.src = pane.dataset.src; }

  const open = document.getElementById('open-tab');
  open.href = PANES[index].dataset.src || '#';
  location.hash = index ? 'tab' + (index + 1) : '';
}

BUTTONS.forEach((button, index) => button.addEventListener('click', () => show(index)));

const FROM_HASH = parseInt(location.hash.replace('#tab', ''), 10) - 1;
show(Number.isInteger(FROM_HASH) && FROM_HASH >= 0 && FROM_HASH < PANES.length
     ? FROM_HASH : 0);
"""


def _tab_button(label, index):
    """Tlačidlo jednej záložky."""
    return (f'<button type="button" role="tab" '
            f'aria-selected="{"true" if index == 0 else "false"}">'
            f"{report.escape(label)}</button>")


def _tab_pane(path, index):
    """Rám s reportom, alebo odkaz na to, čo treba spustiť, ak súbor chýba."""
    name = os.path.basename(path)
    hidden = "" if index == 0 else " hidden"

    if not os.path.exists(path):
        return (f'<div class="missing"{hidden} data-src="">'
                f"<p>Report <code>{report.escape(name)}</code> ešte nie je "
                f"vygenerovaný.</p></div>")

    return f'<iframe data-src="{report.escape(name)}" title="{report.escape(name)}"{hidden}></iframe>'


def render_portal(tabs):
    """Zloží HTML rozcestníka. tabs je zoznam dvojíc (názov, cesta k reportu)."""
    buttons = []
    panes = []
    for index, (label, path) in enumerate(tabs):
        buttons.append(_tab_button(label, index))
        panes.append(_tab_pane(path, index))

    return f"""<!doctype html>
<html lang="sk"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>B2B analýzy</title>
<style>{STYLESHEET}</style></head>
<body>
<nav class="bar" role="tablist">
<span class="name">B2B analýzy</span>
{"".join(buttons)}
<a id="open-tab" target="_blank" rel="noreferrer">Otvoriť samostatne ↗</a>
</nav>
<main class="panes">
{"".join(panes)}
</main>
<script>{SCRIPT}</script>
</body></html>
"""


# ── kompletný build ───────────────────────────────────────────────────────────
def build_environment():
    """Prostredie s koreňom projektu v PYTHONPATH, aby `-m src...` fungovalo."""
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(C.PROJECT_ROOT)
    return environment


def step_command(step, rebuild_items):
    """Príkaz jedného kroku."""
    command = [sys.executable, "-m", step["module"]]
    if rebuild_items and step.get("rebuildable"):
        command.append("--rebuild")
    return command


def run_step(step, rebuild_items):
    """Spustí jeden krok a povie, či prešiel. Výstup ide rovno na konzolu."""
    print(f"\n── {step['label']} ──", flush=True)
    started = time.monotonic()
    result = subprocess.run(step_command(step, rebuild_items),
                            cwd=str(C.PROJECT_ROOT), env=build_environment())
    print(f"   {step['label']}: {time.monotonic() - started:.0f} s")
    return result.returncode == 0


def run_build(rebuild_items):
    """Všetky kroky v poradí. Pri prvom zlyhaní sa build zastaví.

    Zastavuje sa zámerne — každý ďalší krok stojí na výstupe predchádzajúceho
    a report postavený na polovičných dátach je horší než žiadny.
    """
    started = time.monotonic()
    for step in BUILD_STEPS:
        if not run_step(step, rebuild_items):
            print(f"\nkrok „{step['label']}“ zlyhal — build zastavený")
            return False

    print(f"\nvšetky kroky hotové za {time.monotonic() - started:.0f} s")
    return True


def parse_arguments():
    parser = argparse.ArgumentParser(description="Rozcestník reportov")
    parser.add_argument("--output", default=C.OUTPUT_HTML_PORTAL)
    parser.add_argument("--build", action="store_true",
                        help="pred rozcestníkom prepočítať dáta a všetky reporty")
    parser.add_argument("--rebuild-items", action="store_true",
                        help="pri --build znova prejsť 4 GB súbor s položkami")
    return parser.parse_args()


def main():
    arguments = parse_arguments()

    if arguments.build and not run_build(arguments.rebuild_items):
        return 1

    html = render_portal(C.PORTAL_TABS)

    with open(arguments.output, "w", encoding="utf-8") as output_file:
        output_file.write(html)

    missing = [label for label, path in C.PORTAL_TABS if not os.path.exists(path)]
    print(f"hotovo: {arguments.output} ({len(C.PORTAL_TABS)} záložiek)")
    if missing:
        print(f"chýbajúce reporty: {', '.join(missing)}")
    return 0


# python3 -m src.portal.main_portal --build --rebuild-items
if __name__ == "__main__":
    sys.exit(main())
