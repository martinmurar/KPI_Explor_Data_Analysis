# -*- coding: utf-8 -*-
"""Vykreslenie HTML reportu.

Tabuľky sa generujú z DataFrame-ov, nie sú napísané natvrdo — pri novom exporte
dát sa prepočítajú spolu s grafmi. Čísla v komentároch sa vkladajú cez f-stringy
z rovnakých metrík, ktoré kreslia grafy, takže nemôžu zostať zastarané.
"""

import html
import json
import re

import pandas as pd

from src.common import formatting

CHARTJS_CDN = "https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.js"

STYLESHEET = """
:root{--ink:#141413;--ink2:#52514e;--mut:#898781;--bd:#e1e0d9;--bg:#faf9f5;--card:#fff}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
 font:400 16px/1.7 -apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif;
 -webkit-font-smoothing:antialiased}
.wrap{max-width:1000px;margin:0 auto;padding:48px 28px 80px}
h1{font-size:30px;font-weight:500;margin:0 0 6px;letter-spacing:-.01em}
h2{font-size:21px;font-weight:500;margin:56px 0 14px;padding-bottom:10px;border-bottom:1px solid var(--bd)}
h3{font-size:16px;font-weight:500;margin:32px 0 10px}
p{margin:0 0 14px}
.lead{color:var(--ink2);font-size:15px;margin-bottom:28px}
.small{font-size:13px;color:var(--mut)}
/* border-collapse:separate, nie collapse — Safari pri collapse position:sticky
   na hlavičke ignoruje. Čiary medzi riadkami kreslí border-bottom buniek,
   takže vzhľad je rovnaký. */
table{border-collapse:separate;border-spacing:0;width:100%;font-size:13.5px;
 margin:14px 0 22px}
th,td{padding:7px 10px;text-align:right;border-bottom:1px solid var(--bd)}
/* Hlavička zostáva na vrchu aj po odrolovaní. */
th{font-weight:500;color:var(--ink2);background:#f3f2ec;
 position:sticky;top:0;z-index:1}
th:first-child,td:first-child{text-align:left}
tr:hover td{background:#f7f6f1}
.fig{background:var(--card);border:1px solid var(--bd);border-radius:12px;
 padding:18px 20px 20px;margin:20px 0 28px}
.fig h4{margin:0 0 2px;font-size:14.5px;font-weight:500}
.fig .cap{font-size:12.5px;color:var(--mut);margin:0 0 14px}
.cv{position:relative;width:100%}
.cols{display:grid;grid-template-columns:1fr 1fr;gap:22px;align-items:start;
 margin-inline:-110px}
.cols h3{margin-top:0}
.cols .fig{margin:16px 0 20px}
@media (max-width:1280px){.cols{margin-inline:0}}
@media (max-width:900px){.cols{grid-template-columns:1fr}}
.lg{display:flex;flex-wrap:wrap;gap:14px;margin:0 0 12px;font-size:12px;color:var(--ink2)}
.lg span{display:flex;align-items:center;gap:5px}
.lg i{width:10px;height:10px;border-radius:2px;display:inline-block}
.kpi{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin:22px 0 8px}
.kpi div{background:#f3f2ec;border-radius:8px;padding:14px 16px}
.kpi .l{font-size:12.5px;color:var(--mut);margin:0 0 4px}
.kpi .v{font-size:23px;font-weight:500;margin:0}
.note{background:#f3f2ec;border-left:3px solid #eb6834;padding:14px 18px;margin:20px 0;
 font-size:14.5px;border-radius:0 8px 8px 0}
ol,ul{margin:0 0 14px;padding-left:22px}
li{margin-bottom:7px}
.neg{color:#a32d2d}.pos{color:#0f6e56}
.sec>summary{font-size:21px;font-weight:500;margin:56px 0 14px;padding-bottom:10px;
 border-bottom:1px solid var(--bd);cursor:pointer;list-style:none;
 display:flex;align-items:center;gap:10px;user-select:none}
.sec>summary::-webkit-details-marker{display:none}
.sec>summary:hover{color:var(--ink2)}
.sec>summary::before{content:"";width:0;height:0;flex:none;
 border-left:6px solid var(--mut);border-top:5px solid transparent;
 border-bottom:5px solid transparent;transition:transform .15s}
.sec[open]>summary::before{transform:rotate(90deg)}
.sec:not([open])>summary{margin-bottom:0}
.sec:not([open])+.sec>summary{margin-top:22px}
.roll>summary{font-size:14px;font-weight:500;color:var(--ink2);cursor:pointer;
 list-style:none;display:flex;align-items:center;gap:8px;user-select:none;margin:24px 0 0}
.roll>summary::-webkit-details-marker{display:none}
.roll>summary:hover{color:var(--ink)}
.roll>summary::before{content:"";width:0;height:0;flex:none;
 border-left:5px solid var(--mut);border-top:4px solid transparent;
 border-bottom:4px solid transparent;transition:transform .15s}
.roll[open]>summary::before{transform:rotate(90deg)}
.sel{display:flex;align-items:center;gap:8px;margin:0 0 12px;font-size:12.5px;color:var(--ink2)}
.sel select,.sel input{font:inherit;font-size:12.5px;color:var(--ink);
 background:var(--card);border:1px solid var(--bd);border-radius:7px;
 padding:5px 10px;max-width:100%}
.sel input{width:180px}
.sel input::placeholder{color:var(--mut)}
.sel .hit{color:var(--mut);font-size:12px}
.fold{display:flex;gap:8px;margin:26px 0 0}
.fold button{font:inherit;font-size:13px;color:var(--ink2);background:var(--card);
 border:1px solid var(--bd);border-radius:7px;padding:5px 12px;cursor:pointer}
.fold button:hover{background:#f3f2ec}
@media print{.fold{display:none}}
"""

