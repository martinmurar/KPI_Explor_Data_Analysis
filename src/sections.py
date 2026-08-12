# -*- coding: utf-8 -*-
"""Jednotlivé sekcie reportu.

Každá funkcia vytvorí HTML jednej sekcie a zoznam grafov, ktoré v nej sú.
Čísla v texte sa vkladajú z metrík — nikde nie sú napísané natvrdo.
"""

import pandas as pd

from src import constants as C
import charts
import data
import metrics_account_growth
import metrics_kpi_diagnostics as MD
import report as R

EUR = R.format_eur
PCT = R.format_pct
NUM = R.format_number
SIGNED_EUR = R.format_signed_eur
SIGNED_PCT = R.format_signed_pct


def _fig(figures, figure_id):
    """Vykreslí graf podľa jeho ID, alebo nič, ak je v C.HIDDEN_CHARTS.

    Vypnúť/zapnúť graf v reporte znamená len upraviť C.HIDDEN_CHARTS —
    toto je jediné miesto, ktoré ten zoznam pri kreslení grafu čita.
    """
    if figure_id in C.HIDDEN_CHARTS:
        return ""
    for figure in figures:
        if figure["id"] == figure_id:
            return R.render_figure(figure)
    raise KeyError(f"graf s id '{figure_id}' nie je medzi figures")


def header(metrics):
    """Nadpis, prehľadové karty a hlavný nález."""
    quality = metrics["quality_displayed"]
    yearly = metrics["yearly"]
    churn = metrics["churn_curves"]
    account_growth = metrics["account_growth_summary"]

    partial = yearly.loc[C.PARTIAL_YEAR]
    yoy = metrics["yoy_growth"].loc[C.PARTIAL_YEAR, "growth_pct"]
    churn_now = churn[f"churn_{C.CHURN_MAIN_THRESHOLD_MONTHS}m"].iloc[-1]

    cards = [
        (f"GMV {data.year_label(C.PARTIAL_YEAR)}",
         EUR(partial["gmv"] / 1e6, 2).replace("\u00a0€", "\u00a0mil.\u00a0€")),
        ("Medziročný rast", SIGNED_PCT(yoy, 0)),
        (f"Medián objednávky {data.year_label(C.PARTIAL_YEAR)}",
         EUR(partial["median_order"])),
        (f"Churn (od {C.DISPLAY_START_YEAR})",
         PCT(churn_now, 0)),
        ("Account growth", PCT(account_growth["growing_pct"], 1)),
    ]

    html = f"""
<h1>Exploratívna dátová analýza — account growth B2B</h1>
{_header_facts(quality)}
{R.render_kpi_cards(cards)}
"""
    return html, []


def _header_facts(quality):
    """Odrážky so zdrojom dát a rozsahom zobrazovaného obdobia."""
    start = pd.Timestamp(year=C.DISPLAY_START_YEAR, month=1, day=1)

    return f"""
<ul class="lead">
<li>Zdroj: <code>{C.INPUT_XLSX}</code></li>
<li>Zobrazované obdobie: {start:%-d.\u00a0%-m.\u00a0%Y} – {C.AS_OF:%-d.\u00a0%-m.\u00a0%Y}</li>
<li>Objednávky: {NUM(quality["orders"])}</li>
<li>Zákazníci: {NUM(quality["customers"])}</li>
</ul>
"""


def trend_section(metrics):
    """Trend GMV a sezónnosť."""
    yearly = metrics["yearly"]
    seasonality = metrics["seasonality"]
    peak_month = seasonality.idxmax()
    low_month = seasonality.idxmin()

    quality = metrics["quality_displayed"]
    figures = [
        charts.monthly_trend(metrics["monthly"], quality["customers"]),
        charts.seasonality(seasonality, metrics["seasonality_customers"]),
    ]

    table = R.render_table(
        yearly,
        [("label", "Rok", str),
         ("orders", "Objednávky", NUM),
         ("gmv", "GMV", EUR),
         ("customers", "Zákazníci", NUM),
         ("orders_per_customer", "Obj./zákazník", lambda v: NUM(v, 1)),
         ("gmv_per_customer", "GMV/zákazník", EUR)],
        show_index=False,
    )

    html = f"""
<h2>1. Trend GMV</h2>
{_fig(figures, "monthly_trend")}
{table}
{_partial_year_note()}
{_fig(figures, "seasonality")}
<p>Najsilnejší mesiac je {peak_month}. ({PCT(seasonality.max())} ročného GMV), najslabší
{low_month}. ({PCT(seasonality.min())}). Rozdiel medzi špičkou a dnom je len
{NUM(seasonality.max() - seasonality.min(), 1)} p. b. — sezónnosť je mierna.
Percentuálny bod je aritmetický rozdiel dvoch podielov; relatívne je najsilnejší
mesiac o {SIGNED_PCT(seasonality.max() / seasonality.min() * 100 - 100, 0)} silnejší
než najslabší.</p>
"""
    return html, figures


