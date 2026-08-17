# -*- coding: utf-8 -*-
"""Špecifikácie grafov reportu Account growth drill-in.

Spoločné stavebné kamene sú v src/common/charts_base.py — tu sú len grafy,
ktoré kreslí main_drill_in.py.
"""

from src.common import charts_base as base
from src.common import constants as C
from src.common import formatting


def kpi_by_order_count(breakdown, reference_pct, filtered=None):
    """KPI osobitne pre každý kôš podľa počtu objednávok za rok.

    Ak je zadaný filtered, vykreslí sa ako užšia svetlá séria cez plnú — ten
    istý rez nad datasetom bez spodných extrémov. Prekryv namiesto stĺpcov
    vedľa seba drží obe hodnoty na tej istej pozícii, takže rozdiel medzi nimi
    je vidieť ako presah spodnej série, nie ako vzdialenosť dvoch stĺpcov.
    """
    values = list(breakdown["growing_pct"])
    series = [base.series("Celý dataset", values, C.KPI_DIAG_COLOR_NEUTRAL,
                      point_colors=base.kpi_status_colors(values, reference_pct))]
    if filtered is None:
        hover = _order_count_hover(breakdown)
    else:
        series.append(base.series("Bez spodných extrémov", list(filtered["growing_pct"]),
                              C.COLOR_BLUE_LIGHT, overlay=True))
        hover = _order_count_comparison_hover(breakdown, filtered)

    return base.figure(
        "kpi_by_order_count",
        f"Account growth podľa počtu objednávok za {C.FREQUENCY_WINDOW_MONTHS} mesiacov",
        f"V %. Kôš určuje počet objednávok za posledných {C.FREQUENCY_WINDOW_MONTHS} "
        f"mesiacov. {base.population_note(int(breakdown['customers'].sum()), 'posudzovanými účtami')} "
        f"Farba spodnej série: zelená nad cieľom {C.ACCOUNT_GROWTH_TARGET_PCT} %, "
        f"červená pod celkovým KPI. Svetlá séria navrchu je ten istý rez nad datasetom "
        f"bez zákazníkov s celoživotným GMV pod "
        f"{formatting.format_eur(C.SMALL_VETERAN_LIFETIME_GMV)}, ktorí sú zároveň starší "
        f"ako {C.SMALL_VETERAN_AGE_MONTHS} mesiacov.",
        "bar",
        breakdown.index,
        series,
        height=max(200, 40 * len(breakdown) + 60),
        index_axis="y",
        value_format="pct",
        y_max=100,
        hover_mode="index",
        hover_extras=hover,
        hover_font="mono",
        hover_labels_only=filtered is not None,
    )


# Popisky riadkov porovnávacej tabuľky v hoveri a stĺpce, z ktorých sa plnia.
ORDER_COUNT_HOVER_ROWS = [
    ("% rastúcich", "growing_pct", formatting.format_pct),
    ("Účtov", "customers", formatting.format_number),
    ("Rastúcich", "growing", formatting.format_number),
    ("Netto GMV", "net_delta", formatting.format_signed_eur),
]

# Hlavičky stĺpcov porovnávacej tabuľky. Kratšie než názvy sérií v legende —
# tooltip musí zostať úzky, identitu sérií nesie farebný štvorček nad tabuľkou.
ORDER_COUNT_HOVER_HEADERS = ("celý", "filtrovaný")


def _order_count_comparison_hover(breakdown, filtered):
    """Zarovnaná porovnávacia tabuľka do hoveru: jeden riadok na metriku.

    Šírky stĺpcov sa počítajú cez všetky koše naraz, nie pre každý zvlášť —
    tabuľka tak pri prechode myšou po grafe neposkakuje. Zarovnanie medzerami
    funguje len v neproporcionálnom písme, preto hover_font="mono".
    """
    label_width = max(len(label) for label, _, _ in ORDER_COUNT_HOVER_ROWS)
    label_width = max(label_width, len(""))
    left_width = _hover_column_width(breakdown, ORDER_COUNT_HOVER_HEADERS[0])
    right_width = _hover_column_width(filtered, ORDER_COUNT_HOVER_HEADERS[1])

    header = ("".ljust(label_width) + "  "
              + ORDER_COUNT_HOVER_HEADERS[0].rjust(left_width) + "  "
              + ORDER_COUNT_HOVER_HEADERS[1].rjust(right_width))

    lines = []
    for bucket in breakdown.index:
        rows = [header]
        for label, column, formatter in ORDER_COUNT_HOVER_ROWS:
            rows.append(label.ljust(label_width) + "  "
                        + formatter(breakdown.loc[bucket, column]).rjust(left_width) + "  "
                        + formatter(filtered.loc[bucket, column]).rjust(right_width))
        lines.append(rows)
    return lines


