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
        ("Cieľ", f"{C.ACCOUNT_GROWTH_TARGET_PCT} %"),
        ("Rastúcich medzi účtami aktívnymi v okne", PCT(summary["in_window_growing_pct"], 1)),
        ("GMV v rastúcich účtoch", PCT(summary["gmv_growing_pct"], 0)),
    ]

    html = f"""
<h1>Account growth — čo drží KPI pod cieľom</h1>
<p class="lead">Diagnostika interného KPI · okno {C.GMV_WINDOW_MONTHS} mesiace medziročne
k {C.AS_OF:%-d. %-m. %Y} · menovateľ {NUM(summary["accounts"])} účtov ·
zdroj <code>{C.INPUT_XLSX}</code> · {NUM(quality["orders"])} objednávok</p>
{R.render_kpi_cards(cards)}
{R.render_note(
    f"<b>Téza.</b> Medzi účtami, ktoré v okne nakúpili, je KPI na "
    f"{PCT(summary['in_window_growing_pct'])} — takmer na cieli. Celkových "
    f"{PCT(summary['growing_pct'])} vzniká tým, že sa k nim priráta "
    f"{NUM(summary['cannot_grow'])} účtov, ktoré v okne nenakúpili a rastúce teda "
    f"nemôžu byť z definície. Otázka preto nie je „prečo účty nerastú“, ale "
    f"<b>„prečo {NUM(summary['cannot_grow'])} účtov v okne nenakúpilo“</b>.")}
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


# ── 2. kedy účty naposledy nakúpili ───────────────────────────────────────────
def activity_section(metrics):
    """Rozdelenie menovateľa a scenár pravidelného objednávania."""
    activity = metrics["diag_activity_split"]
    scenario = metrics["diag_regular_scenario"]

    figures = [
        charts.kpi_activity_split(activity),
        charts.kpi_regular_ordering(scenario),
    ]

    table = R.render_table(
        activity,
        [("customers", "Účty", NUM),
         ("share_pct", "% menovateľa", PCT),
         ("growing_pct", "% rastúcich", PCT),
         ("previous_gmv", "GMV pred rokom", EUR)],
        index_label="Kedy naposledy nakúpili",
    )

    in_window = activity.iloc[0]
    outside = activity.iloc[1]
    churned = activity.iloc[2]
    reported = scenario["growing_pct"].iloc[0]
    scenario_pct = scenario["growing_pct"].iloc[1]

    html = f"""
<h2>2. Časť účtov nie je churnutá, len netrafila okno</h2>
{_fig(figures, "kpi_activity_split")}
{table}
<p>V aktuálnom okne nakúpilo {NUM(in_window["customers"])} účtov
({PCT(in_window["share_pct"])} menovateľa) a rastie z nich
{PCT(in_window["growing_pct"])}. Ostatné dve skupiny majú
{PCT(0)} rastúcich z definície — bez objednávky v okne nemá čo rásť.</p>
<p>Medzi nimi leží <b>{NUM(outside["customers"])} účtov</b>, ktoré nakúpili za
posledných {C.KPI_DIAG_CHURN_DAYS} dní, ale mimo {C.GMV_WINDOW_MONTHS}-mesačného
okna. Nie sú churnuté a predstavujú {EUR(outside["previous_gmv"])} minuloročného
GMV — KPI ich napriek tomu počíta ako klesajúce, do jednej. Churnutých, teda bez
objednávky {C.KPI_DIAG_CHURN_DAYS} a viac dní, je {NUM(churned["customers"])}.</p>
{_fig(figures, "kpi_regular_ordering")}
<p>Ak by tých {NUM(outside["customers"])} účtov objednávalo aspoň raz za
{C.GMV_WINDOW_MONTHS} mesiace, KPI by bolo {PCT(scenario_pct)} namiesto
{PCT(reported)} — <b>o {NUM(scenario_pct - reported, 1)} p. b. vyššie bez toho, aby
sa získal jediný nový zákazník</b>. Nie je to rast tržieb, je to pravidelnosť
objednávania.</p>
{R.render_note(
    f"<b>Je to horná hranica, nie prognóza.</b> Scenár počíta všetkých "
    f"{NUM(outside['customers'])} týchto účtov ako rastúce. V skutočnosti má každý "
    f"z nich nenulové minuloročné GMV, takže rastúcim sa stane len ten, ktorý ho "
    f"prekročí. Číslo hovorí, koľko priestoru v KPI leží v časovaní objednávok, "
    f"nie koľko sa z neho podarí získať.")}
"""
    return html, figures


# ── 3. zabránenie churnu ──────────────────────────────────────────────────────
def churn_prevented_section(metrics):
    """Scenár, v ktorom churnuté účty zostanú aktívne."""
    sensitivity = metrics["diag_churn_sensitivity"]
    activity = metrics["diag_activity_split"]

    figures = [charts.kpi_churn_sensitivity(sensitivity)]

    table = R.render_table(
        sensitivity,
        [("probability_pct", "Predpoklad rastu", lambda v: PCT(v, 0)),
         ("growing_pct", "Account growth", PCT)],
        index_label="Scenár",
    )

    churned = activity.iloc[2]
    prevented = int(sensitivity["prevented"].iloc[0])
    lowest = sensitivity["growing_pct"].iloc[0]
    middle = sensitivity["growing_pct"].iloc[1]
    highest = sensitivity["growing_pct"].iloc[-1]

    html = f"""
