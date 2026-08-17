# -*- coding: utf-8 -*-
"""Spoločné stavebné kamene špecifikácií grafov.

Každý graf v reporte je slovník serializovateľný do JSON. Prekladom do Chart.js
sa zaoberá JavaScript v report.py — Python tu nerieši formátovanie osí ani
tooltipov, len dáta a farby.

Tento modul obsahuje len to, čo používajú oba reporty. Konkrétne grafy sú
v charts.py jednotlivých reportov.

Štruktúra špecifikácie:
    id             — identifikátor canvasu
    title          — nadpis grafu
    caption        — komentár pod nadpisom
    height         — výška v pixeloch
    type           — "bar" alebo "line"
    labels         — popisky osi kategórií
    datasets       — zoznam sérií
    stacked        — či sa stĺpce stohujú
    index_axis     — "x" (zvislé stĺpce) alebo "y" (vodorovné)
    value_format   — formát čísiel: mil_eur, k_eur, eur, pct, count
    y_max          — voliteľný strop osi
"""

from src.common import constants as C
from src.common import formatting


def series(label, values, color, chart_type="bar", dashed=False,
           point_colors=None, value_format=None, overlay=False,
           hover_extras=None):
    """Jedna séria grafu.

    value_format prepíše formát čísiel grafu — použije sa, keď má séria inú
    jednotku ako zvyšok grafu (napríklad percentá vedľa absolútnych počtov).

    overlay=True vykreslí sériu cez predchádzajúcu, nie vedľa nej, a užšie —
    tak, aby spodná séria zostala po stranách vidieť. Slúži na porovnanie tej
    istej metriky nad dvoma datasetmi.

    hover_extras sú riadky do tooltipu patriace tejto sérii. Pri dvoch sériách
    nad rôznymi datasetmi nestačia riadky na úrovni grafu — tie sú spoločné pre
    obe série a ukázali by čísla len jedného datasetu.
    """
    return {
        "label": label,
        "data": [None if value is None else clean(value) for value in values],
        "color": color,
        "type": chart_type,
        "dashed": dashed,
        "point_colors": point_colors,
        "value_format": value_format,
        "overlay": overlay,
        "hover_extras": hover_extras,
    }


def clean(value):
    """Nahradí NaN hodnotou None, aby prežila serializáciu do JSON."""
    try:
        if value != value:
            return None
    except TypeError:
        return value
    return round(float(value), 4)


def figure(figure_id, title, caption, chart_type, labels, datasets, **options):
    """Zloží špecifikáciu grafu s predvolenými hodnotami."""
    figure = {
        "id": figure_id,
        "title": title,
        "caption": caption,
        "type": chart_type,
        "labels": list(labels),
        "datasets": datasets,
        "height": options.get("height", 300),
        "stacked": options.get("stacked", False),
        "index_axis": options.get("index_axis", "x"),
        "value_format": options.get("value_format", "count"),
        "y_max": options.get("y_max"),
        "y_begin_at_zero": options.get("y_begin_at_zero", True),
        "hover_extras": options.get("hover_extras"),
        "hover_mode": options.get("hover_mode"),
        "hover_font": options.get("hover_font"),
        "hover_labels_only": options.get("hover_labels_only", False),
        "selector": options.get("selector"),
    }
    return figure


def population_note(count, unit):
    """Veta na konec popisu: s akou populáciou graf pracuje.

    Každý graf v reporte stojí na inej skupine (všetci zákazníci / posudzované
    účty / účty aktívne v oboch oknách) a bez tejto vety to čitateľ z grafu
    nevyčíta — rozdielne počty potom vyzerajú ako chyba.
    """
    return f"Graf pracuje s {formatting.format_number(count)} {unit}."


def diverging_colors(values):
    """Modrá pre kladné hodnoty, červená pre záporné."""
    colors = []
    for value in values:
        if value is None or value < 0:
            colors.append(C.COLOR_RED)
        else:
            colors.append(C.COLOR_BLUE)
    return colors


def kpi_status_colors(values, reference_pct):
    """Zelená nad cieľom, červená pod referenčnou hodnotou, inak modrá."""
    colors = []
    for value in values:
        if value >= C.ACCOUNT_GROWTH_TARGET_PCT:
            colors.append(C.KPI_DIAG_COLOR_GOOD)
        elif value < reference_pct:
            colors.append(C.KPI_DIAG_COLOR_BAD)
        else:
            colors.append(C.KPI_DIAG_COLOR_NEUTRAL)
    return colors


def kpi_hover(rows, lines_fn):
    """Riadky do hover pre každý riadok tabuľky rezu."""
    lines = []
    for _, row in rows.iterrows():
        lines.append(lines_fn(row))
    return lines