def _partial_year_note():
    """Prečo sa hodnoty „na zákazníka" za nekompletný rok nedajú porovnávať."""
    return R.render_note(
        f"<b>Rok {data.year_label(C.PARTIAL_YEAR)} je nekompletný</b> — "
        f"{C.PARTIAL_YEAR_LAST_MONTH} mesiacov namiesto 12. Objednávky a GMV sú "
        f"preto nižšie, než bude celý rok, a stĺpce „Obj./zákazník\u201c "
        f"a „GMV/zákazník\u201c nie sú porovnateľné s predchádzajúcimi rokmi: "
        f"zákazník má v kratšom okne menej času objednať. Nečítaj z nich pokles.")


def bridge_section(metrics):
    """Komponenty medziročnej zmeny GMV."""
    bridge = metrics["bridge"]
    figure = charts.yearly_bridge(bridge, metrics["quality_displayed"]["customers"])

    columns = [("label", "Rok", str), ("delta", "Netto zmena", SIGNED_EUR)]
    for component in C.BRIDGE_COMPONENTS:
        columns.append((component, C.BRIDGE_LABELS_SK[component], SIGNED_EUR))
    table = R.render_table(bridge, columns, show_index=False)

    html = f"""
<h2>2. Komponenty medziročnej zmeny GMV</h2>
{_fig([figure], "yearly_bridge")}
{table}
{R.render_note(
    "<b>Pozor na interpretáciu položky Reaktivovaní pri ročných oknách.</b> "
    f"Pri celých rokoch znamená „nenakúpil celý predchádzajúci rok\u201c. Stĺpec "
    f"{data.year_label(C.PARTIAL_YEAR)} však porovnáva len Jan–Júl, takže sa doň dostanú aj "
    "zákazníci, ktorí nakúpili v druhej polovici predchádzajúceho roku. Jeho hodnota preto "
    "nie je porovnateľná s predchádzajúcimi rokmi a nemá sa z nej čítať počet reaktivácií.")}
"""
    return html, [figure]


def order_value_section(metrics):
    """Priemerná vs mediánová hodnota objednávky."""
    yearly = metrics["yearly"]
    figure = charts.order_value(yearly, metrics["quality_displayed"]["orders"])

    table = R.render_table(
        yearly,
        [("label", "Rok", str),
         ("mean_order", "Priemer", EUR),
         ("median_order", "Medián", EUR),
         ("mean_to_median", "Priemer / medián", lambda v: NUM(v, 2))],
        show_index=False,
    )

    first = yearly.iloc[0]
    last = yearly.iloc[-1]
    mean_growth = (last["mean_order"] / first["mean_order"] - 1) * 100
    median_growth = (last["median_order"] / first["median_order"] - 1) * 100

    html = f"""
<h2>3. Priemerná vs mediánová hodnota objednávky</h2>
{_fig([figure], "order_value")}
{table}
<p>Od {first["label"]} do {last["label"]} vzrástol priemer o {SIGNED_PCT(mean_growth, 0)},
zatiaľ čo medián o {SIGNED_PCT(median_growth, 0)}. Pomer priemer/medián sa zdvihol
z {NUM(first["mean_to_median"], 1)}× na {NUM(last["mean_to_median"], 1)}×.
Typická objednávka sa nezmenila; zmenil sa chvost.</p>
"""
    return html, [figure]


def concentration_section(metrics):
    """Koncentrácia portfólia."""
    concentration = metrics["concentration"]

    figures = [charts.concentration_shares(concentration)]

    concentration_table = R.render_table(
        concentration,
        [("label", "Rok", str),
         ("customers", "Zákazníci", NUM),
         ("top1_pct", "Top 1", PCT),
         ("top5_pct", "Top 5", PCT),
         ("top10_pct", "Top 10", PCT),
         ("top20_pct", "Top 20", PCT),
         ("customers_for_80pct", "Zák. na 80 % GMV", NUM),
         ("hhi", "HHI", lambda v: NUM(v, 0)),
         ("gini", "Gini", lambda v: NUM(v, 2))],
        show_index=False,
    )

    first = concentration.iloc[0]
    last = concentration.iloc[-1]

    html = f"""
<h2>4. Koncentrácia portfólia</h2>
{_fig(figures, "concentration_shares")}
{concentration_table}
<p>Podiel top 5 zákazníkov sa zmenil z {PCT(first["top5_pct"])} ({first["label"]}) na
{PCT(last["top5_pct"])} ({last["label"]}). 80 % GMV dnes tvorí iba
{NUM(last["customers_for_80pct"])} zákazníkov oproti
{NUM(first["customers_for_80pct"])} v roku {first["label"]}.</p>
"""
    return html, figures


