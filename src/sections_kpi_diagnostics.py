# -*- coding: utf-8 -*-
"""Sekcie diagnostického reportu KPI account growth.

Rovnaká konvencia ako sections.py: každá funkcia vráti HTML jednej sekcie a
zoznam grafov v nej, čísla v texte sa vkladajú z metrík. Hlavný report tento
modul nepoužíva.
"""

from src import constants as C
import charts
import metrics_kpi_diagnostics as MD
import report as R

EUR = R.format_eur
PCT = R.format_pct
NUM = R.format_number
SIGNED_EUR = R.format_signed_eur
SIGNED_PCT = R.format_signed_pct


def _fig(figures, figure_id):
    """Vykreslí graf podľa jeho ID, alebo nič, ak je v C.HIDDEN_CHARTS."""
    if figure_id in C.HIDDEN_CHARTS:
        return ""
    for figure in figures:
        if figure["id"] == figure_id:
            return R.render_figure(figure)
    raise KeyError(f"graf s id '{figure_id}' nie je medzi figures")


# ── hlavička ──────────────────────────────────────────────────────────────────
def header(metrics):
    """Nadpis, prehľadové karty a hlavná téza."""
    summary = metrics["diag_summary"]
    quality = metrics["quality"]

    cards = [
        ("Account growth", PCT(summary["growing_pct"], 1)),
        ("Cieľ", f"{C.ACCOUNT_GROWTH_TARGET_PCT} %"),
        ("GMV v rastúcich účtoch", PCT(summary["gmv_growing_pct"], 0)),
        ("Šum metriky", f"±{NUM(summary['noise_sd'], 1)} p. b."),
    ]

    html = f"""
<h1>Account growth — čo drží KPI pod cieľom</h1>
<p class="lead">Diagnostika interného KPI · okno {C.GMV_WINDOW_MONTHS} mesiace medziročne
k {C.AS_OF:%-d. %-m. %Y} · menovateľ {NUM(summary["accounts"])} účtov ·
zdroj <code>{C.INPUT_XLSX}</code> · {NUM(quality["orders"])} objednávok</p>
{R.render_kpi_cards(cards)}
{R.render_note(
    f"<b>Téza.</b> Z odstupu od cieľa nie je všetko biznis. Časť je vlastnosť "
    f"definície metriky — {PCT(summary['thin_pct'], 0)} menovateľa má v oboch oknách "
    f"najviac {C.KPI_DIAG_THIN_ORDERS} objednávky, takže KPI z veľkej časti meria "
    f"časovanie objednávok. A časť cieľa je aritmeticky nedosiahnuteľná retenciou, "
    f"o čom je sekcia 5.")}
"""
    return html, []


# ── 1. frekvencia ─────────────────────────────────────────────────────────────
def frequency_section(metrics):
    """Rast účtu ako funkcia počtu objednávok."""
    frequency = metrics["diag_frequency"]
    summary = metrics["diag_summary"]

    figures = [charts.kpi_frequency_effect(frequency, summary["growing_pct"])]

    table = R.render_table(
        frequency,
        [("customers", "Účty", NUM),
         ("growing", "Z toho rastúcich", NUM),
         ("growing_pct", "% rastúcich", PCT),
         ("net_delta", "Netto zmena GMV", SIGNED_EUR)],
        index_label="Zmena počtu objednávok",
    )

    more = frequency.loc[MD.FREQUENCY_MORE]
    same = frequency.loc[MD.FREQUENCY_SAME]
    fewer = frequency.loc[MD.FREQUENCY_FEWER]

    html = f"""
<h2>1. Rast účtu je o počte objednávok, nie o ich veľkosti</h2>
{_fig(figures, "kpi_frequency")}
{table}
<p>Vzťah je takmer deterministický. Účet, ktorý objedná rovnaký počet krát, je
coin flip ({PCT(same["growing_pct"])}). Účet, ktorý objedná menejkrát, je odpísaný
({PCT(fewer["growing_pct"])}). Účet, ktorý objedná viackrát, rastie takmer vždy
({PCT(more["growing_pct"])}).</p>
<p>Pri {C.GMV_WINDOW_MONTHS}-mesačnom okne je „o jednu objednávku menej“ bežná vec —
{PCT(summary["thin_pct"], 0)} menovateľa má v oboch oknách najviac
{C.KPI_DIAG_THIN_ORDERS} objednávky. <b>Frekvencia je zároveň najlepší predstihový
indikátor tohto KPI</b>: dá sa sledovať týždenne, kým samotné KPI sa dá zmerať až
s ročným odstupom.</p>
"""
    return html, figures