CHART_BUILDER_JS = """
const GRID = {color:'#e1e0d9', drawTicks:false};
const NO_GRID = {display:false};

Chart.defaults.font.family = '-apple-system,BlinkMacSystemFont,Segoe UI,Helvetica,Arial,sans-serif';
Chart.defaults.font.size = 12;
Chart.defaults.color = '#898781';

const FORMATTERS = {
  mil_eur: {tick: v => v.toFixed(1), tip: v => v.toFixed(2) + ' mil. €'},
  k_eur:   {tick: v => v + 'k',      tip: v => Math.round(v).toLocaleString('sk-SK') + ' tis. €'},
  eur:     {tick: v => v.toLocaleString('sk-SK'), tip: v => Math.round(v).toLocaleString('sk-SK') + ' €'},
  pct:     {tick: v => v + ' %',     tip: v => v.toFixed(1) + ' %'},
  count:   {tick: v => v.toLocaleString('sk-SK'), tip: v => Math.round(v).toLocaleString('sk-SK')}
};

function buildDataset(series, spec) {
  const isLine = series.type === 'line';
  const dataset = {
    type: series.type,
    label: series.label,
    data: series.data,
    valueFormat: series.value_format || spec.value_format
  };
  if (isLine) {
    dataset.borderColor = series.color;
    dataset.borderWidth = 2.5;
    dataset.pointRadius = 3;
    dataset.pointBackgroundColor = series.color;
    dataset.tension = 0.25;
    dataset.fill = false;
    dataset.order = 0;
    if (series.dashed) { dataset.borderDash = [6, 4]; dataset.borderWidth = 2; }
    // V stohovanom grafe Chart.js stohuje aj línie. Vlastná stack skupina pre
    // každú líniu ich drží nezávislé — bez toho sa druhá línia vykreslí ako
    // súčet s prvou a pri y_max = 100 vypadne z grafu.
    if (spec.stacked) { dataset.stack = 'line-' + series.label; }
  } else {
    dataset.hoverExtras = series.hover_extras || null;
    dataset.backgroundColor = series.point_colors || series.color;
    dataset.borderRadius = 3;
    dataset.order = 1;
    if (spec.stacked) { dataset.stack = 'total'; }
    // grouped:false vykreslí sériu cez predchádzajúcu namiesto vedľa nej.
    // Užší stĺpec necháva spodnú sériu po stranách vidieť, order:0 ju kreslí
    // navrch — bez toho by ju spodná séria prekryla.
    if (series.overlay) {
      dataset.grouped = false;
      dataset.barPercentage = 0.5;
      dataset.categoryPercentage = 0.9;
      dataset.order = 0;
    }
  }
  return dataset;
}

function buildValueAxis(spec) {
  const formatter = FORMATTERS[spec.value_format];
  return {
    stacked: spec.stacked,
    beginAtZero: spec.y_begin_at_zero,
    max: spec.y_max,
    grid: GRID,
    border: {display: false},
    ticks: {callback: formatter.tick}
  };
}

function buildCategoryAxis(spec) {
  return {
    stacked: spec.stacked,
    grid: NO_GRID,
    border: {color: '#c3c2b7'},
    ticks: {autoSkip: spec.labels.length > 24, maxRotation: 60, maxTicksLimit: 26}
  };
}

function buildChart(spec) {
  const horizontal = spec.index_axis === 'y';
  const valueAxis = buildValueAxis(spec);
  const categoryAxis = buildCategoryAxis(spec);

  const chart = new Chart(document.getElementById(spec.id), {
    data: {
      labels: spec.labels,
      datasets: spec.datasets.map(series => buildDataset(series, spec))
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      indexAxis: spec.index_axis,
      // hover_mode 'index' ukáže v jednom tooltipe všetky série daného koša.
      // Pri prekryte je to jediný spôsob, ako sa dostať k číslam série, ktorú
      // tá druhá celou šírkou zakrýva.
      //
      // axis musí sedieť s indexAxis. Bez toho Chart.js hľadá najbližší prvok
      // po osi x aj vo vodorovnom grafe, takže pri kurzore nad krátkym stĺpcom
      // trafí ten kôš, ktorého dĺžka je náhodou najbližšie — typicky najdlhší.
      interaction: spec.hover_mode
        ? {mode: spec.hover_mode, intersect: false, axis: horizontal ? 'y' : 'x'}
        : {mode: 'nearest', intersect: true},
      plugins: {
        legend: {display: false},
        tooltip: {
          // Neproporcionálne písmo drží stĺpce zarovnanej tabuľky pod sebou.
          bodyFont: spec.hover_font === 'mono'
            ? {family: 'ui-monospace, SFMono-Regular, Menlo, Consolas, monospace'}
            : {},
          // Poradie sérií v tooltipe má sedieť s poradím v legende, nie
          // s poradím kreslenia — prekrytá séria sa kreslí navrch a bez tohto
          // by v tooltipe skočila na prvé miesto.
          itemSort: (a, b) => a.datasetIndex - b.datasetIndex,
          callbacks: {
          label: item => {
            // hover_labels_only: hodnota je v zarovnanej tabuľke nižšie, tu
            // zostáva len názov série s farebným štvorčekom ako legenda.
            if (spec.hover_labels_only) { return item.dataset.label; }
            const value = horizontal ? item.parsed.x : item.parsed.y;
            const format = item.dataset.valueFormat;
            return item.dataset.label + ': ' + FORMATTERS[format].tip(value);
          },
          afterBody: items => {
            // Riadky na úrovni série majú prednosť: pri dvoch sériách nad
            // rôznymi datasetmi sú spoločné riadky grafu nepoužiteľné, lebo
            // by ku každej sérii vypísali čísla toho istého datasetu.
            const perSeries = items.filter(item => item.dataset.hoverExtras);
            if (perSeries.length) {
              // Názov série sa pred riadky píše len keď je sérií viac. Pri
              // jednej by len zopakoval to, čo je o riadok vyššie pri hodnote.
              const named = perSeries.length > 1;
              const lines = [];
              perSeries.forEach(item => {
                if (named) { lines.push(item.dataset.label + ':'); }
                (item.dataset.hoverExtras[item.dataIndex] || []).forEach(
                  line => lines.push(named ? '  ' + line : line));
              });
              return lines;
            }
            if (!spec.hover_extras) { return []; }
            return spec.hover_extras[items[0].dataIndex] || [];
          }
        }}
      },
      scales: horizontal
        ? {x: valueAxis, y: categoryAxis}
        : {x: categoryAxis, y: valueAxis}
    }
  });

  if (spec.selector) { wireSelector(spec, chart); }
}

// Prepínač série. Prekresľujú sa len dáta a názov série — popisky osi zostávajú,
// preto musia mať všetky série rovnakú dĺžku (o to sa stará Python).
function wireSelector(spec, chart) {
  const select = document.getElementById('sel-' + spec.id);
  if (!select) { return; }

  const apply = () => {
    const chosen = select.value;
    chart.data.datasets[0].data = spec.selector.series[chosen];
    chart.data.datasets[0].label = select.options[select.selectedIndex].text;
    // Riadky hoveru patria k účtu, nie ku grafu — musia sa prepnúť spolu
    // s dátami, inak by pri druhom účte ostali počty objednávok toho prvého.
    if (spec.selector.hover) {
      chart.data.datasets[0].hoverExtras = spec.selector.hover[chosen];
    }
    chart.update();
  };

  select.addEventListener('change', apply);
  wireSelectorSearch(spec, select, apply);
  apply();
}

// Hľadanie v prepínači. Zoznam sa neskrýva cez CSS, ale prestavuje — skrývanie
// jednotlivých <option> prehliadače nerobia rovnako. Keď hľadanie nenájde nič,
// zostáva celý zoznam, aby graf nikdy neostal bez dát.
function wireSelectorSearch(spec, select, apply) {
  const search = document.getElementById('q-' + spec.id);
  const hits = document.getElementById('hit-' + spec.id);
  if (!search) { return; }

  const all = spec.selector.options;
  search.addEventListener('input', () => {
    const needle = plainText(search.value);
    const matching = all.filter(option => plainText(option.label).includes(needle));
    const shown = matching.length ? matching : all;

    fillOptions(select, shown);
    if (hits) {
      hits.textContent = needle && matching.length ? shown.length + ' nájdených'
                       : needle ? 'nič nenájdené' : '';
    }
    apply();
  });
}

// Porovnáva sa bez diakritiky a bez veľkých písmen, aby „decathlon" našiel
// aj účet písaný s diakritikou alebo veľkými písmenami.
function plainText(text) {
  return text.normalize('NFD').replace(/[\\u0300-\\u036f]/g, '').toLowerCase();
}

function fillOptions(select, options) {
  const chosen = select.value;
  select.innerHTML = '';
  for (const option of options) {
    const element = document.createElement('option');
    element.value = option.value;
    element.textContent = option.label;
    select.appendChild(element);
  }
  if (options.some(option => option.value === chosen)) { select.value = chosen; }
}

SPECS.forEach(buildChart);
"""