def account_growth_section(metrics):
    """Interné KPI account growth, jeho príčiny a štruktúra rastu GMV."""
    summary = metrics["account_growth_summary"]
    history = metrics["account_growth_history"]
    composition = metrics["account_growth_composition"]
    diag = metrics["diag_summary"]

    figures = [
        charts.account_growth_over_time(history),
        charts.account_growth_composition(composition),
        charts.kpi_frequency_effect(metrics["diag_frequency"], diag["growing_pct"]),
        charts.kpi_by_order_count(metrics["diag_by_order_count"], diag["growing_pct"]),
        charts.kpi_activity_split(metrics["diag_activity_split"]),
        charts.kpi_regular_ordering(metrics["diag_regular_scenario"]),
        charts.kpi_churn_sensitivity(metrics["diag_churn_sensitivity"]),
        charts.net_gmv_by_band(metrics["growth_by_band"], metrics["band_window"]),
    ]

    html = f"""
<h2>5. Account growth a štruktúra rastu</h2>
{_account_growth_definition(summary)}
{_fig(figures, "account_growth_over_time")}
{_account_growth_trend_text(history, summary)}

<h3>Z čoho sa skladajú posudzované účty</h3>
{_fig(figures, "account_growth_composition")}
{_account_growth_composition_table(composition)}
{_account_growth_composition_text(composition, summary)}

<h3>Čím je rozhodnuté, či účet rastie</h3>
{_fig(figures, "kpi_frequency")}
{_frequency_text(metrics)}
{_fig(figures, "kpi_by_order_count")}
{_order_count_text(metrics)}

<h3>Kedy účty naposledy nakúpili</h3>
{_fig(figures, "kpi_activity_split")}
{_activity_text(metrics)}
{_fig(figures, "kpi_regular_ordering")}
{_regular_ordering_text(metrics)}

<h3>Čo ak by sme zabránili churnu</h3>
{_fig(figures, "kpi_churn_sensitivity")}
{_churn_sensitivity_text(metrics)}

<h3>Netto GMV podľa veľkostného pásma</h3>
{_fig(figures, "net_gmv_by_band")}
{_band_gmv_text(metrics)}
{_top_band_table(metrics)}
"""
    return html, figures


def _band_gmv_text(metrics):
    """Odstavec k netto zmene GMV podľa pásma."""
    growth = metrics["growth_by_band"]

    top_band = growth.iloc[-1]
    smaller = growth.iloc[:-1]

    return f"""
<p>Pásmo {growth.index[-1]} pridalo {SIGNED_EUR(top_band["net_delta"])} pri
{int(top_band["customers"])} účtoch. Všetky ostatné pásma spolu
{SIGNED_EUR(smaller["net_delta"].sum())} pri {int(smaller["customers"].sum())} účtoch.</p>
"""


def _top_band_table(metrics):
    """Tabuľka účtov v najvyššom pásme."""
    growth = metrics["growth_by_band"]
    table = R.render_table(
        metrics["top_band_detail"],
        [("previous", "GMV pred rokom", EUR),
         ("current", "GMV teraz", EUR),
         ("delta", "Netto zmena", SIGNED_EUR)],
        index_label="Účet",
    )

    return f"""
<h4 style="font-size:14px;font-weight:500;margin:24px 0 8px">Účty v pásme
{R.escape(growth.index[-1])}</h4>
{table}
<p class="small">Zoradené podľa netto zmeny. Účet bez vyplneného
<code>company_bill</code> je uvedený e-mailom. Tá istá firma sa môže objaviť
viackrát, ak nakupuje z viacerých e-mailov.</p>
"""


def _frequency_text(metrics):
    """Odstavec k rastu podľa počtu objednávok."""
    frequency = metrics["diag_frequency"]
    more = frequency.loc[MD.FREQUENCY_MORE]
    same = frequency.loc[MD.FREQUENCY_SAME]
    fewer = frequency.loc[MD.FREQUENCY_FEWER]

    return f"""
<p>Vzťah je takmer deterministický: účet, ktorý objedná viackrát než pred rokom,
rastie v {PCT(more["growing_pct"])} prípadov, pri rovnakom počte je to coin flip
({PCT(same["growing_pct"])}) a pri nižšom počte je účet odpísaný
({PCT(fewer["growing_pct"])}). <b>Rast účtu v tomto KPI je o frekvencii, nie
o veľkosti objednávky.</b></p>
"""