# ── 2. živé účty mimo okna ────────────────────────────────────────────────────
def dropped_section(metrics):
    """Padnuté účty: koľko z nich je naozaj mŕtvych."""
    recency = metrics["diag_dropped_recency"]
    effect = metrics["diag_alive_effect"]
    summary = metrics["diag_summary"]

    figures = [
        charts.kpi_dropped_recency(recency),
        charts.kpi_alive_effect(effect),
    ]

    table = R.render_table(
        recency,
        [("customers", "Účty", NUM),
         ("previous_gmv", "GMV pred rokom", EUR)],
        index_label="Posledná objednávka",
    )

    alive = recency.loc[recency["is_alive"], "customers"].sum()
    dead = recency.loc[~recency["is_alive"], "customers"].sum()
    reported = effect["growing_pct"].iloc[0]
    adjusted = effect["growing_pct"].iloc[1]

    html = f"""
<h2>2. Väčšina „padnutých“ účtov je živá</h2>
{_fig(figures, "kpi_dropped_recency")}
{table}
<p>Z {NUM(summary["dropped"])} účtov s nulovým GMV v aktuálnom okne nakúpilo
<b>{NUM(alive)}</b> po skončení minuloročného okna. Nie sú churnuté — len neobjednali
práve v porovnávanom okne. Preukázateľne mŕtvych je {NUM(dead)}.</p>
{_fig(figures, "kpi_alive_effect")}
<p>Keď tie živé účty z metriky vynechám, KPI stúpne z {PCT(reported)} na
{PCT(adjusted)}, teda o {NUM(adjusted - reported, 1)} p. b. To nie je zlepšenie
biznisu, je to <b>meranie toho, koľko z odstupu od cieľa vyrába samotné okno</b>.</p>
"""
    return html, figures


# ── 3. šum ────────────────────────────────────────────────────────────────────
def noise_section(metrics):
    """Koľko sa KPI hýbe bez toho, aby sa hýbal biznis."""
    noise = metrics["diag_noise"]
    summary = metrics["diag_summary"]

    figures = [charts.kpi_monthly_noise(noise)]

    html = f"""
<h2>3. Šum: to isté KPI merané o mesiac inak</h2>
{_fig(figures, "kpi_noise")}
<p>Za posledných {C.KPI_DIAG_NOISE_MONTHS} mesiacov sa KPI pohybovalo medzi
{PCT(summary["noise_min"])} a {PCT(summary["noise_max"])} pri smerodajnej odchýlke
{NUM(summary["noise_sd"], 1)} p. b. <b>Rozdiel dvoch susedných meraní v tomto
rozpätí nie je signál.</b> Pri stanovovaní cieľa a pri jeho vyhodnocovaní treba
s týmto pásmom počítať, inak sa bude reagovať na šum.</p>
"""
    return html, figures


# ── 4. okno vs populácia ──────────────────────────────────────────────────────
def window_section(metrics):
    """Čo naozaj mení dĺžka okna."""
    variants = metrics["diag_window"]
    summary = metrics["diag_summary"]

    figures = [charts.kpi_window_vs_population(variants, summary["growing_pct"])]

    table = R.render_table(
        variants,
        [("customers", "Menovateľ", NUM),
         ("growing_pct", "% rastúcich", PCT)],
        index_label="Variant",
    )

    short = variants["growing_pct"].iloc[0]
    long_same = variants["growing_pct"].iloc[1]
    long_own = variants["growing_pct"].iloc[2]
    extra = variants.iloc[3]

    html = f"""
<h2>4. Dĺžka okna nie je voľba merania, ale voľba populácie</h2>
{_fig(figures, "kpi_window_population")}
{table}
<p>Intuícia hovorí, že dlhšie okno odstráni artefakt zo sekcie 2. Odstráni —
ale číslo tým nestúpne. Na tých istých účtoch dá {C.KPI_DIAG_LONG_WINDOW_MONTHS}-mesačné
okno {PCT(long_same)} namiesto {PCT(short)}, teda rozdiel
{NUM(long_same - short, 1)} p. b. Celý prepad na {PCT(long_own)} robí
{NUM(extra["customers"])} účtov, ktoré krátke okno do menovateľa vôbec nevpustí —
a tie rastú len na {PCT(extra["growing_pct"])}.</p>
{R.render_note(
    f"<b>Neexistuje okno, ktoré zároveň zníži šum a zvýši číslo.</b> Kratšie okno "
    f"zamlčí slabé účty, dlhšie ich vpustí. Číslo je nízke preto, že báza je plochá — "
    f"nie preto, že okno je krátke. Pred stanovením cieľa "
    f"{C.ACCOUNT_GROWTH_TARGET_PCT} % treba zafixovať, ktorá z hodnôt v tabuľke je "
    f"„account growth“.")}
"""
    return html, figures