# Zbaľovanie sekcií. Beží vo vlastnom <script> pred Chart.js a nezávisí od neho —
# keby bolo v tom istom bloku, zlyhané načítanie knižnice z CDN (offline, proxy)
# by zhodilo aj zbaľovanie a report by ostal natrvalo rozbalený.
#
# Grafy sa kreslia raz, pri načítaní, keď sú všetky sekcie otvorené — Chart.js
# potrebuje nenulovú šírku kontajnera. Zbalenie ich preto nezničí, len skryje;
# po rozbalení si responsive layout poradí sám.
FOLD_TOOLBAR_HTML = """<div class="fold">
<button type="button" data-fold="open">Rozbaliť všetko</button>
<button type="button" data-fold="close">Zbaliť všetko</button>
</div>"""

FOLD_JS = """
const SECTIONS = document.querySelectorAll('details.sec');

document.querySelectorAll('.fold button').forEach(button => {
  button.addEventListener('click', () => {
    const shouldOpen = button.dataset.fold === 'open';
    SECTIONS.forEach(section => { section.open = shouldOpen; });
  });
});

// Zbalená sekcia sa nevytlačí. Pred tlačou sa všetky otvoria a po nej vráti
// späť, aby si používateľ nemusel pamätať, čo mal rozbalené.
let foldedBeforePrint = [];
window.addEventListener('beforeprint', () => {
  foldedBeforePrint = [...SECTIONS].filter(section => !section.open);
  foldedBeforePrint.forEach(section => { section.open = true; });
});
window.addEventListener('afterprint', () => {
  foldedBeforePrint.forEach(section => { section.open = false; });
});
"""