def _order_count_text(metrics):
    """Odstavec ku KPI podľa počtu objednávok za rok."""
    breakdown = metrics["diag_by_order_count"]
    summary = metrics["account_growth_summary"]

    dormant = breakdown.loc[C.KPI_ORDER_COUNT_BUCKETS[0]]
    top = breakdown.iloc[-1]
    thin = breakdown.iloc[1:3]
    dormant_share = dormant["customers"] / breakdown["customers"].sum() * 100

    return f"""
<p>KPI rastie s frekvenciou naprieč celým rozsahom: od {PCT(thin["growing_pct"].min())}
pri účtoch s jednou či dvoma objednávkami po {PCT(top["growing_pct"])} pri účtoch
s {breakdown.index[-1]} objednávkami. <b>Cieľ {C.ACCOUNT_GROWTH_TARGET_PCT} % dosahuje
jediný kôš — ten najfrekventovanejší.</b></p>
<p>Kôš 0 je {PCT(dormant["growing_pct"])} z definície: kto za
{C.FREQUENCY_WINDOW_MONTHS} mesiacov nenakúpil, nemá GMV ani v kratšom okne KPI
a je automaticky klesajúci. Práve to je jeho výpoveď — <b>{NUM(dormant["customers"])}
z {NUM(breakdown["customers"].sum())} posudzovaných účtov
({PCT(dormant_share)}) je celý rok mŕtvych</b> a KPI ich napriek tomu drží
v menovateli. Bez nich by celkových {PCT(summary["growing_pct"])} bolo
{PCT(summary["growing"] / (breakdown["customers"].sum() - dormant["customers"]) * 100)}.</p>
"""


def _activity_text(metrics):
    """Odstavec k rozdeleniu posudzovaných účtov podľa poslednej objednávky."""
    activity = metrics["diag_activity_split"]
    in_window = activity.iloc[0]
    outside = activity.iloc[1]
    churned = activity.iloc[2]

    diag = metrics["diag_summary"]
    composition = metrics["account_growth_composition"]
    automatic = int(composition.loc[metrics_account_growth.COMPOSITION_NO_PREVIOUS, "customers"])
    both = int(composition.loc[metrics_account_growth.COMPOSITION_BOTH, "customers"])

    return f"""
<p>V aktuálnom okne nakúpilo {NUM(in_window["customers"])} účtov
({PCT(in_window["share_pct"])} posudzovaných účtov) a rastie z nich
{PCT(in_window["growing_pct"])}. To číslo je ale nadhodnotené — {NUM(automatic)}
z tých {NUM(in_window["customers"])} účtov malo pred rokom nulové GMV a je rastúcich
automaticky. Z {NUM(both)} účtov, ktoré nakúpili v oboch oknách, rastie
{PCT(diag["active_in_both_growing_pct"])}. Ostatné dve skupiny majú
{PCT(0)} rastúcich z definície. Medzi nimi leží {NUM(outside["customers"])} účtov,
ktoré nakúpili za posledných {C.KPI_DIAG_CHURN_DAYS} dní, ale mimo okna: nie sú
churnuté a predstavujú {EUR(outside["previous_gmv"])} minuloročného GMV.
Churnutých je {NUM(churned["customers"])}.</p>
"""


def _regular_ordering_text(metrics):
    """Odstavec k scenáru pravidelného objednávania."""
    scenario = metrics["diag_regular_scenario"]
    outside = int(scenario["converted"].iloc[0])
    reported = scenario["growing_pct"].iloc[0]
    scenario_pct = scenario["growing_pct"].iloc[1]

    return f"""
<p>Ak by tých {NUM(outside)} účtov objednávalo aspoň raz za
{C.GMV_WINDOW_MONTHS} mesiace, KPI by bolo {PCT(scenario_pct)} namiesto
{PCT(reported)}, teda o {NUM(scenario_pct - reported, 1)} p. b. vyššie bez jediného
nového zákazníka. Je to <b>horná hranica, nie prognóza</b> — každý z tých účtov má
nenulové minuloročné GMV, takže rastúcim sa stane len ten, ktorý ho prekročí.</p>
"""


def _churn_sensitivity_text(metrics):
    """Odstavec k scenáru zabráneného churnu."""
    sensitivity = metrics["diag_churn_sensitivity"]
    prevented = int(sensitivity["prevented"].iloc[0])
    lowest = sensitivity["growing_pct"].iloc[0]
    highest = sensitivity["growing_pct"].iloc[-1]

    return f"""
<p>Ak by všetkých {NUM(prevented)} churnutých účtov bolo aktívnych v okne, KPI by
podľa predpokladu o ich raste bolo {PCT(lowest)} až {PCT(highest)}.</p>
"""


