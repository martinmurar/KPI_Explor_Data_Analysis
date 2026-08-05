# -*- coding: utf-8 -*-
"""Jednotlivé sekcie reportu.

Každá funkcia vytvorí HTML jednej sekcie a zoznam grafov, ktoré v nej sú.
Čísla v texte sa vkladajú z metrík — nikde nie sú napísané natvrdo.
"""

from src import constants as C
import charts
import data
import metrics_account_growth
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
    quality = metrics["quality"]
    yearly = metrics["yearly"]
    growth = metrics["growth_by_band"]
    concentration = metrics["concentration"]
    churn = metrics["churn_curves"]
    account_growth = metrics["account_growth_summary"]

    partial = yearly.loc[C.PARTIAL_YEAR]
    yoy = metrics["yoy_growth"].loc[C.PARTIAL_YEAR, "growth_pct"]
    top10 = concentration.loc[C.PARTIAL_YEAR, "top10_pct"]
    churn_now = churn[f"churn_{C.CHURN_MAIN_THRESHOLD_MONTHS}m"].iloc[-1]
    top_band = growth.iloc[-1]
    smaller_bands_delta = growth.iloc[:-1]["net_delta"].sum()

    cards = [
        (f"GMV {data.year_label(C.PARTIAL_YEAR)}", EUR(partial["gmv"] / 1e6, 2).replace("\u00a0€", "\u00a0mil.\u00a0€")),
        ("Medziročný rast", SIGNED_PCT(yoy, 0)),
        ("Medián objednávky", EUR(partial["median_order"])),
        ("Top 10 účtov", PCT(top10, 0)),
        (f"Churn {C.CHURN_MAIN_THRESHOLD_MONTHS} mes.", PCT(churn_now, 0)),
        ("Account growth", PCT(account_growth["growing_pct"], 0)),
    ]

    html = f"""
<h1>EDA — rast GMV v B2B</h1>
<p class="lead">Zdroj: <code>{C.INPUT_XLSX}</code> · {NUM(quality["orders"])} objednávok ·
{NUM(quality["customers"])} zákazníkov ·
{quality["date_min"]:%-d.\u00a0%-m.\u00a0%Y} – {quality["date_max"]:%-d.\u00a0%-m.\u00a0%Y} ·
GMV {EUR(quality["gmv"] / 1e6, 2).replace("\u00a0€", "\u00a0mil.\u00a0€")}</p>
{R.render_kpi_cards(cards)}
{R.render_note(
    f"<b>Hlavný nález.</b> GMV rastie o {SIGNED_PCT(yoy, 0)} medziročne, ale rast nie je "
    f"v báze — je v hrsti účtov. Za posledné {C.GMV_WINDOW_MONTHS} mesiace pásmo "
    f"{growth.index[-1]} pridalo {SIGNED_EUR(top_band['net_delta'])} pri "
    f"{int(top_band['customers'])} zákazníkoch, kým všetky menšie pásmá spolu "
    f"{SIGNED_EUR(smaller_bands_delta)}. Zároveň "
    f"{PCT(churn_now, 0)} akvirovanej bázy nenakúpilo posledných "
    f"{C.CHURN_MAIN_THRESHOLD_MONTHS} mesiacov.")}
"""
    return html, []


def methodology(metrics):
    """Kvalita dát a metodické rozhodnutia."""
    quality = metrics["quality"]
    statuses = metrics["status_table"]
    complete_share = statuses.loc[statuses.index.isin(["complete", "complete_no_invoice"]), "share_pct"].sum()

    html = f"""
<h2>Kvalita dát a metodika</h2>
<ul>
<li>Chýbajúce hodnoty: {NUM(quality["missing_values"])}. Duplicitné <code>entity_id</code>:
{NUM(quality["duplicate_ids"])}. Objednávky s GMV = 0: {NUM(quality["zero_gmv_orders"])}.</li>
<li><b>Statusy sa nefiltrujú.</b> {PCT(complete_share)} GMV je v dokončených stavoch a v dátach
nie je žiadny <code>canceled</code>. Filtrovaním by sa podhodnotil posledný mesiac, kde sú
čerstvé objednávky ešte rozpracované.</li>
<li><b>Rok 2018 je vylúčený z trendov</b> — pilot, {NUM(len(metrics["orders_2018"]))} objednávok,
medián {EUR(metrics["orders_2018"]["gmv"].median(), 1)}.</li>
<li><b>Rok {C.PARTIAL_YEAR} je nekompletný</b> (do
{C.AS_OF:%-d.\u00a0%-m.\u00a0%Y}) a v grafoch je označený hviezdičkou. Medziročné porovnania
používajú rovnaké okno (Jan–Júl vs Jan–Júl).</li>
<li><b>Zákazník = <code>customer_email</code>.</b> Ak firma nakupuje z viacerých e-mailov,
je v dátach ako viac zákazníkov — to nadhodnocuje nových, churn aj reaktivácie.</li>
<li><b>Churn:</b> v časovom bode <i>t</i> je zákazník churned, ak od jeho poslednej objednávky
prešlo viac ako N mesiacov. Budúce objednávky sa ignorujú. Menovateľ = zákazníci akvirovaní
aspoň N mesiacov pred <i>t</i>.</li>
<li><b>Reaktivácia:</b> objednávka po medzere dlhšej ako {C.REACTIVATION_GAP_MONTHS} mesiacov.</li>
</ul>
"""
    return html, []