# ── formátovanie čísiel ───────────────────────────────────────────────────────
# Preposielané zo spoločného modulu, aby ich sections.py mohol brať odtiaľto.
format_number = formatting.format_number
format_eur = formatting.format_eur
format_pct = formatting.format_pct
format_signed_eur = formatting.format_signed_eur
format_signed_pct = formatting.format_signed_pct


# ── HTML komponenty ───────────────────────────────────────────────────────────
def render_table(table, columns, index_label="", show_index=True):
    """Vykreslí DataFrame ako HTML tabuľku.

    columns je zoznam trojíc (názov stĺpca, hlavička, formátovacia funkcia).
    show_index=False sa použije, keď tabuľka už má vlastný popisný stĺpec
    a index by sa v nej zobrazil dvakrát.
    """
    header_cells = []
    if show_index:
        header_cells.append(f"<th>{escape(index_label)}</th>")
    for _, header, _ in columns:
        header_cells.append(f"<th>{escape(header)}</th>")

    body_rows = []
    for index, row in table.iterrows():
        cells = []
        if show_index:
            cells.append(f"<td>{_index_text(index)}</td>")
        for column, _, formatter in columns:
            value = row[column]
            cells.append(f"<td>{_cell_html(value, formatter)}</td>")
        body_rows.append("<tr>" + "".join(cells) + "</tr>")

    return ("<table><thead><tr>" + "".join(header_cells) + "</tr></thead><tbody>"
            + "".join(body_rows) + "</tbody></table>")


