# -*- coding: utf-8 -*-
"""Špecifikácie grafov reportu o produktoch.

Spoločné stavebné kamene sú v src/common/charts_base.py — tu sú len grafy,
ktoré kreslí main_products.py.
"""

from src.common import charts_base as base
from src.common import constants as C
from src.common import formatting


def _above_below_colors(values, reference):
    """Modrá nad referenčnou hodnotou, červená pod ňou."""
    colors = []
    for value in values:
        colors.append(C.COLOR_BLUE if value >= reference else C.COLOR_RED)
    return colors


def entry_product_retention(worst, reference_pct):
    """Produkty s najhorším podielom návratov po prvej objednávke."""
    colors = _above_below_colors(worst["returned_pct"], reference_pct)
    return base.figure(
        "entry_product_retention",
        f"Vstupné produkty s najhorším podielom návratov (top {len(worst)})",
        f"V %. Podiel zákazníkov, ktorí sa po prvej objednávke vrátili, podľa "
        f"produktu, ktorý v tej prvej objednávke mali. Priemer naprieč všetkými "
        f"zákazníkmi je {formatting.format_pct(reference_pct)} — červené sú pod ním. "
        f"Zákazník sa počíta ku každému produktu zo svojej prvej objednávky. "
        f"Zahrnuté sú len produkty s aspoň {C.PRODUCT_MIN_CUSTOMERS} zákazníkmi. "
        f"{base.population_note(len(worst), 'produktmi')}",
        "bar",
        worst["short_label"],
        [base.series("Vrátili sa", worst["returned_pct"], C.COLOR_RED,
                     point_colors=colors)],
        height=520,
        index_axis="y",
        value_format="pct",
        hover_extras=base.kpi_hover(worst, lambda row: [
            f"Produkt: {row['label']}",
            f"Kód: {row.name}",
            f"Zákazníkov s ním v prvej objednávke: "
            f"{formatting.format_number(row['customers'])}",
            f"Z toho sa vrátilo: {formatting.format_number(row['returned'])}",
        ]),
    )


def basket_width(width, reference_pct):
    """Podiel návratov podľa šírky prvého košíka."""
    colors = _above_below_colors(width["returned_pct"], reference_pct)
    return base.figure(
        "basket_width",
        "Návrat podľa počtu rôznych produktov v prvej objednávke",
        f"V %. Na osi x počet rôznych produktov v prvej objednávke, na osi y "
        f"podiel zákazníkov, ktorí si objednali znova. Priemer je "
        f"{formatting.format_pct(reference_pct)}. Ak podiel s košíkom rastie, "
        f"šírka prvého nákupu je signál dostupný hneď v deň objednávky. "
        f"{base.population_note(int(width['customers'].sum()), 'zákazníkmi')}",
        "bar",
        width.index,
        [base.series("Vrátili sa", width["returned_pct"], C.COLOR_BLUE,
                     point_colors=colors)],
        value_format="pct",
        hover_extras=base.kpi_hover(width, lambda row: [
            f"Zákazníkov: {formatting.format_number(row['customers'])}",
            f"Medián prvej objednávky: {formatting.format_eur(row['median_gmv'])}",
        ]),
    )


def assortment_narrowing(left, right, left_label, right_label):
    """Šírka sortimentu v oknách pred koncom, odídení proti aktívnym."""
    return base.figure(
        "assortment_narrowing",
        "Šírka sortimentu pred odchodom",
        f"Priemerný počet rôznych produktov na účet v trojmesačnom okne. "
        f"U odídených sa okná počítajú od ich poslednej objednávky, u aktívnych "
        f"od {C.AS_OF:%-d. %-m. %Y}, takže sú porovnateľné. Ak sa krivka odídených "
        f"pred koncom zvažuje a krivka aktívnych nie, zúženie košíka je varovný "
        f"signál mesiace pred odchodom.",
        "line",
        left.index,
        [
            base.series(left_label, left["products"], C.COLOR_RED, chart_type="line"),
            base.series(right_label, right["products"], C.COLOR_TEAL, chart_type="line"),
        ],
        height=320,
        value_format="count",
    )


def dependence_split(split):
    """Účty podľa toho, akú časť ich GMV drží jeden produkt."""
    colors = [C.COLOR_TEAL, C.COLOR_BLUE, C.COLOR_ORANGE, C.COLOR_RED]
    return base.figure(
        "dependence_split",
        "Závislosť účtu na jedinom produkte",
        f"Počet účtov podľa toho, akú časť ich GMV tvorí ich najsilnejší produkt. "
        f"Účty pod {formatting.format_eur(C.PRODUCT_MIN_ACCOUNT_GMV)} sa nepočítajú "
        f"— pri nich je podiel jedného produktu náhoda. Účty vpravo sú krehké: "
        f"výpadok skladu alebo lacnejšia konkurencia zoberie celý účet. "
        f"{base.population_note(int(split['accounts'].sum()), 'účtami')}",
        "bar",
        split.index,
        [base.series("Účtov", split["accounts"], C.COLOR_BLUE, point_colors=colors)],
        value_format="count",
        hover_extras=base.kpi_hover(split, lambda row: [
            f"GMV skupiny: {formatting.format_eur(row['gmv'])}"
            f" ({formatting.format_pct(row['gmv_share_pct'])} portfólia)",
        ]),
    )
