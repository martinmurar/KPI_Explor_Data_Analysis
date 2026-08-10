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
            point_colors=None, value_format=None):
    """Jedna séria grafu.

    value_format prepíše formát čísiel grafu — použije sa, keď má séria inú
    jednotku ako zvyšok grafu (napríklad percentá vedľa absolútnych počtov).
    """
    return {
        "label": label,
        "data": [None if value is None else _clean(value) for value in values],
        "color": color,
        "type": chart_type,
        "dashed": dashed,
        "point_colors": point_colors,
        "value_format": value_format,
    }


def _clean(value):
    """Nahradí NaN hodnotou None, aby prežila serializáciu do JSON.

    Dvojica [od, do] sa čistí po prvkoch — Chart.js z nej kreslí plávajúci
    stĺpec, čo potrebuje waterfall v diagnostickom reporte. V hlavnom reporte
    žiadna séria dvojice neobsahuje, takže tá vetva sa tam nikdy nepoužije.
    """
    if isinstance(value, (list, tuple)):
        return [_clean(item) for item in value]
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
    }
    return figure


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
def monthly_trend(monthly):
    """Mesačné GMV so 12-mesačným klzavým priemerom."""
    millions = monthly["gmv"] / 1e6
    average = monthly["moving_average"] / 1e6
    return _figure(
        "monthly_trend",
        "Mesačné GMV a 12-mesačný klzavý priemer",
        f"V mil. €. Klzavý priemer vyhladzuje sezonalitu — stúpa bez prerušenia, "
        f"ale mesačné stĺpce kolíšu čoraz viac.",
        "bar",
        [str(period) for period in monthly.index],
        [
            _series("12-mes. klzavý priemer", average, C.COLOR_ORANGE, chart_type="line"),
            _series("GMV", millions, C.COLOR_BLUE_LIGHT),
        ],
        height=360,
        value_format="mil_eur",
    )


def seasonality(shares):
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
        "Sezonalita",
        f"Priemerný podiel mesiaca na ročnom GMV, {first_year}–{last_year} "
        f"(len kompletné roky).",
        "bar",
        month_names,
        [_series("Podiel na ročnom GMV", shares.values, C.COLOR_BLUE, point_colors=colors)],
        value_format="pct",
    )


def yearly_bridge(bridge):
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
        "porovnávať čiastočný rok s celým by nemalo zmysel.",
        "bar",
        bridge["label"],
        datasets,
        height=360,
        stacked=True,
        value_format="mil_eur",
        y_begin_at_zero=False,
    )