def escape(text):
    """Escapuje text pre HTML.

    Nutné pre popisky pásiem ako "<0,5k €" — bez escapovania ich prehliadač
    interpretuje ako začiatok tagu a popisok zmizne.
    """
    return html.escape(str(text))


class Html(str):
    """Text, ktorý je už hotové HTML a v tabuľke sa nemá escapovať.

    render_table štandardne escapuje všetko, čo formátovacia funkcia vráti —
    inak by názov firmy so znakom „&“ rozbil tabuľku. Odkaz je jediný prípad,
    kde chceme, aby sa značka naozaj vykreslila.
    """


def render_link(url, text):
    """Odkaz do bunky tabuľky. Prázdna URL vráti pomlčku."""
    if not url:
        return Html("—")
    return Html(f'<a href="{escape(url)}" target="_blank" '
                f'rel="noreferrer">{escape(text)}</a>')


def _index_text(index):
    """Textová podoba indexu tabuľky."""
    return escape(index)


def _cell_html(value, formatter):
    """Obsah jednej celly, so zafarbením negatívnych čísiel."""
    formatted = formatter(value)
    if isinstance(formatted, Html):
        text = formatted
    else:
        text = escape(formatted)
    is_number = isinstance(value, (int, float)) and not pd.isna(value)
    if is_number and value < 0:
        return f'<span class="neg">{text}</span>'
    return text