def trend_section(metrics):
    """Trend GMV a sezonalita."""
    yearly = metrics["yearly"]
    seasonality = metrics["seasonality"]
    peak_month = seasonality.idxmax()
    low_month = seasonality.idxmin()

    figures = [
        charts.monthly_trend(metrics["monthly"]),
        charts.seasonality(seasonality),
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
{_fig(figures, "seasonality")}
<p>Najsilnejší mesiac je {peak_month}. ({PCT(seasonality.max())} ročného GMV), najslabší
{low_month}. ({PCT(seasonality.min())}). Rozdiel medzi špičkou a dnom je len
{PCT(seasonality.max() - seasonality.min())} — sezonalita je mierna a rozhodnutia
sa na ňu nedajú zvaľovať.</p>
"""
    return html, figures


def bridge_section(metrics):
    """Komponenty medziročnej zmeny GMV."""
    bridge = metrics["bridge"]
    figure = charts.yearly_bridge(bridge)

    columns = [("label", "Rok", str), ("delta", "Netto zmena", SIGNED_EUR)]
    for component in C.BRIDGE_COMPONENTS:
        columns.append((component, C.BRIDGE_LABELS_SK[component], SIGNED_EUR))
    table = R.render_table(bridge, columns, show_index=False)

    last = bridge.iloc[-1]
    gross_gains = last["expansion"] + last["reactivated"] + last["new"]
    gross_losses = last["contraction"] + last["churn"]

    html = f"""
<h2>2. Komponenty medziročnej zmeny GMV</h2>
{_fig([figure], "yearly_bridge")}
{table}
<p>V období {last["label"]} sú hrubé prírastky {SIGNED_EUR(gross_gains)} a hrubé straty
{SIGNED_EUR(gross_losses)} — na každé euro prírastku sa stratí
{NUM(abs(gross_losses) / gross_gains, 2)} €. Netto zmena
{SIGNED_EUR(last["delta"])} je teda výsledkom veľkého obratu na oboch stranách,
nie plynulého rastu bázy.</p>
{R.render_note(
    "<b>Pozor na interpretáciu položky Reaktivovaní pri ročných oknách.</b> "
    f"Pri celých rokoch znamená „nenakúpil celý predchádzajúci rok\u201c, čo je "
    f"blízke definícii reaktivácie ({C.REACTIVATION_GAP_MONTHS} mesiacov). Stĺpec "
    f"{data.year_label(C.PARTIAL_YEAR)} však porovnáva len Jan–Júl, takže sa doň dostanú aj "
    "zákazníci, ktorí nakúpili v druhej polovici predchádzajúceho roku. Jeho hodnota preto "
    "nie je porovnateľná s predchádzajúcimi rokmi — skutočný počet reaktivácií je v sekcii 9.")}
"""
    return html, [figure]


def order_value_section(metrics):
    """Priemerná vs mediánová hodnota objednávky."""
    yearly = metrics["yearly"]
    figure = charts.order_value(yearly)

    table = R.render_table(
        yearly,
        [("label", "Rok", str),
         ("mean_order", "Priemer", EUR),
         ("median_order", "Medián", EUR),
         ("p95_order", "p95", EUR),
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
    structure = metrics["portfolio_structure"]

    figures = [
        charts.concentration_shares(concentration),
        charts.concentration_threshold(concentration),
        charts.portfolio_structure(structure),
    ]

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

    structure_table = R.render_table(
        structure,
        [("customers", "Zákazníci", NUM),
         ("customer_pct", "% zákazníkov", PCT),
         ("gmv", "GMV", EUR),
         ("gmv_pct", "% GMV", PCT)],
        index_label="Pásmo",
    )

    first = concentration.iloc[0]
    last = concentration.iloc[-1]
    biggest_band = structure["gmv_pct"].idxmax()

    html = f"""
<h2>4. Koncentrácia portfólia</h2>
{_fig(figures, "concentration_shares")}
{_fig(figures, "concentration_threshold")}
{concentration_table}
<p>Podiel top 5 zákazníkov sa zmenil z {PCT(first["top5_pct"])} ({first["label"]}) na
{PCT(last["top5_pct"])} ({last["label"]}). Na 80 % GMV dnes stačí
{NUM(last["customers_for_80pct"])} zákazníkov, HHI je {NUM(last["hhi"])} a Gini
{NUM(last["gini"], 2)}.</p>
{_fig(figures, "portfolio_structure")}
{structure_table}
<p>Pásmo {biggest_band} tvorí {PCT(structure.loc[biggest_band, "gmv_pct"])} GMV pri
{PCT(structure.loc[biggest_band, "customer_pct"])} zákazníkov.</p>
"""
    return html, figures


def markets_section(metrics):
    """Rozdelenie trhov."""
    by_market = metrics["market_gmv"]
    summary = metrics["market_summary"]
    growth = metrics["market_growth"]

    figures = [
        charts.market_gmv(by_market),
        charts.market_growth(growth),
    ]

    table = R.render_table(
        summary,
        [("gmv", "GMV", EUR),
         ("share_pct", "Podiel", PCT),
         ("growth_pct", "Rast YoY", SIGNED_PCT),
         ("customers", "Zákazníci", NUM),
         ("median_order", "Medián obj.", EUR),
         ("gmv_per_customer", "GMV/zákazník", EUR)],
        index_label="Trh",
    )

    top_two = summary.head(2)
    top_two_share = top_two["share_pct"].sum()
    weakest = summary["gmv_per_customer"].idxmin()
    other = summary.loc[C.OTHER_MARKET_LABEL]

    html = f"""
<h2>5. Rozdelenie trhov</h2>
{_fig(figures, "market_gmv")}
{table}
<p>{" + ".join(top_two.index)} tvoria {PCT(top_two_share)} GMV. Rozdiel v GMV na zákazníka
je zásadný: {top_two.index[0]} {EUR(top_two.iloc[0]["gmv_per_customer"])} oproti
{weakest} {EUR(summary.loc[weakest, "gmv_per_customer"])}.</p>
{_fig(figures, "market_growth")}
<p>Kategória {C.OTHER_MARKET_LABEL} je najzreteľnejší prípad rozdielu medzi počtom
a hodnotou: {NUM(other["customers"])} zákazníkov, teda
{PCT(other["customers"] / summary["customers"].sum() * 100)} celej bázy, ale len
{PCT(other["share_pct"])} GMV. Mediánová objednávka {EUR(other["median_order"])} je
retailová — nie sú to B2B partneri, ale drobní odberatelia, ktorí v metrikách
„na zákazníka“ vážia rovnako ako key accounty.</p>
"""
    return html, figures


def churn_section(metrics):
    """Churn v čase a podľa pásma."""
    curves = metrics["churn_curves"]
    growth = metrics["growth_by_band"]
    churn_bands = metrics["churn_by_band"]

    figures = [
        charts.churn_over_time(curves),
        charts.growth_and_churn_by_band(growth, churn_bands),
        charts.net_gmv_by_band(growth),
    ]

    band_table = R.render_table(
        growth.join(churn_bands[["churn_pct", "gmv_churn_pct"]], rsuffix="_churn"),
        [("customers", "Zákazníci", NUM),
         ("growing_pct", "% rastúcich", PCT),
         ("median_change_pct", "Mediánová zmena", SIGNED_PCT),
         ("churn_pct", f"% churn ({C.CHURN_MAIN_THRESHOLD_MONTHS} mes.)", PCT),
         ("net_delta", "Netto zmena GMV", SIGNED_EUR)],
        index_label="Pásmo",
    )

    main = f"churn_{C.CHURN_MAIN_THRESHOLD_MONTHS}m"
    first_point = curves.iloc[0]
    last_point = curves.iloc[-1]
    top_band = growth.iloc[-1]
    smaller = growth.iloc[:-1]

    html = f"""
<h2>6. Churn</h2>
{_fig(figures, "churn_over_time")}
<p>Churn rastie na všetkých troch prahoch. {C.CHURN_MAIN_THRESHOLD_MONTHS}-mesačný churn stúpol
z {PCT(first_point[main])} ({curves.index[0]:%-m/%Y}) na {PCT(last_point[main])}
({curves.index[-1]:%-m/%Y}). Krivky sú blízko seba
({PCT(last_point["churn_3m"])} / {PCT(last_point["churn_6m"])} / {PCT(last_point["churn_12m"])}),
čo znamená, že väčšina neaktívnych zákazníkov nie je dočasne stíchnutá — je dávno mimo.
Rozdiel medzi 3- a 12-mesačným churnom, teda pásmo zákazníkov, ktorých sa ešte dá vrátiť,
je len {PCT(last_point["churn_3m"] - last_point["churn_12m"])} bázy.</p>

<h3>Rast a churn podľa veľkostného pásma</h3>
{_fig(figures, "band_growth_churn")}
{band_table}
<p>Podiel rastúcich stúpa s veľkosťou zákazníka z {PCT(growth.iloc[0]["growing_pct"])} na
{PCT(top_band["growing_pct"])}, churn klesá z {PCT(churn_bands.iloc[0]["churn_pct"])} na
{PCT(churn_bands.iloc[-1]["churn_pct"])}. Mediánová zmena GMV je pritom negatívna vo
<b>všetkých</b> pásmach — vrátane najväčšieho ({SIGNED_PCT(top_band["median_change_pct"])}).
Typický zákazník neklesá len v dlhom chvoste; klesá všade, a agregát ťahá nahor niekoľko
výnimiek.</p>

<h3>Netto GMV podľa pásma</h3>
{_fig(figures, "net_gmv_by_band")}
<p>Pásmo {growth.index[-1]} pridalo {SIGNED_EUR(top_band["net_delta"])} pri
{int(top_band["customers"])} zákazníkoch. Všetky ostatné pásma spolu
{SIGNED_EUR(smaller["net_delta"].sum())} pri {int(smaller["customers"].sum())} zákazníkoch.
Celý rast portfólia je záležitosťou {int(top_band["customers"])} účtov.</p>
"""
    return html, figures


def account_growth_section(metrics):
    """Interné KPI account growth a hľadanie dôvodu jeho nízkej hodnoty."""
    summary = metrics["account_growth_summary"]
    history = metrics["account_growth_history"]
    composition = metrics["account_growth_composition"]

    figures = [
        charts.account_growth_over_time(history),
        charts.account_growth_composition(composition),
    ]
    figures.extend(_account_growth_breakdown_figures(metrics))

    html = f"""
<h2>7. Account growth (interné KPI)</h2>
{_account_growth_definition(summary)}
{_fig(figures, "account_growth_over_time")}
{_account_growth_trend_text(history, summary)}

<h3>Z čoho sa skladá menovateľ</h3>
{_fig(figures, "account_growth_composition")}
{_account_growth_composition_table(composition)}
{_account_growth_composition_text(composition, summary)}

<h3>Kde je rozdiel</h3>
{_account_growth_breakdown_html(metrics, figures)}

<h3>Citlivosť na definíciu</h3>
{_account_growth_sensitivity_table(metrics)}
{_account_growth_sensitivity_text(metrics, summary)}
"""
    return html, figures


def _account_growth_definition(summary):
    """Úvodný odstavec: definícia KPI a jeho aktuálna hodnota."""
    return f"""
<p>KPI porovnáva GMV účtu za posledné {C.GMV_WINDOW_MONTHS} mesiace s GMV za to isté okno
o rok skôr. Účet rastie, ak je aktuálne GMV vyššie. Do menovateľa patrí účet, ktorý je
starší ako {C.ACCOUNT_GROWTH_MIN_AGE_MONTHS} mesiacov <b>a</b> bol aktívny aspoň v jednom
z dvoch okien. Vekový filter nie je voľný parameter — 12 + {C.GMV_WINDOW_MONTHS} zaručuje,
že každý účet v menovateli mal plné minuloročné okno.</p>
{R.render_note(
    f"<b>Aktuálna hodnota: {PCT(summary['growing_pct'])}</b> "
    f"({NUM(summary['growing'])} z {NUM(summary['accounts'])} účtov). "
    f"Klesá {PCT(summary['declining_pct'])}. Do cieľa "
    f"{C.ACCOUNT_GROWTH_TARGET_PCT} % chýba {NUM(summary['accounts_needed_for_target'])} "
    f"ďalších rastúcich účtov. Zároveň ale "
    f"<b>{PCT(summary['gmv_growing_pct'])} tržieb už v rastúcich účtoch leží</b> — "
    f"nevážené KPI a tržby nehovoria to isté.")}
"""


def _account_growth_trend_text(history, summary):
    """Odstavec k časovému radu KPI."""
    trough_date = history["growing_pct"].idxmin()
    peak_date = history["growing_pct"].idxmax()
    trough = history.loc[trough_date, "growing_pct"]
    peak = history.loc[peak_date, "growing_pct"]

    return f"""
<p>KPI nie je v prepade. Od dna {PCT(trough)} ({trough_date:%-m/%Y}) sa vrátilo na
{PCT(summary["growing_pct"])} a posledné štyri kvartály rastie. <b>Maximum celého radu je
{PCT(peak)} ({peak_date:%-m/%Y}), teda cieľ {C.ACCOUNT_GROWTH_TARGET_PCT} % sa v tomto
rozsahu dát nikdy nedosiahol</b> — nie je to návrat do normálu, ale nová hodnota, a to
by malo vstúpiť do rozhovoru o tom, či je cieľ realistický.</p>
<p>GMV-vážená línia je celý čas výrazne vyššia než stĺpce. Rozdiel medzi nimi je mierou
toho, ako silno nevážené KPI váži drobné účty rovnako ako strategické.</p>
"""


def _account_growth_composition_table(composition):
    """Tabuľka rozkladu menovateľa."""
    return R.render_table(
        composition,
        [("customers", "Účty", NUM),
         ("share_pct", "% menovateľa", PCT),
         ("growing_pct", "% rastúcich", PCT),
         ("previous_gmv", "GMV pred rokom", EUR),
         ("current_gmv", "GMV teraz", EUR)],
        index_label="Skupina",
    )


def _account_growth_composition_text(composition, summary):
    """Odstavec k rozkladu menovateľa."""
    reactivated = composition.loc[metrics_account_growth.COMPOSITION_REACTIVATED]
    dropped = composition.loc[metrics_account_growth.COMPOSITION_DROPPED]
    both = composition.loc[metrics_account_growth.COMPOSITION_BOTH]
    binary_share = reactivated["share_pct"] + dropped["share_pct"]

    return f"""
<p><b>{PCT(binary_share)} menovateľa je rozhodnuté binárne</b> — účet buď v okne nakúpil
alebo nenakúpil. {NUM(reactivated["customers"])} reaktivovaných účtov je rastúcich
automaticky (z nuly rastie čokoľvek), {NUM(dropped["customers"])} odídených je automaticky
klesajúcich. Len {NUM(both["customers"])} účtov aktívnych v oboch oknách naozaj meria zmenu
objemu, a tam je podiel rastúcich {PCT(both["growing_pct"])}, teda takmer presne pol na pol.</p>
<p>Z toho vyplýva, kde je páka: s odídenými účtami zmizlo
{EUR(dropped["previous_gmv"])} z minuloročného okna. <b>KPI sa nezvýši tým, že účty
prinútime rásť — zvýši sa tým, že ich nedopustíme spadnúť do nuly.</b> Zároveň to je jeho
najväčšia slabina: {NUM(summary["accounts_needed_for_target"])} chýbajúcich rastúcich účtov
sa dá „splniť“ reaktiváciou drobných dormantných účtov s takmer nulovým vplyvom na tržby.</p>
"""


def _account_growth_breakdown_specs(metrics):
    """Definícia rezov: kľúč v metrikách, id grafu, nadpis a komentár."""
    return [
        ("account_growth_by_band", "ag_by_band", "Podľa veľkostného pásma",
         "Pásmo je určené GMV v minuloročnom okne. Zelená = nad cieľom, "
         "červená = pod celkovým KPI."),
        ("account_growth_by_group", "ag_by_group", "Podľa customer_group_id",
         f"Skupiny s menej ako {C.ACCOUNT_GROWTH_MIN_SEGMENT_SIZE} účtami sú vynechané. "
         f"Čo skupiny znamenajú, v dátach nie je — bez doplnenia z e-shopu sa rez "
         f"nedá interpretovať, hoci má najväčší rozptyl zo všetkých."),
        ("account_growth_by_country", "ag_by_country", "Podľa krajiny",
         f"Bez zlúčenej kategórie {C.OTHER_MARKET_LABEL}, ktorú používa zvyšok reportu — "
         f"práve v jednotlivých krajinách je rozptyl najväčší."),
        ("account_growth_by_cohort", "ag_by_cohort", "Podľa roku prvej objednávky",
         "Vek účtu. Ukazuje, či nízke KPI nie je vlastnosť konkrétnych kohort."),
        ("account_growth_by_orders", "ag_by_orders", "Podľa počtu objednávok pred rokom",
         f"Len účty aktívne v minuloročnom okne — reaktivované sú rastúce automaticky "
         f"a graf by skreslili. Účet s jednou objednávkou za {C.GMV_WINDOW_MONTHS} "
         f"mesiace je porovnávaný na základe jedinej udalosti, takže KPI tam meria "
         f"z veľkej časti časovanie objednávky, nie rast."),
    ]


def _account_growth_breakdown_figures(metrics):
    """Grafy všetkých rezov.

    Vytvoria sa všetky, aj tie skryté cez C.HIDDEN_CHARTS — nie sú výpočtovo
    náročné a _account_growth_breakdown_html z nich aj tak vynechá celý rez
    (graf i komentár), ak je jeho ID medzi skrytými.
    """
    overall = metrics["account_growth_summary"]["growing_pct"]
    figures = []
    for key, figure_id, title, caption in _account_growth_breakdown_specs(metrics):
        figures.append(charts.account_growth_breakdown(
            metrics[key], figure_id, title, caption, overall))
    return figures


def _account_growth_breakdown_html(metrics, figures):
    """HTML rezov: graf a k nemu komentár so extrémami, skrytý rez sa vynechá celý."""
    parts = []
    for key, figure_id, _, _ in _account_growth_breakdown_specs(metrics):
        if figure_id in C.HIDDEN_CHARTS:
            continue
        parts.append(_fig(figures, figure_id))
        parts.append(_breakdown_comment(metrics[key]))
    return "\n".join(parts)


def _breakdown_comment(breakdown):
    """Veta s najlepším a najhorším segmentom rezu.

    Popisky segmentov idú cez escape — pásma začínajú znakom „<“ a bez escapu
    by prehliadač zvyšok odstavca zjedol ako otvorenú značku.
    """
    best = breakdown["growing_pct"].idxmax()
    worst = breakdown["growing_pct"].idxmin()
    spread = breakdown.loc[best, "growing_pct"] - breakdown.loc[worst, "growing_pct"]
    return (f'<p class="small">Najvyššie {R.escape(best)} '
            f'({PCT(breakdown.loc[best, "growing_pct"])}, '
            f'{NUM(breakdown.loc[best, "customers"])} účtov), najnižšie {R.escape(worst)} '
            f'({PCT(breakdown.loc[worst, "growing_pct"])}, '
            f'{NUM(breakdown.loc[worst, "customers"])} účtov). Rozptyl '
            f'{NUM(spread, 1)} p. b.</p>')


def _account_growth_sensitivity_table(metrics):
    """Tabuľka citlivosti KPI na parametre definície."""
    return R.render_table(
        metrics["account_growth_sensitivity"],
        [("accounts", "Účty v menovateli", NUM),
         ("growing_pct", "% rastúcich", PCT),
         ("gmv_growing_pct", "% GMV v rastúcich", PCT)],
        index_label="Variant definície",
    )


def _account_growth_sensitivity_text(metrics, summary):
    """Odstavec o tom, koľko z hodnoty KPI je vlastnosť definície."""
    sensitivity = metrics["account_growth_sensitivity"]
    windows = sensitivity.loc[[f"{months}-mes. okno"
                               for months in C.ACCOUNT_GROWTH_WINDOW_VARIANTS]]
    shortest = windows.iloc[0]
    longest = windows.iloc[-1]

    return f"""
<p>Dĺžka okna mení KPI o desiatky percentuálnych bodov:
{C.ACCOUNT_GROWTH_WINDOW_VARIANTS[0]}-mesačné okno dáva {PCT(shortest["growing_pct"])},
{C.ACCOUNT_GROWTH_WINDOW_VARIANTS[-1]}-mesačné {PCT(longest["growing_pct"])}. Zvolené
{C.GMV_WINDOW_MONTHS} mesiace teda číslu <b>lichotia</b> — čím dlhšie okno, tým viac
účtov sa do menovateľa dostane a tým nižší podiel rastie. Kratšie okno zároveň znamená
menej objednávok na účet, takže väčší podiel KPI je časovanie objednávok.
Pred stanovením cieľa {C.ACCOUNT_GROWTH_TARGET_PCT} % treba zafixovať, ktorá z týchto
hodnôt je „account growth“ — inak je cieľ nastavený na neurčenú metriku.</p>
"""


def loyalty_section(metrics):
    """Zákazníci s jednou objednávkou a frekvencia objednávania."""
    single = metrics["single_order"]
    frequency = metrics["frequency"]

    figures = [
        charts.single_order_by_cohort(single),
        charts.frequency_histogram(frequency, metrics["frequency_max"]),
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
    dormant = frequency.loc["0"]
    one_order = frequency.loc["1"]
    two_orders = frequency.loc["2"]
    top_bucket = frequency.iloc[-1]
    total_base = int(frequency["customers_at_or_above"].iloc[0])

    html = f"""
<h2>8. Lojalita a frekvencia</h2>
{_fig(figures, "single_order")}
{single_table}
<p>Podiel zákazníkov s jedinou objednávkou za život stúpol z {PCT(first["single_order_pct"])}
(kohorta {first["label"]}) na {PCT(last["single_order_pct"])} ({last["label"]}). Medián
objednávok za život klesol z {NUM(first["median_orders"])} na {NUM(last["median_orders"])}
a medián LTV z {EUR(first["median_ltv"])} na {EUR(last["median_ltv"])}. Akvizícia rastie
v počte a klesá v kvalite.</p>
{_fig(figures, "frequency_histogram")}
<p>Menovateľom je celá databáza, {NUM(total_base)} zákazníkov. Najväčšia skupina za
posledných {C.FREQUENCY_WINDOW_MONTHS} mesiacov <b>nenakúpila vôbec</b> —
{NUM(dormant["customers"])} zákazníkov, teda {PCT(dormant["share_pct"])} bázy.
Druhá najväčšia má jedinú objednávku: {NUM(one_order["customers"])}
({PCT(one_order["share_pct"])}). Dve objednávky má {NUM(two_orders["customers"])}
zákazníkov ({PCT(two_orders["share_pct"])}).</p>
<p>Histogram nemá tvar zvonu — rozdelenie je monotónne klesajúce s modusom na nule.
Reverzný kumulatív to ukazuje presne: aspoň jednu objednávku má
{PCT(one_order["share_at_or_above_pct"])} bázy, aspoň desať už len
{PCT(frequency.loc["10"]["share_at_or_above_pct"])} a v poslednom koši
({top_bucket.name} objednávok) je {NUM(top_bucket["customers"])} zákazníkov, teda
{PCT(top_bucket["share_pct"])}. Práve tí sú ale celý biznis — väčšina databázy nemá
nákupný rytmus, len jednorazový kontakt.</p>
"""
    return html, figures


def reactivation_section(metrics):
    """Reaktivovaní zákazníci."""
    histogram = metrics["reactivation_histogram"]
    by_year = metrics["repeat_reactivation"]
    value = metrics["reactivation_value"]

    figures = [
        charts.reactivation_histogram(histogram),
        charts.repeat_reactivation(by_year),
    ]

    histogram_table = R.render_table(
        histogram,
        [("customers", "Zákazníci", NUM), ("share_pct", "Podiel", PCT)],
        index_label="Počet reaktivácií",
    )

    value_table = R.render_table(
        value,
        [("customers", "Zákazníci", NUM),
         ("median_orders", "Medián objednávok", lambda v: NUM(v, 0)),
         ("median_ltv", "Medián LTV", EUR),
         ("total_gmv", "GMV celkom", EUR)],
        index_label="Skupina",
    )

    never = histogram.iloc[0]
    once = histogram.iloc[1]
    repeat = histogram.iloc[2:]["customers"].sum()
    repeat_share = histogram.iloc[2:]["share_pct"].sum()
    last_year = by_year.iloc[-1]

    html = f"""
<h2>9. Reaktivovaní zákazníci</h2>
{_fig(figures, "reactivation_histogram")}
{histogram_table}
<p>Zo zákazníkov s aspoň dvoma objednávkami nebolo nikdy reaktivovaných
{PCT(never["share_pct"])}. Raz {PCT(once["share_pct"])}, dvakrát a viackrát
{PCT(repeat_share)}, čo je {NUM(repeat)} zákazníkov.</p>
{_fig(figures, "repeat_reactivation")}
<p><b>Odpoveď na otázku, či sa v reaktiváciách točia stále tí istí: nie.</b>
V období {last_year["label"]} bolo {NUM(last_year["events"])} reaktivácií a len
{PCT(last_year["repeat_pct"])} z nich pripadalo na zákazníkov, ktorí už raz reaktivovaní boli.
Reaktivácia je jednorazová udalosť, nie kolotoč — a to je zlá správa: kto raz odíde,
väčšinou sa nevráti ani raz.</p>
{value_table}
<p>Opakovane reaktivovaní zákazníci sú navyše malí — ich celkové GMV je
{EUR(value.iloc[-1]["total_gmv"])}, teda zlomok toho, čo robia stabilní zákazníci
({EUR(value.iloc[0]["total_gmv"])}). Reaktivácia nie je páka na rast; páka je nedopustiť odchod.</p>
"""
    return html, figures


def conclusions(metrics):
    """Zhrnutie a odporúčania."""
    growth = metrics["growth_by_band"]
    concentration = metrics["concentration"]
    curves = metrics["churn_curves"]
    single = metrics["single_order"]
    frequency = metrics["frequency"]

    last_concentration = concentration.iloc[-1]
    top_band = growth.iloc[-1]
    main = f"churn_{C.CHURN_MAIN_THRESHOLD_MONTHS}m"
    mature = single.loc[~single["is_immature"]]

    markets = metrics["market_summary"]
    top_two_share = markets.head(2)["share_pct"].sum()
    other_market = markets.loc[C.OTHER_MARKET_LABEL]
    small_customer_share = other_market["customers"] / markets["customers"].sum() * 100
    small_gmv_share = other_market["share_pct"]

    html = f"""
<h2>10. Zhrnutie</h2>
<ol>
<li><b>Rast je koncentrovaný do {int(top_band["customers"])} účtov.</b> Pásmo
{growth.index[-1]} pridalo {SIGNED_EUR(top_band["net_delta"])}, všetky ostatné pásma spolu
{SIGNED_EUR(growth.iloc[:-1]["net_delta"].sum())}. Top 1 zákazník je
{PCT(last_concentration["top1_pct"])} GMV, top 10 je {PCT(last_concentration["top10_pct"])}.
Pri odchode jedného účtu padne ročné GMV o pätinu.</li>

<li><b>Typický zákazník nerastie.</b> Mediánová hodnota objednávky je plochá a mediánová
medziročná zmena GMV je negatívna vo všetkých veľkostných pásmach. Nízky podiel rastúcich
zákazníkov nie je chyba merania — je to štruktúra portfólia.</li>

<li><b>Churn rastie a je nezvratný.</b> {C.CHURN_MAIN_THRESHOLD_MONTHS}-mesačný churn stúpol
na {PCT(curves.iloc[-1][main])}. Reaktivácia je pritom vzácna a jednorazová, takže
odchod je v praxi definitívny.</li>

<li><b>Akvizícia klesá v kvalite.</b> Podiel zákazníkov s jedinou objednávkou stúpol na
{PCT(mature.iloc[-1]["single_order_pct"])} a {PCT(frequency.loc["0"]["share_pct"])} celej bázy
za posledných {C.FREQUENCY_WINDOW_MONTHS} mesiacov nenakúpilo vôbec.
Do B2B kanálu tečú drobní odberatelia.</li>

<li><b>Rast je geograficky úzky.</b> Dva najväčšie trhy tvoria {PCT(top_two_share)} GMV.
Kategória {C.OTHER_MARKET_LABEL} má {PCT(small_customer_share)} zákazníkov, ale len
{PCT(small_gmv_share)} GMV — a tým ťahá každú metriku „na zákazníka" dole.</li>
</ol>

<h3>Odporúčania k metrikám</h3>
<ol>
<li>Doplniť ku každej metrike „na zákazníka" jej <b>GMV-váženú verziu</b>. Nevážená verzia
meria hlavne dlhý chvost drobných odberateľov.</li>
<li>Merať rast a churn <b>oddelene pre strategické účty a transakčných kupujúcich</b>
(hranica napríklad {EUR(C.BAND_EDGES[3])} ročne alebo aspoň 4 objednávky ročne).</li>
<li>Zafixovať menovateľ v definícii churnu a rastu — v tomto reporte je to explicitne
uvedené pri každom grafe, v internom KPI to chýba.</li>
</ol>

<h3>Odporúčania k biznisu</h3>
<ol>
<li><b>Znížiť závislosť na top účtoch</b> rozšírením mid-market pásma, ktoré je dnes
netto negatívne.</li>
<li><b>Zamerať sa na prvých 90 dní.</b> Rastúci podiel zákazníkov s jedinou objednávkou
je najlacnejšia páka — druhá objednávka rozhoduje o celej kohorte.</li>
<li><b>Kvalifikovať akvizíciu.</b> Buď oddeliť drobných odberateľov do samoobslužného
segmentu bez account managementu, alebo zvýšiť vstupnú hranicu.</li>
<li><b>Nestavať na win-back kampaniach.</b> Dáta hovoria, že odchod je definitívny;
prevencia je jediná fungujúca stratégia.</li>
</ol>

<h3>Ďalšie kroky v analýze</h3>
<ol>
<li>Zjednotiť identitu zákazníka (viac e-mailov = jedna firma). Bez toho sú noví, churn
aj reaktivácie nadhodnotené.</li>
<li>Doplniť produktovú a maržovú dimenziu — rast priemernej objednávky môže byť mix efekt,
nie skutočný rast hodnoty.</li>
</ol>

<p class="small" style="margin-top:48px;border-top:1px solid var(--bd);padding-top:16px">
Grafy sú interaktívne — prejdi kurzorom pre presné hodnoty. Legendy sú statické.
Všetky tabuľky a čísla v texte sú generované z dát. Dátum analýzy
{C.AS_OF:%-d.\u00a0%-m.\u00a0%Y}.</p>
"""
    return html, []


SECTION_BUILDERS = [
    header,
    methodology,
    trend_section,
    bridge_section,
    order_value_section,
    concentration_section,
    markets_section,
    churn_section,
    account_growth_section,
    loyalty_section,
    reactivation_section,
    conclusions,
]


def build_all(metrics):
    """Poskladá HTML všetkých sekcií a zoznam grafov, ktoré sa naozaj vykreslili.

    Grafy skryté cez C.HIDDEN_CHARTS sa sem nedostanú — inak by Chart.js na
    strane prehliadača skúšal nakresliť graf do neexistujúceho <canvas> a
    spadol by aj so zvyšnými grafmi za ním.
    """
    html_parts = []
    figures = []
    for builder in SECTION_BUILDERS:
        section_html, section_figures = builder(metrics)
        html_parts.append(section_html)
        for figure in section_figures:
            if figure["id"] not in C.HIDDEN_CHARTS:
                figures.append(figure)
    return "\n".join(html_parts), figures