def _account_growth_definition(summary):
    """Úvodný odstavec: definícia KPI a jeho aktuálna hodnota."""
    return f"""
<p>KPI porovnáva GMV účtu za posledné {C.GMV_WINDOW_MONTHS} mesiace s GMV za to isté okno
o rok skôr. Účet rastie, ak je aktuálne GMV vyššie. Posudzuje sa účet, ktorý je
starší ako {C.ACCOUNT_GROWTH_MIN_AGE_MONTHS} mesiacov <b>a</b> bol aktívny aspoň v jednom
z dvoch okien.</p>
{R.render_note(
    f"<b>Aktuálna hodnota: {PCT(summary['growing_pct'])}</b> "
    f"({NUM(summary['growing'])} z {NUM(summary['accounts'])} účtov). Do cieľa "
    f"{C.ACCOUNT_GROWTH_TARGET_PCT} % chýba {NUM(summary['accounts_needed_for_target'])} "
    f"ďalších rastúcich účtov. Zároveň ale "
    f"<b>{PCT(summary['gmv_growing_pct'])} tržieb už v rastúcich účtoch leží</b>.")}
"""


def _account_growth_trend_text(history, summary):
    """Odstavec k časovému radu KPI."""
    trough_date = history["growing_pct"].idxmin()
    peak_date = history["growing_pct"].idxmax()
    trough = history.loc[trough_date, "growing_pct"]
    peak = history.loc[peak_date, "growing_pct"]

    return f"""
<p>KPI nie je v prepade. Od dna {PCT(trough)} ({trough_date:%-m/%Y}) sa vrátilo na
{PCT(summary["growing_pct"])} a posledné štyri kvartály rastie. <b>KPI je práve teraz na
maxime celého radu ({PCT(peak)}, {peak_date:%-m/%Y}) — cieľ {C.ACCOUNT_GROWTH_TARGET_PCT} %
sa v tomto rozsahu dát nikdy nedosiahol.</b> Nie je to teda návrat do normálu, ale nová
hodnota, a to by malo vstúpiť do rozhovoru o tom, či je cieľ realistický.</p>
<p>GMV-vážená línia je celý čas výrazne vyššia než stĺpce. Rozdiel medzi nimi je mierou
toho, ako silno nevážené KPI váži drobné účty rovnako ako strategické.</p>
"""


def _account_growth_composition_table(composition):
    """Tabuľka rozkladu posudzovaných účtov."""
    return R.render_table(
        composition,
        [("customers", "Účty", NUM),
         ("share_pct", "% posudzovaných účtov", PCT),
         ("growing_pct", "% rastúcich", PCT),
         ("previous_gmv", "GMV pred rokom", EUR),
         ("current_gmv", "GMV teraz", EUR)],
        index_label="Skupina",
    )


def _account_growth_composition_text(composition, summary):
    """Odstavec k rozkladu posudzovaných účtov."""
    no_previous = composition.loc[metrics_account_growth.COMPOSITION_NO_PREVIOUS]
    dropped = composition.loc[metrics_account_growth.COMPOSITION_DROPPED]
    both = composition.loc[metrics_account_growth.COMPOSITION_BOTH]
    binary_share = no_previous["share_pct"] + dropped["share_pct"]

    return f"""
<p>Posudzované účty nie sú homogénne — sedia v nich tri rôzne situácie.
<b>Pri {PCT(binary_share)} účtov je výsledok rozhodnutý už tým, či účet v okne vôbec
nakúpil.</b> {NUM(no_previous["customers"])} účtov bez GMV v minuloročnom okne (pred rokom
nenakúpili, teraz áno) je rastúcich automaticky, lebo z nuly rastie čokoľvek. Nie sú
to nutne reaktivované účty — medián ich medzery je okolo štyroch mesiacov, väčšina
z nich len jedno okno vynechala.
{NUM(dropped["customers"])} odídených účtov (pred rokom nakúpili, teraz už nie) je
z rovnakého dôvodu automaticky klesajúcich. Skutočnú zmenu objemu meria len zvyšných
{NUM(both["customers"])} účtov aktívnych v oboch oknách — a tam rastie
{PCT(both["growing_pct"])}, teda takmer presne pol na pol.</p>
<p>KPI sa preto hýbe hlavne cez pády do nuly, nie cez rast existujúcich účtov:
s odídenými účtami zmizlo {EUR(dropped["previous_gmv"])} z minuloročného okna.
<b>KPI sa nezvýši tým, že účty prinútime rásť — zvýši sa tým, že ich nedopustíme spadnúť
do nuly.</b></p>
"""