# ── 5. distribúcia a aritmetická stena ────────────────────────────────────────
def wall_section(metrics):
    """Prečo je cieľ nedosiahnuteľný samotnou retenciou."""
    histogram = metrics["diag_change_histogram"]
    wall = metrics["diag_wall"]
    paths = metrics["diag_paths"]
    summary = metrics["diag_summary"]

    figures = [
        charts.kpi_change_histogram(histogram),
        charts.kpi_retention_wall(wall, summary["growing_pct"]),
    ]

    paths_table = R.render_table(
        paths,
        [("needed", "Potrebné", lambda v: NUM(v, 0)),
         ("available", "Dostupné", lambda v: NUM(v, 0)),
         ("unit", "Jednotka", str),
         ("feasible", "Stačí materiál?", _yes_no)],
        index_label="Samostatná cesta k cieľu",
    )

    today = wall["growing_pct"].iloc[0]
    zero_churn = wall["growing_pct"].iloc[1]

    html = f"""
<h2>5. Aritmetická stena: cieľ sa retenciou dosiahnuť nedá</h2>
{_fig(figures, "kpi_change_histogram")}
<p>Distribúcia je takmer symetrická okolo nuly, medián
{SIGNED_PCT(histogram["median_change_pct"].iloc[0])}. Preto je podiel rastúcich medzi
aktívnymi účtami {PCT(summary["active_growing_pct"])} — typický aktívny účet je plochý
a o jeho zaradení rozhoduje maličkosť.</p>
{_fig(figures, "kpi_retention_wall")}
<p>Ak by ani jeden účet nespadol do nuly a všetky by sa chovali ako priemerný aktívny
účet, KPI by bolo {PCT(zero_churn)}, nie {C.ACCOUNT_GROWTH_TARGET_PCT} %. Dôvod je
subtílny: <b>zachránený pád sa nestane rastúcim účtom automaticky</b> — presunie sa
do skupiny, kde má {PCT(summary["active_growing_pct"], 0)} šancu na rast.</p>
{paths_table}
<p>Reaktivácia dormantných účtov je jediná samostatne funkčná cesta, lebo dormantný
účet sa po jednej objednávke stane rastúcim automaticky. Kandidátov je
{NUM(summary["dormant"])}. Ich medián životného GMV je však
{EUR(summary["dormant_median_ltv"])}, takže je to
<b>cesta, ktorá cieľ splní a tržbám nedá takmer nič</b>.</p>
"""
    return html, figures


def _yes_no(value):
    """Áno/nie pre stĺpec s realizovateľnosťou cesty."""
    if bool(value):
        return "áno"
    return "nie"


# ── 6. rebrík pák ─────────────────────────────────────────────────────────────
def ladder_section(metrics):
    """Kombinácia pák, ktorá cieľ dosiahne."""
    ladder = metrics["diag_ladder"]
    summary = metrics["diag_summary"]

    figures = [charts.kpi_lever_ladder(ladder)]

    table = R.render_table(
        ladder,
        [("gain", "Prírastok rastúcich účtov", lambda v: NUM(v, 0)),
         ("growing_pct", "KPI po kroku", PCT)],
        index_label="Krok",
    )

    reactivations = int(ladder["reactivations"].iloc[0])
    saved = int(ladder["saved"].iloc[0])
    fewer = int(ladder["fewer_accounts"].iloc[0])
    addressable = summary["fewer_delta"] - summary["dropped_gmv"]

    html = f"""
<h2>6. Kombinácia, ktorá cieľ dosiahne</h2>
{_fig(figures, "kpi_lever_ladder")}
{table}
<p>Udržať frekvenciu u {NUM(fewer)} účtov, ktoré objednali menejkrát, a zachrániť
polovicu pádov do nuly ({NUM(saved)} účtov) posunie KPI natoľko, že na cieľ stačí
{NUM(reactivations)} reaktivácií namiesto niekoľkých stoviek.
<b>Poradie je jednoznačné: frekvencia → prevencia pádov → reaktivácia ako doplnok,
nie ako stratégia.</b></p>
{R.render_note(
    f"Prvé dva kroky sa vyplatia aj keby žiadne KPI neexistovalo. "
    f"{NUM(fewer)} účtov s nižšou frekvenciou stratilo "
    f"{SIGNED_EUR(summary['fewer_delta'])}, {NUM(summary['dropped'])} pádov do nuly "
    f"{SIGNED_EUR(-summary['dropped_gmv'])}. Spolu <b>{SIGNED_EUR(addressable)}</b> "
    f"medziročne.")}
"""
    return html, figures


