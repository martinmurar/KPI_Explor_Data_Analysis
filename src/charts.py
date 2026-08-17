# -*- coding: utf-8 -*-
"""Zostavenie špecifikácií grafov.

Každá funkcia vytvorí jeden graf ako slovník, ktorý je serializovateľný do JSON.
Prekladom do Chart.js sa zaoberá JavaScript v report.py — Python tu nerieši
formátovanie osí ani tooltipov, len dáta a farby.

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

from src import constants as C
import data
import formatting


def _series(label, values, color, chart_type="bar", dashed=False,
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
        "data": [None if value is None else _clean(value) for value in values],
        "color": color,
        "type": chart_type,
        "dashed": dashed,
        "point_colors": point_colors,
        "value_format": value_format,
        "overlay": overlay,
        "hover_extras": hover_extras,
    }


def _clean(value):
    """Nahradí NaN hodnotou None, aby prežila serializáciu do JSON."""
    try:
        if value != value:
            return None
    except TypeError:
        return value
    return round(float(value), 4)


def _figure(figure_id, title, caption, chart_type, labels, datasets, **options):
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


def _population_note(count, unit):
    """Veta na konec popisu: s akou populáciou graf pracuje.

    Každý graf v reporte stojí na inej skupine (všetci zákazníci / posudzované
    účty / účty aktívne v oboch oknách) a bez tejto vety to čitateľ z grafu
    nevyčíta — rozdielne počty potom vyzerajú ako chyba.
    """
    return f"Graf pracuje s {formatting.format_number(count)} {unit}."


def _diverging_colors(values):
    """Modrá pre kladné hodnoty, červená pre záporné."""
    colors = []
    for value in values:
        if value is None or value < 0:
            colors.append(C.COLOR_RED)
        else:
            colors.append(C.COLOR_BLUE)
    return colors


# ── analýza ───────────────────────────────────────────────────────────────────
def monthly_trend(monthly, customers):
    """Mesačné GMV so 12-mesačným klzavým priemerom."""
    millions = monthly["gmv"] / 1e6
    average = monthly["moving_average"] / 1e6
    return _figure(
        "monthly_trend",
        "Mesačné GMV a 12-mesačný klzavý priemer",
        f"V mil. €. Klzavý priemer vyhladzuje sezónnosť — stúpa bez prerušenia, "
        f"ale mesačné stĺpce kolíšu čoraz viac. "
        f"{_population_note(customers, 'zákazníkmi')}",
        "bar",
        [str(period) for period in monthly.index],
        [
            _series("12-mes. klzavý priemer", average, C.COLOR_ORANGE, chart_type="line"),
            _series("GMV", millions, C.COLOR_BLUE_LIGHT),
        ],
        height=360,
        value_format="mil_eur",
    )


def seasonality(shares, customers):
    """Priemerný podiel mesiaca na ročnom GMV."""
    month_names = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII"]
    colors = []
    for share in shares.values:
        if share >= 9:
            colors.append(C.COLOR_BLUE)
        else:
            colors.append(C.COLOR_BLUE_LIGHT)

    first_year, last_year = C.SEASONALITY_YEARS
    return _figure(
        "seasonality",
        "Sezónnosť",
        f"Priemerný podiel mesiaca na ročnom GMV, {first_year}–{last_year} "
        f"(len kompletné roky). {_population_note(customers, 'zákazníkmi')}",
        "bar",
        month_names,
        [_series("Podiel na ročnom GMV", shares.values, C.COLOR_BLUE, point_colors=colors)],
        value_format="pct",
    )


def yearly_bridge(bridge, customers):
    """Komponenty medziročnej zmeny GMV po rokoch."""
    datasets = []
    for component in C.BRIDGE_COMPONENTS:
        datasets.append(_series(
            C.BRIDGE_LABELS_SK[component],
            bridge[component] / 1e6,
            C.BRIDGE_COLORS[component],
        ))
    datasets.append(_series("Netto zmena", bridge["delta"] / 1e6, C.COLOR_INK, chart_type="line"))

    return _figure(
        "yearly_bridge",
        "Komponenty medziročnej zmeny GMV",
        "V mil. €, kalendárne roky. Stĺpec 2026* porovnáva Jan–Júl 2026 s Jan–Júl 2025 — "
        "porovnávať čiastočný rok s celým by nemalo zmysel. "
        f"{_population_note(customers, 'zákazníkmi')}",
        "bar",
        bridge["label"],
        datasets,
        height=360,
        stacked=True,
        value_format="mil_eur",
        y_begin_at_zero=False,
    )


def order_value(summary, orders):
    """Priemerná vs mediánová hodnota objednávky."""
    return _figure(
        "order_value",
        "Priemerná vs mediánová hodnota objednávky",
        "V €. Medián je „prostredná“ objednávka — polovica objednávok je menšia, "
        "polovica väčšia. Priemer rastie, medián je plochý, takže celý rast sedí "
        "vo veľkých objednávkach. "
        f"{_population_note(orders, 'objednávkami')}",
        "line",
        summary["label"],
        [
            _series("Priemer", summary["mean_order"], C.COLOR_BLUE, chart_type="line"),
            _series("Medián", summary["median_order"], C.COLOR_ORANGE, chart_type="line"),
        ],
        value_format="eur",
    )


def concentration_shares(concentration):
    """Podiel top N zákazníkov na GMV v čase."""
    colors = [C.COLOR_RED, C.COLOR_BLUE, C.COLOR_TEAL, C.COLOR_VIOLET, C.COLOR_GREY]
    datasets = []
    for level, color in zip(C.TOP_N_LEVELS, colors):
        datasets.append(_series(
            f"Top {level}",
            concentration[f"top{level}_pct"],
            color,
            chart_type="line",
        ))

    return _figure(
        "concentration_shares",
        "Podiel top N zákazníkov na GMV",
        "V %. Rastúca koncentrácia znamená, že celkový rast závisí od stále menšieho "
        "počtu účtov. Každý rok pracuje so svojimi zákazníkmi — "
        f"{formatting.format_number(concentration['customers'].iloc[-1])} "
        f"v {concentration['label'].iloc[-1]}, počty za ostatné roky sú v tabuľke "
        f"nižšie. Rok {data.year_label(C.PARTIAL_YEAR)} je nekompletný "
        f"({C.PARTIAL_YEAR_LAST_MONTH} mesiacov namiesto 12), a keďže za kratšie "
        f"okno majú zákazníci menej času objednávky rozložiť, koncentrácia v ňom "
        f"môže byť umelo navýšená.",
        "line",
        concentration["label"],
        datasets,
        value_format="pct",
        y_max=100,
    )
def single_order_by_cohort(single_order):
    """Podiel zákazníkov s jednou objednávkou podľa kohorty."""
    colors = []
    for is_immature in single_order["is_immature"]:
        if is_immature:
            colors.append(C.COLOR_GREY)
        else:
            colors.append(C.COLOR_RED)

    return _figure(
        "single_order",
        "Podiel zákazníkov s jedinou objednávkou za život",
        "V %, podľa roku prvej objednávky. Kohorta 2026* je sivá — ešte nemala čas "
        "objednať druhýkrát, jej hodnota nie je porovnateľná. "
        f"{_population_note(int(single_order['customers'].sum()), 'zákazníkmi')} "
        "Sú to len zákazníci s prvou objednávkou v zobrazovanom období; kto "
        "nakúpil prvýkrát skôr, do žiadnej z týchto kohort nepatrí.",
        "bar",
        single_order["label"],
        [_series("% s jedinou objednávkou", single_order["single_order_pct"],
                 C.COLOR_RED, point_colors=colors)],
        value_format="pct",
    )
def frequency_histogram(histogram):
    """Histogram frekvencie objednávania: počet zákazníkov podľa počtu objednávok."""
    caption = (
        f"Na osi x počet objednávok za posledných {C.FREQUENCY_WINDOW_MONTHS} mesiacov, "
        f"na osi y počet zákazníkov. Zahrnutí sú zákazníci s aspoň jednou objednávkou "
        f"v okne. "
        f"{_population_note(int(histogram['customers'].sum()), 'zákazníkmi')}"
    )

    return _figure(
        "frequency_histogram",
        "Frekvencia objednávania",
        caption,
        "bar",
        histogram.index,
        [_series("Zákazníci", histogram["customers"], C.COLOR_BLUE)],
        height=360,
        value_format="count",
        hover_extras=_frequency_hover_lines(histogram),
    )


def _frequency_hover_lines(histogram):
    """Riadky do hover: reverzný kumulatív zákazníkov.

    Prah sa berie z order_count, nie z popisku koša — posledný kôš má popisok
    "30+" a text "frekvencia 30+ a vyššia" by bol nezmyselný.
    """
    lines = []
    for _, row in histogram.iterrows():
        threshold = int(row["order_count"])
        customers = formatting.format_number(row["customers_at_or_above"])
        share = formatting.format_pct(row["share_at_or_above_pct"])
        lines.append([f"Frekvencia {threshold} a vyššia: {customers} zákazníkov "
                      f"({share} všetkých účtov)"])
    return lines


# ── account growth ────────────────────────────────────────────────────────────
def account_growth_over_time(history):
    """Podiel rastúcich účtov v čase, s GMV-váženým variantom a cieľovou čiarou."""
    target = [C.ACCOUNT_GROWTH_TARGET_PCT] * len(history)
    labels = [f"{date:%Y-%m}" for date in history.index]

    return _figure(
        "account_growth_over_time",
        "Account growth v čase",
        f"V %, klzavé {C.GMV_WINDOW_MONTHS} mesiace medziročne, body sú "
        f"{C.GMV_WINDOW_MONTHS}-mesačné kroky (konce januára, apríla, júla a októbra). "
        f"Zvyšok stĺpca do 100 % posudzovaných účtov sú klesajúce. Čierna línia je GMV-vážený variant: "
        f"podiel tržieb, ktoré ležia v rastúcich účtoch. Prerušovaná čiara je cieľ "
        f"{C.ACCOUNT_GROWTH_TARGET_PCT} %. Populácia je v každom bode iná — v poslednom bode "
        f"{formatting.format_number(history['accounts'].iloc[-1])} posudzovaných účtov, "
        f"počty za ostatné body sú v hover.",
        "bar",
        labels,
        [
            _series(f"Cieľ {C.ACCOUNT_GROWTH_TARGET_PCT} %", target,
                    C.ACCOUNT_GROWTH_COLOR_TARGET, chart_type="line", dashed=True),
            _series("% GMV v rastúcich účtoch", history["gmv_growing_pct"],
                    C.ACCOUNT_GROWTH_COLOR_GMV, chart_type="line"),
            _series("% rastúcich účtov", history["growing_pct"],
                    C.ACCOUNT_GROWTH_COLOR_GROWING),
        ],
        height=360,
        value_format="pct",
        y_max=100,
        hover_extras=_account_count_hover(history),
    )


def _account_count_hover(history):
    """Riadky do hover: počet posudzovaných účtov v danom bode."""
    lines = []
    for _, row in history.iterrows():
        accounts = formatting.format_number(row["accounts"])
        lines.append([f"Posudzovaných účtov: {accounts}"])
    return lines


def account_growth_composition(composition):
    """Rozklad posudzovaných účtov na tri skupiny podľa aktivity v oknách."""
    return _figure(
        "account_growth_composition",
        "Z čoho sa skladajú posudzované účty",
        "Počet účtov. Prvé dve skupiny nie sú rozhodnuté rastom, ale tým, či účet "
        "v okne vôbec nakúpil — bez GMV pred rokom rastie účet automaticky, odídené "
        "do nuly klesajú automaticky. Len tretia skupina meria skutočnú zmenu objemu. "
        f"{_population_note(int(composition['customers'].sum()), 'posudzovanými účtami')}",
        "bar",
        composition.index,
        [
            _series("Rastúce", composition["growing"], C.ACCOUNT_GROWTH_COLOR_GROWING),
            _series("Klesajúce", composition["declining"], C.ACCOUNT_GROWTH_COLOR_DECLINING),
        ],
        height=240,
        stacked=True,
        index_axis="y",
        value_format="count",
    )
def net_gmv_by_band(growth, window):
    """Netto medziročná zmena GMV podľa pásma."""
    values = list(growth["net_delta"] / 1000)
    return _figure(
        "net_gmv_by_band",
        "Netto medziročná zmena GMV podľa pásma",
        f"V tis. €. Porovnáva sa {C.GMV_WINDOW_MONTHS}-mesačné okno "
        f"{window['current_start']:%-d. %-m. %Y} – {window['current_end']:%-d. %-m. %Y} "
        f"s rovnakým oknom o rok skôr "
        f"({window['previous_start']:%-d. %-m. %Y} – {window['previous_end']:%-d. %-m. %Y}). "
        f"Pásmo je určené podľa GMV v staršom okne. V grafe sú len účty, ktoré "
        f"v staršom okne nakúpili a sú staršie ako "
        f"{C.ACCOUNT_GROWTH_MIN_AGE_MONTHS} mesiacov — rovnaká populácia ako "
        f"v account growth KPI. "
        f"{_population_note(int(growth['customers'].sum()), 'účtami')}",
        "bar",
        growth.index,
        [_series("Netto zmena", values, C.COLOR_BLUE, point_colors=_diverging_colors(values))],
        index_axis="y",
        value_format="k_eur",
        y_begin_at_zero=False,
    )


# ── diagnostika KPI account growth (druhý report) ─────────────────────────────
# Tieto grafy kreslí len main_kpi_diagnostics.py. Hlavný report ich nevolá,
# takže jeho výstup zostáva nezmenený.
def _kpi_status_colors(values, reference_pct):
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


def _kpi_hover(rows, lines_fn):
    """Riadky do hover pre každý riadok tabuľky rezu."""
    lines = []
    for _, row in rows.iterrows():
        lines.append(lines_fn(row))
    return lines


def kpi_frequency_effect(frequency, reference_pct):
    """Podiel rastúcich podľa zmeny počtu objednávok."""
    values = list(frequency["growing_pct"])
    return _figure(
        "kpi_frequency",
        "Rast účtu podľa zmeny počtu objednávok",
        f"V %. {_population_note(int(frequency['customers'].sum()), 'účtami aktívnymi v oboch oknách')} "
        f"Zelená je nad cieľom {C.ACCOUNT_GROWTH_TARGET_PCT} %, červená pod celkovým KPI.",
        "bar",
        frequency.index,
        [_series("% rastúcich účtov", values, C.KPI_DIAG_COLOR_NEUTRAL,
                 point_colors=_kpi_status_colors(values, reference_pct))],
        height=210,
        index_axis="y",
        value_format="pct",
        y_max=100,
        hover_extras=_kpi_hover(frequency, lambda row: [
            f"Účtov: {formatting.format_number(row['customers'])}",
            f"Netto zmena GMV: {formatting.format_signed_eur(row['net_delta'])}",
        ]),
    )


def kpi_by_order_count(breakdown, reference_pct, filtered=None):
    """KPI osobitne pre každý kôš podľa počtu objednávok za rok.

    Ak je zadaný filtered, vykreslí sa ako užšia svetlá séria cez plnú — ten
    istý rez nad datasetom bez spodných extrémov. Prekryv namiesto stĺpcov
    vedľa seba drží obe hodnoty na tej istej pozícii, takže rozdiel medzi nimi
    je vidieť ako presah spodnej série, nie ako vzdialenosť dvoch stĺpcov.
    """
    values = list(breakdown["growing_pct"])
    series = [_series("Celý dataset", values, C.KPI_DIAG_COLOR_NEUTRAL,
                      point_colors=_kpi_status_colors(values, reference_pct))]
    if filtered is None:
        hover = _order_count_hover(breakdown)
    else:
        series.append(_series("Bez spodných extrémov", list(filtered["growing_pct"]),
                              C.COLOR_BLUE_LIGHT, overlay=True))
        hover = _order_count_comparison_hover(breakdown, filtered)

    return _figure(
        "kpi_by_order_count",
        f"Account growth podľa počtu objednávok za {C.FREQUENCY_WINDOW_MONTHS} mesiacov",
        f"V %. Kôš určuje počet objednávok za posledných {C.FREQUENCY_WINDOW_MONTHS} "
        f"mesiacov. {_population_note(int(breakdown['customers'].sum()), 'posudzovanými účtami')} "
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
    return _kpi_hover(breakdown, lambda row: [
        f"Účtov: {formatting.format_number(row['customers'])}",
        f"Rastúcich: {formatting.format_number(row['growing'])}",
        f"Netto zmena GMV: {formatting.format_signed_eur(row['net_delta'])}",
    ])


_ACTIVITY_COLORS = [
    C.KPI_DIAG_COLOR_GOOD,
    C.KPI_DIAG_COLOR_NEUTRAL,
    C.KPI_DIAG_COLOR_BAD,
]


def kpi_activity_split(activity):
    """Všetky posudzované účty podľa toho, kedy naposledy nakúpili."""
    colors = []
    for status in activity["status"]:
        colors.append(_ACTIVITY_COLORS[int(status)])

    return _figure(
        "kpi_activity_split",
        "Kedy naposledy nakúpili posudzované účty",
        f"Počet účtov. Posudzujú sa účty staršie ako "
        f"{C.ACCOUNT_GROWTH_MIN_AGE_MONTHS} mesiacov s nenulovým GMV aspoň v jednom "
        f"z dvoch okien. Za churned sa považuje účet, ktorý "
        f"nenakúpil {C.KPI_DIAG_CHURN_DAYS} dní. Modrá skupina "
        f"nie je churned - len neobjednala práve v {C.GMV_WINDOW_MONTHS}-mesačnom "
        f"okne, a KPI ju tak počíta ako klesajúcu. "
        f"{_population_note(int(activity['customers'].sum()), 'posudzovanými účtami')}",
        "bar",
        activity.index,
        [_series("Počet účtov", activity["customers"], C.KPI_DIAG_COLOR_NEUTRAL,
                 point_colors=colors)],
        height=230,
        index_axis="y",
        value_format="count",
        hover_extras=_kpi_hover(activity, lambda row: [
            f"Podiel posudzovaných účtov: {formatting.format_pct(row['share_pct'])}",
            f"GMV pred rokom: {formatting.format_eur(row['previous_gmv'])}",
        ]),
    )


def kpi_regular_ordering(scenario):
    """KPI dnes vs KPI, keby živé účty objednávali aspoň raz za okno."""
    converted = int(scenario["converted"].iloc[0])
    colors = [C.KPI_DIAG_COLOR_NEUTRAL, C.KPI_DIAG_COLOR_GOOD]
    return _figure(
        "kpi_regular_ordering",
        f"KPI, keby živé účty objednávali aspoň raz za {C.GMV_WINDOW_MONTHS} mesiace",
        f"V %. Posudzuje sa v oboch stĺpcoch tá istá skupina účtov. Druhý stĺpec počíta "
        f"{converted} živých účtov, ktoré v aktuálnom okne nenakúpili, ako rastúce. "
        f"Je to horná hranica scenára, nie prognóza. "
        f"{_population_note(int(scenario['customers'].iloc[0]), 'posudzovanými účtami')}",
        "bar",
        scenario.index,
        [_series("% rastúcich účtov", scenario["growing_pct"], C.KPI_DIAG_COLOR_NEUTRAL,
                 point_colors=colors)],
        height=170,
        index_axis="y",
        value_format="pct",
        y_max=100,
        hover_extras=_kpi_hover(scenario, lambda row: [
            f"Posudzovaných účtov: {formatting.format_number(row['customers'])}",
        ]),
    )


def kpi_churn_sensitivity(sensitivity):
    """KPI pri zabránení churnu, pre tri predpoklady o raste zachránených účtov."""
    prevented = int(sensitivity["prevented"].iloc[0])
    values = list(sensitivity["growing_pct"])
    target = [C.ACCOUNT_GROWTH_TARGET_PCT] * len(sensitivity)

    return _figure(
        "kpi_churn_sensitivity",
        "KPI pri zabránení churnu — citlivosť na predpoklad o raste",
        f"V %. Všetkých {prevented} churnutých účtov sa berie ako aktívnych v okne, "
        f"mení sa len predpoklad, aký podiel z nich rastie. Posudzovaná skupina je vo "
        f"všetkých stĺpcoch tá istá — {formatting.format_number(sensitivity['customers'].iloc[0])} "
        f"posudzovaných účtov. Prerušovaná čiara je cieľ "
        f"{C.ACCOUNT_GROWTH_TARGET_PCT} %.",
        "bar",
        sensitivity.index,
        [
            _series(f"Cieľ {C.ACCOUNT_GROWTH_TARGET_PCT} %", target,
                    C.KPI_DIAG_COLOR_TARGET, chart_type="line", dashed=True),
            _series("% rastúcich účtov", values, C.KPI_DIAG_COLOR_NEUTRAL,
                    point_colors=_kpi_status_colors(values, values[0] + 0.01)),
        ],
        height=280,
        value_format="pct",
        y_max=70,
        hover_extras=_kpi_hover(sensitivity, lambda row: [
            f"Posudzovaných účtov: {formatting.format_number(row['customers'])}",
            f"Zachránených účtov: {formatting.format_number(row['prevented'])}",
        ]),
    )


def dropped_activity_split(split):
    """Vyradené účty podľa aktivity za rok, rozdelené na rastúce a klesajúce."""
    return _figure(
        "dropped_activity",
        "Účty vyradené filtrom podľa aktivity za posledný rok",
        f"Počet účtov. Ľavá skupina je z definície celá klesajúca — bez objednávky "
        f"za {C.FREQUENCY_WINDOW_MONTHS} mesiacov nemá účet GMV ani v okne KPI. "
        f"{_population_note(int(split['customers'].sum()), 'účtami vyradenými z menovateľa')}",
        "bar",
        split.index,
        [
            _series("Rastúce", split["growing"], C.KPI_DIAG_COLOR_GOOD),
            _series("Klesajúce", split["declining"], C.KPI_DIAG_COLOR_BAD),
        ],
        height=260,
        stacked=True,
        value_format="count",
        hover_extras=_kpi_hover(split, lambda row: [
            f"Účtov spolu: {formatting.format_number(row['customers'])}",
            f"Lifetime GMV: {formatting.format_eur(row['lifetime_gmv'])}",
            f"GMV za rok: {formatting.format_eur(row['gmv_12m'])}",
        ]),
    )


def order_value_mix(mix):
    """Rozdelenie hodnoty prvej objednávky: jednorazoví vs opakujúci zákazníci."""
    return _figure(
        "order_value_mix",
        "Hodnota prvej objednávky — jednorazoví vs opakujúci zákazníci",
        "V % zákazníkov v danej skupine. Percentá, nie počty — skupiny sú rôzne veľké. "
        "Ak by sa dalo z prvej objednávky poznať, kto sa vráti, tvary by sa líšili.",
        "bar",
        mix.index,
        [
            _series("Jednorazoví", mix["single_pct"], C.KPI_DIAG_COLOR_BAD),
            _series("Opakujúci (prvá objednávka)", mix["repeat_pct"], C.KPI_DIAG_COLOR_NEUTRAL),
        ],
        height=300,
        value_format="pct",
    )


def single_order_by_year(by_year, window_months):
    """Počet jednorazových zákazníkov podľa roku ich jedinej objednávky."""
    return _figure(
        "single_order_year",
        "Jednorazoví zákazníci podľa roku ich jedinej objednávky",
        f"Počet zákazníkov. Posledných {window_months} mesiacov je vynechaných — "
        f"kto nakúpil nedávno, ešte mal čas vrátiť sa a medzi stratených nepatrí. "
        f"Posledný rok je preto nekompletný.",
        "bar",
        [str(year) for year in by_year.index],
        [_series("Zákazníkov", by_year["customers"], C.COLOR_BLUE)],
        height=300,
        value_format="count",
        hover_extras=_kpi_hover(by_year, lambda row: [
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
        series[cust] = [_clean(value) for value in monthly[cust]]
        hover[cust] = _account_hover(orders[cust])
        options.append({"value": cust, "label": _account_option_label(accounts, cust)})

    first = monthly.columns[0]
    return _figure(
        figure_id,
        "GMV účtu v čase",
        f"V €, po mesiacoch od {C.DISPLAY_START_YEAR}. Mesiac bez objednávky je nula, "
        f"nie chýbajúca hodnota. Účet vyber v zozname nad grafom — {group_note}, "
        f"zoradené podľa GMV v minuloročnom okne. V hover je aj počet objednávok.",
        "bar",
        [str(month) for month in monthly.index],
        [_series("GMV", monthly[first], C.COLOR_BLUE)],
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
    return _figure(
        figure_id,
        "Mesiac poslednej objednávky",
        f"Počet účtov — {group_note}. Zhluk v jednom období by znamenal spoločnú "
        f"príčinu, teda udalosť na našej strane, nie stovky nezávislých rozhodnutí. "
        f"V hover je GMV, ktoré tie účty mali v minuloročnom okne.",
        "bar",
        [str(month) for month in cluster.index],
        [_series("Účtov", cluster["customers"], C.COLOR_RED)],
        height=300,
        value_format="count",
        hover_extras=_kpi_hover(cluster, lambda row: [
            f"GMV pred rokom: {formatting.format_eur(row['previous_gmv'])}",
        ]),
    )

def churn_tenure_chart(tenure_df, figure_id, group_note, count):
    """Ako dlho účty nakupovali, kým stíchli."""
    return _figure(
        figure_id,
        "Dĺžka života pred odchodom",
        f"Počet účtov — {group_note}. Čas od prvej po poslednú objednávku. Ukazuje, "
        f"či odchádzajú skôr čerství zákazníci, teda problém akvizície a onboardingu, "
        f"alebo zabehnutí odberatelia. Koše, do ktorých táto skupina padnúť nemôže, "
        f"v grafe nie sú. {_population_note(count, 'účtami')}",
        "bar",
        tenure_df.index,
        [_series("Účtov", tenure_df["customers"], C.COLOR_BLUE)],
        value_format="count",
    )


def churn_orders_chart(orders_df, figure_id, group_note, count):
    """Koľko objednávok účty stihli, kým stíchli."""
    return _figure(
        figure_id,
        "Počet objednávok za život",
        f"Počet účtov — {group_note}. Koľko objednávok stihli urobiť, kým prestali "
        f"nakupovať. Ticho nad {C.KPI_DIAG_CHURN_DAYS} dní neznamená definitívny "
        f"odchod, časť účtov sa môže vrátiť. Koše, do ktorých táto skupina padnúť "
        f"nemôže, v grafe nie sú. {_population_note(count, 'účtami')}",
        "bar",
        orders_df.index,
        [_series("Účtov", orders_df["customers"], C.COLOR_ORANGE)],
        value_format="count",
    )


def churn_country_chart(country_df, figure_id, group_note, count):
    """Z ktorých trhov churnuté účty pochádzajú."""
    shown = int(country_df["customers"].sum())
    return _figure(
        figure_id,
        f"Zloženie podľa krajiny (top {len(country_df)})",
        f"Počet účtov — {group_note}, podľa fakturačnej krajiny. V grafe je "
        f"{formatting.format_number(shown)} z {formatting.format_number(count)} účtov "
        f"skupiny, zvyšok pripadá na menšie trhy. V hover je podiel na posudzovaných "
        f"účtoch danej krajiny — pri malých trhoch stoja tie percentá na pár účtoch, "
        f"preto je vedľa nich aj absolútny počet.",
        "bar",
        country_df.index,
        [_series("Účtov", country_df["customers"], C.COLOR_TEAL)],
        value_format="count",
        hover_extras=_kpi_hover(country_df, lambda row: [
            f"Podiel z posudzovaných účtov v krajine: "
            f"{formatting.format_pct(row['churn_pct'])}",
            f"{formatting.format_number(row['customers'])} z "
            f"{formatting.format_number(row['assessed'])} posudzovaných účtov",
        ]),
    )