def loyalty_section(metrics):
    """Zákazníci s jednou objednávkou a frekvencia objednávania."""
    single = metrics["single_order"]
    frequency = metrics["frequency"]

    figures = [
        charts.single_order_by_cohort(single),
        charts.frequency_histogram(frequency),
    ]

    single_table = R.render_table(
        single,
        [("label", "Kohorta", str),
         ("customers", "Zákazníci", NUM),
         ("single_order_pct", "% s 1 objednávkou", PCT),
         ("median_orders", "Medián objednávok", lambda v: NUM(v, 0)),
         ("median_ltv", "Medián LTV", EUR)],
        show_index=False,
    )

    mature = single.loc[~single["is_immature"]]
    first = mature.iloc[0]
    last = mature.iloc[-1]
    one_order = frequency.loc["1"]
    two_orders = frequency.loc["2"]
    top_bucket = frequency.iloc[-1]
    total_base = int(frequency["customers_at_or_above"].iloc[0])

    html = f"""
<h2>6. Lojalita a frekvencia</h2>
{_fig(figures, "single_order")}
{single_table}
<p>Podiel zákazníkov s jedinou objednávkou za život stúpol z {PCT(first["single_order_pct"])}
(kohorta {first["label"]}) na {PCT(last["single_order_pct"])} ({last["label"]}). Medián
objednávok za život klesol z {NUM(first["median_orders"])} na {NUM(last["median_orders"])}
a medián LTV z {EUR(first["median_ltv"])} na {EUR(last["median_ltv"])}. <b>LTV</b> je tu
celkové GMV, ktoré zákazník utratil od svojej prvej objednávky do
{C.AS_OF:%-d.\u00a0%-m.\u00a0%Y} — teda doterajšia, nie predikovaná hodnota. Akvizícia
rastie v počte a klesá v kvalite.</p>
{_fig(figures, "frequency_histogram")}
<p>Zahrnutí sú zákazníci, ktorí za posledných {C.FREQUENCY_WINDOW_MONTHS} mesiacov
aspoň raz nakúpili — {NUM(total_base)} zákazníkov. <b>Najväčšia skupina má jedinú
objednávku</b>: {NUM(one_order["customers"])} ({PCT(one_order["share_pct"])}).
Dve objednávky má {NUM(two_orders["customers"])} zákazníkov
({PCT(two_orders["share_pct"])}).</p>
<p>Rozdelenie je monotónne klesajúce — čím vyššia frekvencia, tým menej zákazníkov,
bez akéhokoľvek typického nákupného rytmu, okolo ktorého by sa účty zhlukovali.
Aspoň desať objednávok má už len
{PCT(frequency.loc["10"]["share_at_or_above_pct"])} všetkých účtov a v poslednom koši
({top_bucket.name} objednávok) je {NUM(top_bucket["customers"])} zákazníkov, teda
{PCT(top_bucket["share_pct"])}. Práve tí ale tvoria väčšinu tržieb —
{PCT(top_bucket["gmv_share_at_or_above_pct"])} GMV za posledných
{C.FREQUENCY_WINDOW_MONTHS} mesiacov. Väčšina nakupujúcich má s nami len jednorazový
kontakt.</p>
{_frequency_vs_concentration_note(metrics, top_bucket)}
"""
    return html, figures


def _frequency_vs_concentration_note(metrics, top_bucket):
    """Prečo sa toto číslo nerovná počtu účtov na 80 % GMV zo sekcie 4."""
    concentration = metrics["concentration"].iloc[-1]
    window = metrics["frequency_window"]

    return R.render_note(
        f"<b>Prečo je tu {NUM(top_bucket['customers'])} účtov a v sekcii 4 stačí na "
        f"80 % GMV len {NUM(concentration['customers_for_80pct'])}.</b> Nie je to "
        f"rozpor — sú to iné skupiny účtov vybrané podľa iného kritéria. V sekcii 4 sa "
        f"účty zoradia <b>podľa veľkosti GMV</b> a sčítavajú od najväčšieho, takže "
        f"vznikne najmenšia možná skupina, ktorá tú hranicu prekročí. Tu sa vyberajú "
        f"<b>podľa frekvencie nakupovania</b>, teda podľa počtu objednávok — a akékoľvek "
        f"iné kritérium než veľkosť potrebuje na rovnaký podiel GMV viac účtov. "
        f"Skupiny sa prekrývajú len z časti: nájdu sa veľkí zákazníci, ktorí nakupujú "
        f"zriedka a vo veľkých dávkach, aj veľmi častí, ale drobní odberatelia. "
        f"Líšia sa aj okná — sekcia 4 počíta kalendárny rok "
        f"{data.year_label(C.PARTIAL_YEAR)}, tento graf posledných "
        f"{C.FREQUENCY_WINDOW_MONTHS} mesiacov "
        f"({window['start']:%-d.\u00a0%-m.\u00a0%Y} – {window['end']:%-d.\u00a0%-m.\u00a0%Y}).")


def conclusions(metrics):
    """Zhrnutie a odporúčania."""
    html = f"""
<h2>7. Zhrnutie</h2>
{_summary_list(metrics)}

<h3>Odporúčania</h3>
{_recommendations(metrics)}
"""
    return html, []