# ── 7. odporúčania ────────────────────────────────────────────────────────────
def recommendations(metrics):
    """Čo z toho vyplýva pre metriku aj pre biznis."""
    summary = metrics["diag_summary"]
    variants = metrics["diag_window"]

    html = f"""
<h2>7. Odporúčania</h2>
<h3>K metrike</h3>
<ol>
<li><b>Zafixovať definíciu pred cieľom.</b> Tá istá báza dá
{PCT(variants["growing_pct"].iloc[0])} pri {C.GMV_WINDOW_MONTHS}-mesačnom okne a
{PCT(variants["growing_pct"].iloc[2])} pri {C.KPI_DIAG_LONG_WINDOW_MONTHS}-mesačnom.
Cieľ {C.ACCOUNT_GROWTH_TARGET_PCT} % dnes visí na neurčenej metrike.</li>
<li><b>Nastaviť cieľ na tú časť, ktorá je riadená</b> — napríklad na podiel rastúcich
medzi účtami aktívnymi v oboch oknách (dnes {PCT(summary["active_growing_pct"])}).
Tam je {C.ACCOUNT_GROWTH_TARGET_PCT} % ambiciózne, ale dosiahnuteľné, a nedá sa to
splniť reaktivačnou kampaňou.</li>
<li><b>Vykazovať vedľa neváženého KPI aj GMV-vážený variant.</b> Dnes je
{PCT(summary["gmv_growing_pct"])} tržieb v rastúcich účtoch oproti
{PCT(summary["growing_pct"])} účtov — nevážené KPI a tržby nehovoria to isté.</li>
<li><b>Uvádzať pásmo šumu.</b> ±{NUM(summary["noise_sd"], 1)} p. b. znamená, že na
zmenu do 2 p. b. sa nemá reagovať.</li>
</ol>

<h3>K biznisu</h3>
<ol>
<li><b>Sledovať počet objednávok na účet ako predstihový indikátor.</b> Je to
najsilnejší vzťah v dátach a jediný, ktorý sa dá riadiť v priebehu kvartálu.</li>
<li><b>Zamerať prevenciu na účty, ktoré strácajú frekvenciu</b>, nie na tie, ktoré
už spadli do nuly. Do nuly padá účet až po tom, čo mu najprv klesne frekvencia.</li>
<li><b>Reaktivačné kampane nepoužívať na plnenie KPI.</b> Fungujú na číslo, nie na
tržby — medián životného GMV dormantného účtu je
{EUR(summary["dormant_median_ltv"])}.</li>
</ol>

<p class="small" style="margin-top:48px;border-top:1px solid var(--bd);padding-top:16px">
Grafy sú interaktívne — prejdi kurzorom pre presné hodnoty. Všetky tabuľky a čísla
v texte sú generované z dát. Dátum analýzy {C.AS_OF:%-d. %-m. %Y}.</p>
"""
    return html, []


SECTION_BUILDERS = [
    header,
    frequency_section,
    dropped_section,
    noise_section,
    window_section,
    wall_section,
    ladder_section,
    recommendations,
]


def build_all(metrics):
    """Poskladá HTML všetkých sekcií a zoznam grafov."""
    html_parts = []
    figures = []
    for builder in SECTION_BUILDERS:
        section_html, section_figures = builder(metrics)
        html_parts.append(section_html)
        figures.extend(section_figures)
    return "\n".join(html_parts), figures