def _hover_column_width(breakdown, header):
    """Najširšia hodnota stĺpca naprieč všetkými košmi, vrátane hlavičky."""
    width = len(header)
    for _, column, formatter in ORDER_COUNT_HOVER_ROWS:
        for bucket in breakdown.index:
            width = max(width, len(formatter(breakdown.loc[bucket, column])))
    return width


def _order_count_hover(breakdown):
    """Riadky do hoveru pre jednu sériu rezu podľa počtu objednávok."""
    return base.kpi_hover(breakdown, lambda row: [
        f"Účtov: {formatting.format_number(row['customers'])}",
        f"Rastúcich: {formatting.format_number(row['growing'])}",
        f"Netto zmena GMV: {formatting.format_signed_eur(row['net_delta'])}",
    ])


def dropped_activity_split(split):
    """Vyradené účty podľa aktivity za rok, rozdelené na rastúce a klesajúce."""
    return base.figure(
        "dropped_activity",
        "Účty vyradené filtrom podľa aktivity za posledný rok",
        f"Počet účtov. Ľavá skupina je z definície celá klesajúca — bez objednávky "
        f"za {C.FREQUENCY_WINDOW_MONTHS} mesiacov nemá účet GMV ani v okne KPI. "
        f"{base.population_note(int(split['customers'].sum()), 'účtami vyradenými z menovateľa')}",
        "bar",
        split.index,
        [
            base.series("Rastúce", split["growing"], C.KPI_DIAG_COLOR_GOOD),
            base.series("Klesajúce", split["declining"], C.KPI_DIAG_COLOR_BAD),
        ],
        height=260,
        stacked=True,
        value_format="count",
        hover_extras=base.kpi_hover(split, lambda row: [
            f"Účtov spolu: {formatting.format_number(row['customers'])}",
            f"Lifetime GMV: {formatting.format_eur(row['lifetime_gmv'])}",
            f"GMV za rok: {formatting.format_eur(row['gmv_12m'])}",
        ]),
    )


def order_value_mix(mix):
    """Rozdelenie hodnoty prvej objednávky: jednorazoví vs opakujúci zákazníci."""
    return base.figure(
        "order_value_mix",
        "Hodnota prvej objednávky — jednorazoví vs opakujúci zákazníci",
        "V % zákazníkov v danej skupine. Percentá, nie počty — skupiny sú rôzne veľké. "
        "Ak by sa dalo z prvej objednávky poznať, kto sa vráti, tvary by sa líšili.",
        "bar",
        mix.index,
        [
            base.series("Jednorazoví", mix["single_pct"], C.KPI_DIAG_COLOR_BAD),
            base.series("Opakujúci (prvá objednávka)", mix["repeat_pct"], C.KPI_DIAG_COLOR_NEUTRAL),
        ],
        height=300,
        value_format="pct",
    )


def single_order_by_year(by_year, window_months):
    """Počet jednorazových zákazníkov podľa roku ich jedinej objednávky."""
    return base.figure(
        "single_order_year",
        "Jednorazoví zákazníci podľa roku ich jedinej objednávky",
        f"Počet zákazníkov. Posledných {window_months} mesiacov je vynechaných — "
        f"kto nakúpil nedávno, ešte mal čas vrátiť sa a medzi stratených nepatrí. "
        f"Posledný rok je preto nekompletný.",
        "bar",
        [str(year) for year in by_year.index],
        [base.series("Zákazníkov", by_year["customers"], C.COLOR_BLUE)],
        height=300,
        value_format="count",
        hover_extras=base.kpi_hover(by_year, lambda row: [
            f"GMV: {formatting.format_eur(row['gmv'])}",
        ]),
    )


def account_gmv_timeline(monthly, orders, accounts, figure_id, group_note):
    """Mesačné GMV jedného účtu, s prepínačom medzi účtami.

    Všetky série sú v špecifikácii naraz; prehliadač len prepína, ktorá sa
    kreslí. Pri dvoch stovkách účtov je to lacnejšie než dvesto samostatných
    grafov a používateľ nemusí nič načítavať.

    figure_id a group_note sú tu preto, že ten istý graf sa kreslí pre viac
    skupín účtov; dva grafy s rovnakým ID by sa pobili o ten istý <canvas>.
    """
    options = []
    series = {}
    hover = {}
    for cust in monthly.columns:
        series[cust] = [base.clean(value) for value in monthly[cust]]
        hover[cust] = _account_hover(orders[cust])
        options.append({"value": cust, "label": _account_option_label(accounts, cust)})

    first = monthly.columns[0]
    return base.figure(
        figure_id,
        "GMV účtu v čase",
        f"V €, po mesiacoch od {C.DISPLAY_START_YEAR}. Mesiac bez objednávky je nula, "
        f"nie chýbajúca hodnota. Účet vyber v zozname nad grafom — {group_note}, "
        f"zoradené podľa GMV v minuloročnom okne. V hover je aj počet objednávok.",
        "bar",
        [str(month) for month in monthly.index],
        [base.series("GMV", monthly[first], C.COLOR_BLUE)],
        height=320,
        value_format="eur",
        selector={"label": "Účet:", "options": options,
                  "series": series, "hover": hover},
    )