def _summary_list(metrics):
    """Zistenia, ktoré report skutočne dokladá grafmi."""
    summary = metrics["account_growth_summary"]
    composition = metrics["account_growth_composition"]
    diag = metrics["diag_summary"]
    frequency = metrics["diag_frequency"]
    scenario = metrics["diag_regular_scenario"]
    sensitivity = metrics["diag_churn_sensitivity"]
    growth = metrics["growth_by_band"]
    concentration = metrics["concentration"].iloc[-1]
    curves = metrics["churn_curves"]
    yearly = metrics["yearly"]
    single = metrics["single_order"]
    histogram = metrics["frequency"]

    dropped = composition.loc[metrics_account_growth.COMPOSITION_DROPPED]
    both = composition.loc[metrics_account_growth.COMPOSITION_BOTH]
    binary_share = (composition.loc[metrics_account_growth.COMPOSITION_NO_PREVIOUS,
                                    "share_pct"] + dropped["share_pct"])
    top_band = growth.iloc[-1]
    smaller_bands = growth.iloc[:-1]
    churn_now = curves.iloc[-1][f"churn_{C.CHURN_MAIN_THRESHOLD_MONTHS}m"]
    mature_cohorts = single.loc[~single["is_immature"]]

    return f"""
<ol>
<li><b>KPI je na maxime celého radu a cieľ je aj tak ďaleko.</b> Account growth je
{PCT(summary["growing_pct"])} ({NUM(summary["growing"])} z {NUM(summary["accounts"])}
posudzovaných účtov), čo je najviac za celé zobrazované obdobie — a cieľ
{C.ACCOUNT_GROWTH_TARGET_PCT} % sa v ňom nedosiahol ani raz. Do cieľa chýba
{NUM(summary["accounts_needed_for_target"])} ďalších rastúcich účtov.</li>

<li><b>KPI meria hlavne to, či účet v okne nakúpil, nie či vyrástol.</b> Pri
{PCT(binary_share)} posudzovaných účtov je výsledok rozhodnutý binárne: bez GMV pred rokom
rastie účet automaticky, kto odišiel do nuly, automaticky klesá. Skutočnú zmenu objemu meria
len {NUM(both["customers"])} účtov aktívnych v oboch oknách a tam rastie
{PCT(both["growing_pct"])}. S {NUM(dropped["customers"])} odídenými účtami zmizlo
{EUR(dropped["previous_gmv"])} minuloročného GMV.</li>

<li><b>O raste účtu rozhoduje frekvencia, nie veľkosť objednávky.</b> Účet, ktorý objedná
viackrát než pred rokom, rastie v {PCT(frequency.loc[MD.FREQUENCY_MORE, "growing_pct"])}
prípadov; pri nižšom počte objednávok len v
{PCT(frequency.loc[MD.FREQUENCY_FEWER, "growing_pct"])}.</li>

<li><b>Priestor v KPI leží v aktivite, nie v tlaku na rast.</b> Z posudzovaných účtov
{NUM(diag["outside_window"])} je živých, ale netrafilo okno — keby objednávali aspoň raz za
{C.GMV_WINDOW_MONTHS} mesiace, KPI by bolo {PCT(scenario["growing_pct"].iloc[1])}. Ďalších
{NUM(diag["churned"])} účtov je churnutých; keby boli aktívne, KPI by podľa predpokladu
o ich raste bolo {PCT(sensitivity["growing_pct"].iloc[0])} až
{PCT(sensitivity["growing_pct"].iloc[-1])}. Cieľ {C.ACCOUNT_GROWTH_TARGET_PCT} % je teda
dosiahnuteľný len cez udržanie účtov v okne, nie cez rast tých, ktoré už nakupujú.</li>

<li><b>Rast GMV je silne koncentrovaný.</b> Pásmo {growth.index[-1]} —
{int(top_band["customers"])} účtov — pridalo {SIGNED_EUR(top_band["net_delta"])}, kým
všetky ostatné pásma spolu {SIGNED_EUR(smaller_bands["net_delta"].sum())} pri
{int(smaller_bands["customers"].sum())} účtoch. Top 1 zákazník je
{PCT(concentration["top1_pct"])} GMV, top 10 je {PCT(concentration["top10_pct"])}, a na
80 % GMV stačí {NUM(concentration["customers_for_80pct"])} zákazníkov.</li>

<li><b>Nevážené KPI a tržby hovoria dve rôzne veci.</b> Rastúce účty držia
{PCT(summary["gmv_growing_pct"])} tržieb aktuálneho okna, ale v neváženom KPI sú len
{PCT(summary["growing_pct"])} účtov. Rozdiel je celý o tom, že nevážená metrika váži drobný
účet rovnako ako strategický.</li>

<li><b>Typická objednávka sa nemení, rastie chvost.</b> Medián hodnoty objednávky je
{EUR(yearly.iloc[-1]["median_order"])} oproti {EUR(yearly.iloc[0]["median_order"])}
v {yearly.iloc[0]["label"]}, zatiaľ čo priemer stúpol na
{EUR(yearly.iloc[-1]["mean_order"])}. Pomer priemer/medián sa zdvihol na
{NUM(yearly.iloc[-1]["mean_to_median"], 1)}×.</li>

<li><b>Akvizícia klesá v kvalite a churn je vysoký.</b> Podiel zákazníkov s jedinou
objednávkou za život stúpol z {PCT(mature_cohorts.iloc[0]["single_order_pct"])} (kohorta
{mature_cohorts.iloc[0]["label"]}) na {PCT(mature_cohorts.iloc[-1]["single_order_pct"])}
({mature_cohorts.iloc[-1]["label"]}) a z tých, čo za posledných
{C.FREQUENCY_WINDOW_MONTHS} mesiacov vôbec nakúpili, má
{PCT(histogram.loc["1"]["share_pct"])} jedinú objednávku.
{C.CHURN_MAIN_THRESHOLD_MONTHS}-mesačný churn je {PCT(churn_now)}.</li>
</ol>
"""