def render_figure(spec):
    """Vykreslí kontejner grafu vrátane legendy."""
    legend_items = []
    for series in spec["datasets"]:
        color = series["color"]
        label = escape(series["label"])
        legend_items.append(f'<span><i style="background:{color}"></i>{label}</span>')
    legend = '<div class="lg">' + "".join(legend_items) + "</div>"

    return (f'<div class="fig"><h4>{escape(spec["title"])}</h4>'
            f'<p class="cap">{escape(spec["caption"])}</p>{legend}'
            f'{_render_selector(spec)}'
            f'<div class="cv" style="height:{spec["height"]}px">'
            f'<canvas id="{spec["id"]}"></canvas></div></div>')


def _render_selector(spec):
    """Rozbaľovací zoznam nad grafom, ak graf prepína medzi sériami.

    Vykresľuje sa len HTML; naviazanie na graf robí JS v CHART_BUILDER_JS.
    """
    selector = spec.get("selector")
    if not selector:
        return ""

    options = []
    for option in selector["options"]:
        options.append(f'<option value="{escape(option["value"])}">'
                       f'{escape(option["label"])}</option>')
    return (f'<div class="sel"><label for="sel-{spec["id"]}">'
            f'{escape(selector["label"])}</label>'
            f'<input type="search" id="q-{spec["id"]}" autocomplete="off" '
            f'placeholder="hľadať účet…" aria-label="Hľadať v zozname">'
            f'<select id="sel-{spec["id"]}">' + "".join(options) + "</select>"
            f'<span class="hit" id="hit-{spec["id"]}"></span></div>')


def render_kpi_cards(cards):
    """Vykreslí prehľadové karty. cards je zoznam dvojíc (popis, hodnota)."""
    blocks = []
    for label, value in cards:
        blocks.append(f'<div><p class="l">{escape(label)}</p>'
                      f'<p class="v">{escape(value)}</p></div>')
    return '<div class="kpi">' + "".join(blocks) + "</div>"


def render_rollup(title, content):
    """Zabalí obsah do zroloateľného bloku s vlastným nadpisom.

    Na dlhé tabuľky, ktoré patria do reportu ako podklad, ale nemajú ho zaberať
    celý. Na rozdiel od render_collapsible sa nepoužíva na celé sekcie.
    """
    return (f'<details class="roll"><summary>{escape(title)}</summary>\n'
            f"{content}</details>")


def render_columns(rows):
    """Dvojice blokov vedľa seba, na priame porovnanie.

    rows je zoznam dvojíc (vľavo, vpravo). Každá dvojica je jeden riadok
    mriežky, takže si oba stĺpce držia rovnakú výšku aj vtedy, keď je text
    v jednom z nich dlhší — bez toho by sa grafy postupne rozišli a porovnať
    by sa nedali.

    Na užších obrazovkách sa stĺpce zložia pod seba; grafy vedľa seba majú
    zmysel len dovtedy, kým sú dosť široké na to, aby sa dali čítať.
    """
    cells = []
    for left, right in rows:
        cells.append(f"<div>{left}</div><div>{right}</div>")
    return '<div class="cols">' + "".join(cells) + "</div>"


def render_note(text):
    return f'<div class="note">{text}</div>'


def render_collapsible(section_html):
    """Zabalí sekciu do <details>, aby sa dala zbaliť za jej nadpis.

    Nadpis sekcie je prvý <h2> — ten sa stane <summary> a zvyšok telom.
    Sekcia bez <h2> (hlavička reportu) sa vráti nedotknutá.
    """
    match = re.search(r"<h2>(.*?)</h2>", section_html, re.S)
    if match is None:
        return section_html

    title = match.group(1)
    body = section_html[match.end():]
    return (f'<details class="sec" open><summary>{title}</summary>\n'
            f"{body}</details>")


def render_document(title, body_html, specs):
    """Zloží celý HTML dokument."""
    specs_json = json.dumps(specs, ensure_ascii=False)
    return f"""<!doctype html>
<html lang="sk"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<style>{STYLESHEET}</style></head>
<body><div class="wrap">
{body_html}
</div>
<script>{FOLD_JS}</script>
<script src="{CHARTJS_CDN}"></script>
<script>const SPECS = {specs_json};
{CHART_BUILDER_JS}</script>
</body></html>"""
