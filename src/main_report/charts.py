# -*- coding: utf-8 -*-
"""Špecifikácie grafov hlavného reportu.

Spoločné stavebné kamene sú v src/common/charts_base.py — tu sú len grafy,
ktoré kreslí main.py.
"""

from src.common import charts_base as base
from src.common import constants as C
from src.common import data
from src.common import formatting


# ── analýza ───────────────────────────────────────────────────────────────────
def monthly_trend(monthly, customers):
    """Mesačné GMV so 12-mesačným klzavým priemerom."""
    millions = monthly["gmv"] / 1e6
    average = monthly["moving_average"] / 1e6
    return base.figure(
        "monthly_trend",
        "Mesačné GMV a 12-mesačný klzavý priemer",
        f"V mil. €. Klzavý priemer vyhladzuje sezónnosť — stúpa bez prerušenia, "
        f"ale mesačné stĺpce kolíšu čoraz viac. "
        f"{base.population_note(customers, 'zákazníkmi')}",
        "bar",
        [str(period) for period in monthly.index],
        [
            base.series("12-mes. klzavý priemer", average, C.COLOR_ORANGE, chart_type="line"),
            base.series("GMV", millions, C.COLOR_BLUE_LIGHT),
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
    return base.figure(
        "seasonality",
        "Sezónnosť",
        f"Priemerný podiel mesiaca na ročnom GMV, {first_year}–{last_year} "
        f"(len kompletné roky). {base.population_note(customers, 'zákazníkmi')}",
        "bar",
        month_names,
        [base.series("Podiel na ročnom GMV", shares.values, C.COLOR_BLUE, point_colors=colors)],
        value_format="pct",
    )


def yearly_bridge(bridge, customers):
    """Komponenty medziročnej zmeny GMV po rokoch."""
    datasets = []
    for component in C.BRIDGE_COMPONENTS:
        datasets.append(base.series(
            C.BRIDGE_LABELS_SK[component],
            bridge[component] / 1e6,
            C.BRIDGE_COLORS[component],
        ))
    datasets.append(base.series("Netto zmena", bridge["delta"] / 1e6, C.COLOR_INK, chart_type="line"))

    return base.figure(
        "yearly_bridge",
        "Komponenty medziročnej zmeny GMV",
        "V mil. €, kalendárne roky. Stĺpec 2026* porovnáva Jan–Júl 2026 s Jan–Júl 2025 — "
        "porovnávať čiastočný rok s celým by nemalo zmysel. "
        f"{base.population_note(customers, 'zákazníkmi')}",
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
    return base.figure(
        "order_value",
        "Priemerná vs mediánová hodnota objednávky",
        "V €. Medián je „prostredná“ objednávka — polovica objednávok je menšia, "
        "polovica väčšia. Priemer rastie, medián je plochý, takže celý rast sedí "
        "vo veľkých objednávkach. "
        f"{base.population_note(orders, 'objednávkami')}",
        "line",
        summary["label"],
        [
            base.series("Priemer", summary["mean_order"], C.COLOR_BLUE, chart_type="line"),
            base.series("Medián", summary["median_order"], C.COLOR_ORANGE, chart_type="line"),
        ],
        value_format="eur",
    )


def concentration_shares(concentration):
    """Podiel top N zákazníkov na GMV v čase."""
    colors = [C.COLOR_RED, C.COLOR_BLUE, C.COLOR_TEAL, C.COLOR_VIOLET, C.COLOR_GREY]
    datasets = []
    for level, color in zip(C.TOP_N_LEVELS, colors):
        datasets.append(base.series(
            f"Top {level}",
            concentration[f"top{level}_pct"],
            color,
            chart_type="line",
        ))

    return base.figure(
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

    return base.figure(
        "single_order",
        "Podiel zákazníkov s jedinou objednávkou za život",
        "V %, podľa roku prvej objednávky. Kohorta 2026* je sivá — ešte nemala čas "
        "objednať druhýkrát, jej hodnota nie je porovnateľná. "
        f"{base.population_note(int(single_order['customers'].sum()), 'zákazníkmi')} "
        "Sú to len zákazníci s prvou objednávkou v zobrazovanom období; kto "
        "nakúpil prvýkrát skôr, do žiadnej z týchto kohort nepatrí.",
        "bar",
        single_order["label"],
        [base.series("% s jedinou objednávkou", single_order["single_order_pct"],
                 C.COLOR_RED, point_colors=colors)],
        value_format="pct",
    )
def frequency_histogram(histogram):
    """Histogram frekvencie objednávania: počet zákazníkov podľa počtu objednávok."""
    caption = (
        f"Na osi x počet objednávok za posledných {C.FREQUENCY_WINDOW_MONTHS} mesiacov, "
        f"na osi y počet zákazníkov. Zahrnutí sú zákazníci s aspoň jednou objednávkou "
        f"v okne. "
        f"{base.population_note(int(histogram['customers'].sum()), 'zákazníkmi')}"
    )

    return base.figure(
        "frequency_histogram",
        "Frekvencia objednávania",
        caption,
        "bar",
        histogram.index,
        [base.series("Zákazníci", histogram["customers"], C.COLOR_BLUE)],
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

    return base.figure(
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
            base.series(f"Cieľ {C.ACCOUNT_GROWTH_TARGET_PCT} %", target,
                    C.ACCOUNT_GROWTH_COLOR_TARGET, chart_type="line", dashed=True),
            base.series("% GMV v rastúcich účtoch", history["gmv_growing_pct"],
                    C.ACCOUNT_GROWTH_COLOR_GMV, chart_type="line"),
            base.series("% rastúcich účtov", history["growing_pct"],
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
    return base.figure(
        "account_growth_composition",
        "Z čoho sa skladajú posudzované účty",
        "Počet účtov. Prvé dve skupiny nie sú rozhodnuté rastom, ale tým, či účet "
        "v okne vôbec nakúpil — bez GMV pred rokom rastie účet automaticky, odídené "
        "do nuly klesajú automaticky. Len tretia skupina meria skutočnú zmenu objemu. "
        f"{base.population_note(int(composition['customers'].sum()), 'posudzovanými účtami')}",
        "bar",
        composition.index,
        [
            base.series("Rastúce", composition["growing"], C.ACCOUNT_GROWTH_COLOR_GROWING),
            base.series("Klesajúce", composition["declining"], C.ACCOUNT_GROWTH_COLOR_DECLINING),
        ],
        height=240,
        stacked=True,
        index_axis="y",
        value_format="count",
    )
def net_gmv_by_band(growth, window):
    """Netto medziročná zmena GMV podľa pásma."""
    values = list(growth["net_delta"] / 1000)
    return base.figure(
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
        f"{base.population_note(int(growth['customers'].sum()), 'účtami')}",
        "bar",
        growth.index,
        [base.series("Netto zmena", values, C.COLOR_BLUE, point_colors=base.diverging_colors(values))],
        index_axis="y",
        value_format="k_eur",
        y_begin_at_zero=False,
    )


def kpi_frequency_effect(frequency, reference_pct):
    """Podiel rastúcich podľa zmeny počtu objednávok."""
    values = list(frequency["growing_pct"])
    return base.figure(
        "kpi_frequency",
        "Rast účtu podľa zmeny počtu objednávok",
        f"V %. {base.population_note(int(frequency['customers'].sum()), 'účtami aktívnymi v oboch oknách')} "
        f"Zelená je nad cieľom {C.ACCOUNT_GROWTH_TARGET_PCT} %, červená pod celkovým KPI.",
        "bar",
        frequency.index,
        [base.series("% rastúcich účtov", values, C.KPI_DIAG_COLOR_NEUTRAL,
                 point_colors=base.kpi_status_colors(values, reference_pct))],
        height=210,
        index_axis="y",
        value_format="pct",
        y_max=100,
        hover_extras=base.kpi_hover(frequency, lambda row: [
            f"Účtov: {formatting.format_number(row['customers'])}",
            f"Netto zmena GMV: {formatting.format_signed_eur(row['net_delta'])}",
        ]),
    )


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

    return base.figure(
        "kpi_activity_split",
        "Kedy naposledy nakúpili posudzované účty",
        f"Počet účtov. Posudzujú sa účty staršie ako "
        f"{C.ACCOUNT_GROWTH_MIN_AGE_MONTHS} mesiacov s nenulovým GMV aspoň v jednom "
        f"z dvoch okien. Za churned sa považuje účet, ktorý "
        f"nenakúpil {C.KPI_DIAG_CHURN_DAYS} dní. Modrá skupina "
        f"nie je churned - len neobjednala práve v {C.GMV_WINDOW_MONTHS}-mesačnom "
        f"okne, a KPI ju tak počíta ako klesajúcu. "
        f"{base.population_note(int(activity['customers'].sum()), 'posudzovanými účtami')}",
        "bar",
        activity.index,
        [base.series("Počet účtov", activity["customers"], C.KPI_DIAG_COLOR_NEUTRAL,
                 point_colors=colors)],
        height=230,
        index_axis="y",
        value_format="count",
        hover_extras=base.kpi_hover(activity, lambda row: [
            f"Podiel posudzovaných účtov: {formatting.format_pct(row['share_pct'])}",
            f"GMV pred rokom: {formatting.format_eur(row['previous_gmv'])}",
        ]),
    )


def kpi_regular_ordering(scenario):
    """KPI dnes vs KPI, keby živé účty objednávali aspoň raz za okno."""
    converted = int(scenario["converted"].iloc[0])
    colors = [C.KPI_DIAG_COLOR_NEUTRAL, C.KPI_DIAG_COLOR_GOOD]
    return base.figure(
        "kpi_regular_ordering",
        f"KPI, keby živé účty objednávali aspoň raz za {C.GMV_WINDOW_MONTHS} mesiace",
        f"V %. Posudzuje sa v oboch stĺpcoch tá istá skupina účtov. Druhý stĺpec počíta "
        f"{converted} živých účtov, ktoré v aktuálnom okne nenakúpili, ako rastúce. "
        f"Je to horná hranica scenára, nie prognóza. "
        f"{base.population_note(int(scenario['customers'].iloc[0]), 'posudzovanými účtami')}",
        "bar",
        scenario.index,
        [base.series("% rastúcich účtov", scenario["growing_pct"], C.KPI_DIAG_COLOR_NEUTRAL,
                 point_colors=colors)],
        height=170,
        index_axis="y",
        value_format="pct",
        y_max=100,
        hover_extras=base.kpi_hover(scenario, lambda row: [
            f"Posudzovaných účtov: {formatting.format_number(row['customers'])}",
        ]),
    )


def kpi_churn_sensitivity(sensitivity):
    """KPI pri zabránení churnu, pre tri predpoklady o raste zachránených účtov."""
    prevented = int(sensitivity["prevented"].iloc[0])
    values = list(sensitivity["growing_pct"])
    target = [C.ACCOUNT_GROWTH_TARGET_PCT] * len(sensitivity)

    return base.figure(
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
            base.series(f"Cieľ {C.ACCOUNT_GROWTH_TARGET_PCT} %", target,
                    C.KPI_DIAG_COLOR_TARGET, chart_type="line", dashed=True),
            base.series("% rastúcich účtov", values, C.KPI_DIAG_COLOR_NEUTRAL,
                    point_colors=base.kpi_status_colors(values, values[0] + 0.01)),
        ],
        height=280,
        value_format="pct",
        y_max=70,
        hover_extras=base.kpi_hover(sensitivity, lambda row: [
            f"Posudzovaných účtov: {formatting.format_number(row['customers'])}",
            f"Zachránených účtov: {formatting.format_number(row['prevented'])}",
        ]),
    )