def _recommendations(metrics):
    """Čo s tým robiť."""
    diag = metrics["diag_summary"]
    scenario = metrics["diag_regular_scenario"]
    activity = metrics["diag_activity_split"]
    growth = metrics["growth_by_band"]
    smaller_bands = growth.iloc[:-1]
    gain = scenario["growing_pct"].iloc[1] - scenario["growing_pct"].iloc[0]

    return f"""
<ol>
<li><b>Udržať živé účty v okne.</b> {NUM(diag["outside_window"])} účtov nakúpilo za
posledných {C.KPI_DIAG_CHURN_DAYS} dní, ale nie v aktuálnom okne, a nesie
{EUR(activity.iloc[1]["previous_gmv"])} minuloročného GMV. Je to
{NUM(gain, 1)} p. b. v KPI bez jediného nového zákazníka.</li>
<li><b>Prevencia churnu pred win-backom.</b> {NUM(diag["churned"])} churnutých účtov je
celý zvyšok cesty k cieľu — a účet, ktorý raz spadne na nulu, ťahá KPI dole aj celý
nasledujúci rok.</li>
<li><b>Pracovať s frekvenciou, nie s veľkosťou objednávky.</b> Keď má účet objednať
aspoň raz za {C.GMV_WINDOW_MONTHS} mesiace, je to konkrétny cieľ pre account managera;
„zvýšiť objem“ nie je.</li>
<li><b>Znížiť závislosť na top účtoch.</b> Všetky pásma okrem {growth.index[-1]} sú spolu
netto {SIGNED_EUR(smaller_bands["net_delta"].sum())} — rast dnes stojí na
{int(growth.iloc[-1]["customers"])} účtoch.</li>
<li><b>Zamerať sa na druhú objednávku.</b> Rastúci podiel zákazníkov s jedinou objednávkou
je najlacnejšia páka — druhá objednávka rozhoduje o celej kohorte.</li>
<li><b>Kvalifikovať akvizíciu.</b> Buď oddeliť drobných odberateľov do samoobslužného
segmentu bez account managementu, alebo zvýšiť vstupnú hranicu.</li>
</ol>
"""


SECTION_BUILDERS = [
    header,
    trend_section,
    bridge_section,
    order_value_section,
    concentration_section,
    account_growth_section,
    loyalty_section,
    conclusions,
]


def build_all(metrics):
    """Poskladá HTML všetkých sekcií a zoznam grafov, ktoré sa naozaj vykreslili.

    Každá sekcia ide cez render_collapsible, takže sa dá zbaliť za jej nadpis.
    Hlavička sa nezbaľuje — nemá <h2>, vráti sa nedotknutá a hneď za ňu patria
    ovládacie tlačidlá.

    Grafy skryté cez C.HIDDEN_CHARTS sa sem nedostanú — inak by Chart.js na
    strane prehliadača skúšal nakresliť graf do neexistujúceho <canvas> a
    spadol by aj so zvyšnými grafmi za ním.
    """
    html_parts = []
    figures = []
    for position, builder in enumerate(SECTION_BUILDERS):
        section_html, section_figures = builder(metrics)
        html_parts.append(R.render_collapsible(section_html))
        if position == 0:
            html_parts.append(R.FOLD_TOOLBAR_HTML)
        for figure in section_figures:
            if figure["id"] not in C.HIDDEN_CHARTS:
                figures.append(figure)
    return "\n".join(html_parts), figures
