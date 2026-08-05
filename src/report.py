# -*- coding: utf-8 -*-
"""Vykreslenie HTML reportu.

Tabuľky sa generujú z DataFrame-ov, nie sú napísané natvrdo — pri novom exporte
dát sa prepočítajú spolu s grafmi. Čísla v komentároch sa vkladajú cez f-stringy
z rovnakých metrík, ktoré kreslia grafy, takže nemôžu zostať zastarané.
"""

import html
import json

import pandas as pd

import formatting

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
table{border-collapse:collapse;width:100%;font-size:13.5px;margin:14px 0 22px}
th,td{padding:7px 10px;text-align:right;border-bottom:1px solid var(--bd)}
th{font-weight:500;color:var(--ink2);background:#f3f2ec}
th:first-child,td:first-child{text-align:left}
tr:hover td{background:#f7f6f1}
.fig{background:var(--card);border:1px solid var(--bd);border-radius:12px;
 padding:18px 20px 20px;margin:20px 0 28px}
.fig h4{margin:0 0 2px;font-size:14.5px;font-weight:500}
.fig .cap{font-size:12.5px;color:var(--mut);margin:0 0 14px}
.cv{position:relative;width:100%}
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
  } else {
    dataset.backgroundColor = series.point_colors || series.color;
    dataset.borderRadius = 3;
    dataset.order = 1;
    if (spec.stacked) { dataset.stack = 'total'; }
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

  new Chart(document.getElementById(spec.id), {
    data: {
      labels: spec.labels,
      datasets: spec.datasets.map(series => buildDataset(series, spec))
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      indexAxis: spec.index_axis,
      plugins: {
        legend: {display: false},
        tooltip: {callbacks: {
          label: item => {
            const value = horizontal ? item.parsed.x : item.parsed.y;
            const format = item.dataset.valueFormat;
            return item.dataset.label + ': ' + FORMATTERS[format].tip(value);
          },
          afterBody: items => {
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
}

SPECS.forEach(buildChart);
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


def _index_text(index):
    """Textová podoba indexu tabuľky."""
    return escape(index)


def _cell_html(value, formatter):
    """Obsah jednej celly, so zafarbením negatívnych čísiel."""
    text = escape(formatter(value))
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
            f'<div class="cv" style="height:{spec["height"]}px">'
            f'<canvas id="{spec["id"]}"></canvas></div></div>')


def render_kpi_cards(cards):
    """Vykreslí prehľadové karty. cards je zoznam dvojíc (popis, hodnota)."""
    blocks = []
    for label, value in cards:
        blocks.append(f'<div><p class="l">{escape(label)}</p>'
                      f'<p class="v">{escape(value)}</p></div>')
    return '<div class="kpi">' + "".join(blocks) + "</div>"


def render_note(text):
    return f'<div class="note">{text}</div>'


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
<script src="{CHARTJS_CDN}"></script>
<script>const SPECS = {specs_json};
{CHART_BUILDER_JS}</script>
</body></html>"""