def order_value(summary):
    """Priemerná vs mediánová hodnota objednávky."""
    return _figure(
        "order_value",
        "Priemerná vs mediánová hodnota objednávky",
        "V €. Priemer rastie, medián je plochý — celý rast sedí v pravom chvoste "
        "distribúcie. p95 je uvedený ako kontext.",
        "line",
        summary["label"],
        [
            _series("p95", summary["p95_order"], C.COLOR_GREY, chart_type="line", dashed=True),
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
        "počtu účtov.",
        "line",
        concentration["label"],
        datasets,
        value_format="pct",
        y_max=100,
    )


def concentration_threshold(concentration):
    """Počet zákazníkov potrebných na 80 % GMV."""
    return _figure(
        "concentration_threshold",
        "Počet zákazníkov potrebných na 80 % GMV",
        "Čím menšie číslo, tým koncentrovanejšie portfólio.",
        "bar",
        concentration["label"],
        [_series("Zákazníci", concentration["customers_for_80pct"], C.COLOR_VIOLET)],
        value_format="count",
    )


def portfolio_structure(structure):
    """Podiel zákazníkov vs podiel GMV podľa veľkostného pásma."""
    return _figure(
        "portfolio_structure",
        f"Veľkostná štruktúra portfólia ({data.year_label(C.PARTIAL_YEAR)})",
        "V %. Rozdiel medzi sivými a modrými stĺpcami je mierou nerovnosti portfólia.",
        "bar",
        structure.index,
        [
            _series("% zákazníkov", structure["customer_pct"], C.COLOR_GREY),
            _series("% GMV", structure["gmv_pct"], C.COLOR_BLUE),
        ],
        value_format="pct",
    )


def market_gmv(by_market):
    """GMV podľa vykazovaného trhu a roku."""
    datasets = []
    for index, market in enumerate(by_market.index):
        color = C.COUNTRY_PALETTE[index % len(C.COUNTRY_PALETTE)]
        datasets.append(_series(market, by_market.loc[market].values / 1e6, color))

    reported = ", ".join(C.REPORTED_COUNTRIES)
    return _figure(
        "market_gmv",
        "GMV podľa trhu",
        f"V mil. €. Samostatne {reported}, všetky ostatné krajiny spolu "
        f"ako „{C.OTHER_MARKET_LABEL}“.",
        "bar",
        by_market.columns,
        datasets,
        height=360,
        stacked=True,
        value_format="mil_eur",
    )


def market_growth(growth):
    """Medziročný rast podľa trhu."""
    values = list(growth["growth_pct"])
    return _figure(
        "market_growth",
        "Medziročný rast GMV podľa trhu",
        f"V %, Jan–Júl {C.PARTIAL_YEAR} vs rovnaké obdobie predchádzajúceho roku.",
        "bar",
        growth.index,
        [_series("Rast", values, C.COLOR_BLUE, point_colors=_diverging_colors(values))],
        index_axis="y",
        value_format="pct",
        y_begin_at_zero=False,
    )


# ── churn ─────────────────────────────────────────────────────────────────────
def growth_and_churn_by_band(growth, churn):
    """Podiel rastúcich zákazníkov a 6-mesačný churn podľa pásma."""
    return _figure(
        "band_growth_churn",
        f"Podiel rastúcich zákazníkov a {C.CHURN_MAIN_THRESHOLD_MONTHS}-mesačný churn podľa pásma",
        f"V %. Rast je meraný za {C.GMV_WINDOW_MONTHS} mesiace medziročne, churn k dátumu "
        f"{C.AS_OF:%-d. %-m. %Y}. Malí zákazníci nerastú a odchádzajú; veľkí rastú a zostávajú.",
        "bar",
        growth.index,
        [
            _series("% rastúcich", growth["growing_pct"], C.COLOR_BLUE),
            _series(f"% churn ({C.CHURN_MAIN_THRESHOLD_MONTHS} mes.)", churn["churn_pct"], C.COLOR_RED),
        ],
        value_format="pct",
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
        "objednať druhýkrát, jej hodnota nie je porovnateľná.",
        "bar",
        single_order["label"],
        [_series("% s jedinou objednávkou", single_order["single_order_pct"],
                 C.COLOR_RED, point_colors=colors)],
        value_format="pct",
    )


def churn_over_time(curves):
    """Churn v čase pri troch prahoch."""
    colors = [C.COLOR_RED, C.COLOR_ORANGE, C.COLOR_BLUE]
    datasets = []
    for threshold, color in zip(C.CHURN_THRESHOLDS_MONTHS, colors):
        datasets.append(_series(
            f"{threshold} mesiacov",
            curves[f"churn_{threshold}m"],
            color,
            chart_type="line",
        ))

    labels = [f"{date:%Y-%m}" for date in curves.index]
    return _figure(
        "churn_over_time",
        "Churn v čase",
        "V %. V každom bode: podiel zákazníkov, od ktorých poslednej objednávky prešlo "
        "viac ako 3 / 6 / 12 mesiacov. Menovateľ = zákazníci akvirovaní aspoň N mesiacov "
        "pred daným bodom. Budúce objednávky sa neberú do úvahy.",
        "line",
        labels,
        datasets,
        height=340,
        value_format="pct",
        y_max=100,
    )


def reactivation_histogram(histogram):
    """Rozdelenie zákazníkov podľa počtu reaktivácií."""
    return _figure(
        "reactivation_histogram",
        "Počet reaktivácií za život zákazníka",
        f"Reaktivácia = objednávka po medzere dlhšej ako {C.REACTIVATION_GAP_MONTHS} mesiacov. "
        f"Len zákazníci s aspoň dvoma objednávkami.",
        "bar",
        histogram.index,
        [_series("Zákazníci", histogram["customers"], C.COLOR_TEAL)],
        value_format="count",
    )


def repeat_reactivation(by_year):
    """Počet reaktivácií za rok a podiel opakovaných."""
    return _figure(
        "repeat_reactivation",
        "Reaktivácie po rokoch a podiel opakovaných",
        "Stĺpce = počet reaktivácií, línia = aký podiel z nich pripadá na zákazníkov, "
        "ktorí už raz reaktivovaní boli. Ak by sa točili stále tí istí, línia by rástla k 100 %.",
        "bar",
        by_year["label"],
        [
            _series("Reaktivácie", by_year["events"], C.COLOR_TEAL),
            _series("% opakovaných", by_year["repeat_pct"], C.COLOR_ORANGE,
                    chart_type="line", value_format="pct"),
        ],
        value_format="count",
    )


def frequency_histogram(histogram, highest_frequency):
    """Histogram frekvencie objednávania: počet zákazníkov podľa počtu objednávok."""
    caption = (
        f"Na osi x počet objednávok za posledných {C.FREQUENCY_WINDOW_MONTHS} mesiacov, "
        f"na osi y počet zákazníkov. Menovateľom sú zákazníci s aspoň jednou objednávkou "
        f"v okne — dormantní v grafe nie sú. Posledný kôš zlučuje "
        f"{C.FREQUENCY_TOP_BUCKET} a viac objednávok (maximum je {highest_frequency}). "
        f"V hover je aj reverzný kumulatív, teda počet zákazníkov s danou frekvenciou "
        f"a vyššou."
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
        lines.append([f"Frekvencia {threshold} a vyššia: {customers} zákazníkov ({share} bázy)"])
    return lines


# ── account growth ────────────────────────────────────────────────────────────
def account_growth_over_time(history):
    """Podiel rastúcich účtov v čase, s GMV-váženým variantom a cieľovou čiarou."""
    target = [C.ACCOUNT_GROWTH_TARGET_PCT] * len(history)
    labels = [f"{date:%Y-%m}" for date in history.index]

    return _figure(
        "account_growth_over_time",
        "Account growth v čase",
        f"V %, klzavé {C.GMV_WINDOW_MONTHS} mesiace medziročne, body sú konce kvartálov. "
        f"Zvyšok stĺpca do 100 % menovateľa sú klesajúce účty. Čierna línia je GMV-vážený variant: "
        f"podiel tržieb, ktoré ležia v rastúcich účtoch. Prerušovaná čiara je cieľ "
        f"{C.ACCOUNT_GROWTH_TARGET_PCT} %.",
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
    """Riadky do hover: veľkosť menovateľa v danom bode."""
    lines = []
    for _, row in history.iterrows():
        accounts = formatting.format_number(row["accounts"])
        lines.append([f"Menovateľ: {accounts} účtov"])
    return lines


def account_growth_composition(composition):
    """Rozklad menovateľa na reaktivované, odídené a aktívne v oboch oknách."""
    return _figure(
        "account_growth_composition",
        "Z čoho sa skladá menovateľ KPI",
        "Počet účtov. Prvé dve skupiny nie sú rozhodnuté rastom, ale tým, či účet "
        "v okne vôbec nakúpil — reaktivované sú rastúce automaticky, odídené "
        "klesajúce automaticky. Len tretia skupina meria skutočnú zmenu objemu.",
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


def account_growth_breakdown(breakdown, figure_id, title, caption, overall_pct):
    """Podiel rastúcich účtov v jednom reze, farebne voči cieľu a priemeru."""
    values = list(breakdown["growing_pct"])
    return _figure(
        figure_id,
        title,
        caption,
        "bar",
        breakdown.index,
        [_series("% rastúcich účtov", values, C.ACCOUNT_GROWTH_COLOR_GROWING,
                 point_colors=_target_colors(values, overall_pct))],
        height=max(200, 34 * len(breakdown) + 60),
        index_axis="y",
        value_format="pct",
        y_max=100,
        hover_extras=_breakdown_hover(breakdown),
    )


def _target_colors(values, overall_pct):
    """Zelená nad cieľom, červená pod celkovým KPI, inak modrá."""
    colors = []
    for value in values:
        if value >= C.ACCOUNT_GROWTH_TARGET_PCT:
            colors.append(C.ACCOUNT_GROWTH_COLOR_ABOVE_TARGET)
        elif value < overall_pct:
            colors.append(C.ACCOUNT_GROWTH_COLOR_DECLINING)
        else:
            colors.append(C.ACCOUNT_GROWTH_COLOR_GROWING)
    return colors


def _breakdown_hover(breakdown):
    """Riadky do hover: počet účtov, GMV-vážený podiel a netto zmena GMV."""
    lines = []
    for _, row in breakdown.iterrows():
        accounts = formatting.format_number(row["customers"])
        gmv_share = formatting.format_pct(row["gmv_growing_pct"])
        net = formatting.format_signed_eur(row["net_delta"])
        lines.append([
            f"Účtov: {accounts}",
            f"GMV v rastúcich účtoch: {gmv_share}",
            f"Netto zmena GMV: {net}",
        ])
    return lines


def net_gmv_by_band(growth):
    """Netto medziročná zmena GMV podľa pásma."""
    values = list(growth["net_delta"] / 1000)
    return _figure(
        "net_gmv_by_band",
        "Netto medziročná zmena GMV podľa pásma",
        f"V tis. €, {C.GMV_WINDOW_MONTHS} mesiace medziročne. Pásmo je určené podľa GMV "
        f"v porovnávacom období.",
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
        f"V %, len {int(frequency['customers'].sum())} účtov aktívnych v oboch oknách. "
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


def kpi_dropped_recency(recency):
    """Padnuté účty podľa toho, kedy naposledy nakúpili."""
    colors = []
    for is_alive in recency["is_alive"]:
        if is_alive:
            colors.append(C.KPI_DIAG_COLOR_NEUTRAL)
        else:
            colors.append(C.KPI_DIAG_COLOR_BAD)

    return _figure(
        "kpi_dropped_recency",
        "Účty s nulovým GMV v aktuálnom okne",
        "Počet účtov. Modré účty nakúpili po skončení minuloročného okna — nie sú "
        "churnuté, len neobjednali práve v porovnávanom okne. KPI ich aj tak "
        "počíta ako klesajúce.",
        "bar",
        recency.index,
        [_series("Počet účtov", recency["customers"], C.KPI_DIAG_COLOR_NEUTRAL,
                 point_colors=colors)],
        height=210,
        index_axis="y",
        value_format="count",
        hover_extras=_kpi_hover(recency, lambda row: [
            f"GMV pred rokom: {formatting.format_eur(row['previous_gmv'])}",
        ]),
    )


def kpi_alive_effect(effect):
    """KPI ako sa vykazuje vs KPI bez živých účtov mimo okna."""
    excluded = int(effect["excluded"].iloc[0])
    return _figure(
        "kpi_alive_effect",
        "Koľko KPI stoja živé účty mimo okna",
        f"V %. Druhý stĺpec vynecháva {excluded} účtov, ktoré nakúpili po skončení "
        f"minuloročného okna, ale nie v tom aktuálnom.",
        "bar",
        effect.index,
        [_series("% rastúcich účtov", effect["growing_pct"], C.KPI_DIAG_COLOR_NEUTRAL)],
        height=160,
        index_axis="y",
        value_format="pct",
        y_max=100,
        hover_extras=_kpi_hover(effect, lambda row: [
            f"Menovateľ: {formatting.format_number(row['customers'])} účtov",
        ]),
    )


def kpi_monthly_noise(noise):
    """KPI merané s oknom posunutým po mesiacoch."""
    target = [C.ACCOUNT_GROWTH_TARGET_PCT] * len(noise)
    labels = [f"{date:%Y-%m}" for date in noise.index]

    return _figure(
        "kpi_noise",
        "To isté KPI merané o mesiac inak",
        f"V %. Rovnaká definícia, len okno posunuté po mesiacoch. Rozptyl týchto "
        f"meraní je dolná hranica šumu metriky — biznis sa medzi dvoma susednými "
        f"mesiacmi nemení tak, ako sa mení toto číslo.",
        "line",
        labels,
        [
            _series(f"Cieľ {C.ACCOUNT_GROWTH_TARGET_PCT} %", target,
                    C.KPI_DIAG_COLOR_TARGET, chart_type="line", dashed=True),
            _series("% rastúcich účtov", noise["growing_pct"],
                    C.KPI_DIAG_COLOR_NEUTRAL, chart_type="line"),
        ],
        height=280,
        value_format="pct",
        y_max=70,
        hover_extras=_kpi_hover(noise, lambda row: [
            f"Menovateľ: {formatting.format_number(row['accounts'])} účtov",
        ]),
    )


def kpi_window_vs_population(variants, reference_pct):
    """Rozklad efektu dlhšieho okna na efekt merania a efekt populácie."""
    values = list(variants["growing_pct"])
    return _figure(
        "kpi_window_population",
        "Dĺžka okna: voľba merania alebo voľba populácie?",
        f"V %. Dlhé okno je {C.KPI_DIAG_LONG_WINDOW_MONTHS}-mesačné, krátke "
        f"{C.GMV_WINDOW_MONTHS}-mesačné. Ak dlhé okno pustím na tých istých účtoch, "
        f"zmení sa takmer nič — prepad robia účty, ktoré krátke okno do menovateľa "
        f"vôbec nevpustí.",
        "bar",
        variants.index,
        [_series("% rastúcich účtov", values, C.KPI_DIAG_COLOR_NEUTRAL,
                 point_colors=_kpi_status_colors(values, reference_pct))],
        height=230,
        index_axis="y",
        value_format="pct",
        y_max=100,
        hover_extras=_kpi_hover(variants, lambda row: [
            f"Menovateľ: {formatting.format_number(row['customers'])} účtov",
        ]),
    )


def kpi_change_histogram(histogram):
    """Distribúcia medziročnej zmeny GMV u účtov aktívnych v oboch oknách."""
    colors = []
    for is_positive in histogram["is_positive"]:
        if is_positive:
            colors.append(C.KPI_DIAG_COLOR_NEUTRAL)
        else:
            colors.append(C.KPI_DIAG_COLOR_BAD)

    median = histogram["median_change_pct"].iloc[0]
    return _figure(
        "kpi_change_histogram",
        "Distribúcia medziročnej zmeny GMV",
        f"Počet účtov aktívnych v oboch oknách podľa medziročnej zmeny GMV v %. "
        f"Krajné hodnoty sú orezané na hranice krajných košov. Medián "
        f"{formatting.format_signed_pct(median)}.",
        "bar",
        histogram.index,
        [_series("Počet účtov", histogram["customers"], C.KPI_DIAG_COLOR_NEUTRAL,
                 point_colors=colors)],
        height=280,
        value_format="count",
    )


def kpi_retention_wall(wall, reference_pct):
    """KPI dnes, pri nulovom churne a cieľ."""
    values = list(wall["growing_pct"])
    return _figure(
        "kpi_retention_wall",
        "Aritmetická stena retencie",
        f"V %. Scenár nulový churn znamená, že ani jeden účet nespadol do nuly a "
        f"všetky sa chovajú ako priemerný účet aktívny v oboch oknách. Je to horná "
        f"hranica toho, čo dokáže čistá retencia.",
        "bar",
        wall.index,
        [_series("% rastúcich účtov", values, C.KPI_DIAG_COLOR_NEUTRAL,
                 point_colors=_kpi_status_colors(values, reference_pct))],
        height=190,
        index_axis="y",
        value_format="pct",
        y_max=100,
    )


def kpi_lever_ladder(ladder):
    """Kumulatívny efekt pák ako waterfall."""
    target = [C.ACCOUNT_GROWTH_TARGET_PCT] * len(ladder)
    spans = _ladder_spans(ladder)
    colors = _ladder_colors(ladder)

    return _figure(
        "kpi_lever_ladder",
        "Rebrík pák k cieľu",
        f"V %. Každý stĺpec je prírastok KPI oproti predchádzajúcemu kroku. Nie je "
        f"to prognóza — je to kontrafaktuálna aritmetika, ktorá ukazuje pomer sily "
        f"pák. Posledný krok je zámerne tenký.",
        "bar",
        ladder.index,
        [
            _series(f"Cieľ {C.ACCOUNT_GROWTH_TARGET_PCT} %", target,
                    C.KPI_DIAG_COLOR_TARGET, chart_type="line", dashed=True),
            _series("KPI po kroku", spans, C.KPI_DIAG_COLOR_NEUTRAL, point_colors=colors),
        ],
        height=280,
        value_format="pct",
        y_max=70,
        hover_extras=_kpi_hover(ladder, lambda row: [
            f"Prírastok: {formatting.format_signed_pct(row['gain'], 0)} rastúcich účtov"
            if row["gain"] else "Východzí stav",
        ]),
    )


def _ladder_spans(ladder):
    """Dvojice [od, do] pre plávajúce stĺpce waterfallu."""
    values = list(ladder["growing_pct"])
    spans = []
    for index, value in enumerate(values):
        if index == 0:
            spans.append([0, value])
        else:
            spans.append([values[index - 1], value])
    return spans


def _ladder_colors(ladder):
    """Prvý krok je stav, posledný nad cieľom je zelený, ostatné modré."""
    colors = []
    for index, value in enumerate(ladder["growing_pct"]):
        if index == 0:
            colors.append(C.KPI_DIAG_COLOR_MUTED)
        elif value >= C.ACCOUNT_GROWTH_TARGET_PCT:
            colors.append(C.KPI_DIAG_COLOR_GOOD)
        else:
            colors.append(C.KPI_DIAG_COLOR_NEUTRAL)
    return colors