def _account_hover(monthly_orders):
    """Riadky do hoveru pre jeden účet: počet objednávok v danom mesiaci."""
    lines = []
    for count in monthly_orders:
        lines.append([f"Objednávok: {formatting.format_number(count)}"])
    return lines


def _account_option_label(accounts, cust):
    """Popisok účtu v prepínači: názov firmy a jeho minuloročné GMV."""
    row = accounts.loc[cust]
    return f"{row['name']} — {formatting.format_eur(row['previous'])}"


def last_order_cluster(cluster, figure_id, group_note):
    """Kedy účty danej skupiny naposledy nakúpili."""
    return base.figure(
        figure_id,
        "Mesiac poslednej objednávky",
        f"Počet účtov — {group_note}. Zhluk v jednom období by znamenal spoločnú "
        f"príčinu, teda udalosť na našej strane, nie stovky nezávislých rozhodnutí. "
        f"V hover je GMV, ktoré tie účty mali v minuloročnom okne.",
        "bar",
        [str(month) for month in cluster.index],
        [base.series("Účtov", cluster["customers"], C.COLOR_RED)],
        height=300,
        value_format="count",
        hover_extras=base.kpi_hover(cluster, lambda row: [
            f"GMV pred rokom: {formatting.format_eur(row['previous_gmv'])}",
        ]),
    )

def churn_tenure_chart(tenure_df, figure_id, group_note, count):
    """Ako dlho účty nakupovali, kým stíchli."""
    return base.figure(
        figure_id,
        "Dĺžka života pred odchodom",
        f"Počet účtov — {group_note}. Čas od prvej po poslednú objednávku. Ukazuje, "
        f"či odchádzajú skôr čerství zákazníci, teda problém akvizície a onboardingu, "
        f"alebo zabehnutí odberatelia. Koše, do ktorých táto skupina padnúť nemôže, "
        f"v grafe nie sú. {base.population_note(count, 'účtami')}",
        "bar",
        tenure_df.index,
        [base.series("Účtov", tenure_df["customers"], C.COLOR_BLUE)],
        value_format="count",
    )


def churn_orders_chart(orders_df, figure_id, group_note, count):
    """Koľko objednávok účty stihli, kým stíchli."""
    return base.figure(
        figure_id,
        "Počet objednávok za život",
        f"Počet účtov — {group_note}. Koľko objednávok stihli urobiť, kým prestali "
        f"nakupovať. Ticho nad {C.KPI_DIAG_CHURN_DAYS} dní neznamená definitívny "
        f"odchod, časť účtov sa môže vrátiť. Koše, do ktorých táto skupina padnúť "
        f"nemôže, v grafe nie sú. {base.population_note(count, 'účtami')}",
        "bar",
        orders_df.index,
        [base.series("Účtov", orders_df["customers"], C.COLOR_ORANGE)],
        value_format="count",
    )


def churn_country_chart(country_df, figure_id, group_note, count):
    """Z ktorých trhov churnuté účty pochádzajú."""
    shown = int(country_df["customers"].sum())
    return base.figure(
        figure_id,
        f"Zloženie podľa krajiny (top {len(country_df)})",
        f"Počet účtov — {group_note}, podľa fakturačnej krajiny. V grafe je "
        f"{formatting.format_number(shown)} z {formatting.format_number(count)} účtov "
        f"skupiny, zvyšok pripadá na menšie trhy. V hover je podiel na posudzovaných "
        f"účtoch danej krajiny — pri malých trhoch stoja tie percentá na pár účtoch, "
        f"preto je vedľa nich aj absolútny počet.",
        "bar",
        country_df.index,
        [base.series("Účtov", country_df["customers"], C.COLOR_TEAL)],
        value_format="count",
        hover_extras=base.kpi_hover(country_df, lambda row: [
            f"Podiel z posudzovaných účtov v krajine: "
            f"{formatting.format_pct(row['churn_pct'])}",
            f"{formatting.format_number(row['customers'])} z "
            f"{formatting.format_number(row['assessed'])} posudzovaných účtov",
        ]),
    )