<h2>3. Čo ak by sme zabránili churnu?</h2>
{_fig(figures, "kpi_churn_sensitivity")}
{table}
<p>Scenár berie všetkých {NUM(prevented)} churnutých účtov ako aktívnych
v aktuálnom okne a mení jediný predpoklad: aký podiel z nich rastie. Rozsah je
<b>{PCT(lowest)} až {PCT(highest)}</b> — celý zvyšok odstupu od cieľa
{C.ACCOUNT_GROWTH_TARGET_PCT} % sa teda dá vysvetliť samotným churnom, ale len
v tom najoptimistickejšom bode.</p>
<p>Najbližšie realite je stredný scenár. Zachránený účet sa dostane medzi účty
aktívne v oboch oknách a tam rastie
{PCT(metrics["diag_summary"]["active_in_both_growing_pct"])} — teda de facto hod
mincou, čo tých {PCT(50, 0)} v predpoklade zdôvodňuje. Prevencia churnu potom dá
{PCT(middle)}.</p>
<p>S churnutými účtami pritom odišlo {EUR(churned["previous_gmv"])} minuloročného
GMV. Na rozdiel od pravidelnosti objednávania zo sekcie 2 je toto <b>skutočná
strata tržieb, nie chyba merania</b> — prevencia churnu sa vyplatí aj keby žiadne
KPI neexistovalo.</p>
{R.render_note(
    f"<b>Ani jedna z týchto pák sama cieľ spoľahlivo nedosiahne.</b> Pravidelnosť "
    f"dá {PCT(metrics['diag_regular_scenario']['growing_pct'].iloc[1])}, prevencia "
    f"churnu {PCT(middle)} pri strednom predpoklade, cieľ je "
    f"{C.ACCOUNT_GROWTH_TARGET_PCT} %. Sú to však dve disjunktné skupiny účtov — "
    f"živý mimo okna a churnutý sú vzájomne vylučujúce stavy — takže sa efekty "
    f"sčítajú. Spolu dávajú <b>{PCT(metrics['diag_combined_pct'])}</b>.")}
"""
    return html, figures


# ── 4. odporúčania ────────────────────────────────────────────────────────────
def recommendations(metrics):
    """Čo z toho vyplýva pre metriku aj pre biznis."""
    summary = metrics["diag_summary"]
    activity = metrics["diag_activity_split"]

    outside = activity.iloc[1]
    churned = activity.iloc[2]

    html = f"""
<h2>4. Odporúčania</h2>
<h3>K metrike</h3>
<ol>
<li><b>Rozdeliť KPI na dve čísla.</b> Dnes v jednom čísle sedia dve nezávislé
veci: koľko účtov v okne vôbec nakúpilo ({PCT(activity.iloc[0]["share_pct"])}) a
koľko z nich rástlo ({PCT(summary["in_window_growing_pct"])}). Prvé je otázka
pravidelnosti a retencie, druhé otázka rastu objemu. Riadia sa inak a merať ich
jedným číslom znamená nevedieť, ktorá polovica sa zhoršila.</li>
<li><b>Nastaviť cieľ na tú časť, ktorá je riadená.</b> Na podiele rastúcich medzi
účtami aktívnymi v okne je {C.ACCOUNT_GROWTH_TARGET_PCT} % takmer dosiahnutých —
a nedá sa to splniť kampaňou, ktorá len rozhýbe objednávky.</li>
<li><b>Vykazovať vedľa neváženého KPI aj GMV-vážený variant.</b> Dnes je
{PCT(summary["gmv_growing_pct"])} tržieb v rastúcich účtoch oproti
{PCT(summary["growing_pct"])} účtov — nevážené KPI a tržby nehovoria to isté.</li>
</ol>

<h3>K biznisu</h3>
<ol>
<li><b>Sledovať počet objednávok na účet ako predstihový indikátor.</b> Je to
najsilnejší vzťah v dátach a jediný, ktorý sa dá riadiť v priebehu kvartálu —
účet, ktorý objedná menejkrát, je pre KPI stratený takmer isto.</li>
<li><b>Rozhýbať {NUM(outside["customers"])} účtov, ktoré len netrafili okno.</b>
Sú živé, nakúpili za posledných {C.KPI_DIAG_CHURN_DAYS} dní a je to najlacnejšia
páka na KPI. Konkrétne: dostať ich na interval objednávania kratší ako
{C.GMV_WINDOW_MONTHS} mesiace.</li>
<li><b>Prevencia churnu má prioritu podľa GMV, nie podľa počtu účtov.</b>
S {NUM(churned["customers"])} churnutými účtami odišlo
{EUR(churned["previous_gmv"])} — to je skutočná strata a vyplatí sa aj bez ohľadu
na KPI.</li>
<li><b>Zamerať prevenciu na účty, ktoré strácajú frekvenciu</b>, nie na tie, ktoré
už odišli. Do churnu padá účet až po tom, čo mu najprv klesne frekvencia, takže
signál je k dispozícii vopred.</li>
</ol>

<p class="small" style="margin-top:48px;border-top:1px solid var(--bd);padding-top:16px">
Grafy sú interaktívne — prejdi kurzorom pre presné hodnoty. Všetky tabuľky a čísla
v texte sú generované z dát. Scenáre sú kontrafaktuálna aritmetika, nie prognózy.
Dátum analýzy {C.AS_OF:%-d. %-m. %Y}.</p>
"""
    return html, []


SECTION_BUILDERS = [
    header,
    frequency_section,
    activity_section,
    churn_prevented_section,
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
