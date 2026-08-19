# -*- coding: utf-8 -*-
"""Sekcie reportu Account growth drill-in.

Samostatný report, ktorý rozoberá hodnotu KPI na skupiny účtov. Hlavný report
(sections.py) odpovedá na otázku, prečo je KPI nízke; tento ukazuje, kde presne
sedí a čo s ním spraví odfiltrovanie spodných extrémov.
"""

import pathlib

from src.common import constants as C
from src.drill_in import charts
from src.drill_in import metrics_credit_memos
from src.drill_in import metrics_order_items as MOI
from src.drill_in import order_item_groups as GROUPS
from src.common import metrics_kpi_diagnostics as MD
from src.common import report as R

EUR = R.format_eur
PCT = R.format_pct
NUM = R.format_number

MONTHS_PER_YEAR = 12

# Koľko najväčších účtov koša zhrnie veta o koncentrácii.
LONG_TENURE_TOP = 5


def YEARS(months, decimals=1):
    """Mesiace vyjadrené v rokoch."""
    return NUM(months / MONTHS_PER_YEAR, decimals)


def _fig(figures, figure_id):
    """Vykreslí graf podľa jeho ID, alebo nič, ak je v C.HIDDEN_CHARTS."""
    if figure_id in C.HIDDEN_CHARTS:
        return ""
    for figure in figures:
        if figure["id"] == figure_id:
            return R.render_figure(figure)
    raise KeyError(f"graf s id '{figure_id}' nie je medzi figures")


def header(metrics):
    """Nadpis a prehľadové karty oboch datasetov."""
    full = metrics["account_growth_summary"]

    cards = [
        ("KPI, celý dataset", PCT(full["growing_pct"], 1)),
        ("Posudzovaných účtov", NUM(full["accounts"])),
        ("Cieľ", f"{C.ACCOUNT_GROWTH_TARGET_PCT} %"),
    ]

    html = f"""
<h1>Account growth — drill-in</h1>
<ul class="lead">
<li>Zdroj: <code>{C.INPUT_LABEL}</code></li>
<li>Stav k: {C.AS_OF:%-d.\u00a0%-m.\u00a0%Y}</li>
</ul>
{R.render_kpi_cards(cards)}
"""
    return html, []


def order_count_section(metrics):
    """KPI podľa počtu objednávok a kto sú účty, ktoré filter vyradí.

    Jedna sekcia zámerne — druhá polovica odpovedá na otázku, ktorú vyvolá
    prvá: prečo filter KPI nezdvihne. Oddelene sa čítali ako dve nesúvisiace
    zistenia.
    """
    diag = metrics["diag_summary"]
    detail = metrics["dropped_accounts"]
    split = metrics["dropped_growth"]

    figures = [
        charts.kpi_by_order_count(metrics["diag_by_order_count"], diag["growing_pct"],
                                  filtered=metrics["filtered_by_order_count"]),
        charts.dropped_growth_split(split, diag["growing_pct"]),
    ]

    return f"""
<h2>1. KPI podľa počtu objednávok za posledných {C.KPI_DIAG_WINDOW_MONTHS} mesiacov</h2>
{_dataset_definitions(metrics)}
{_fig(figures, "kpi_by_order_count")}
{_filtered_text(metrics)}

<h3>Kto sú vyradené účty</h3>
{_dropped_intro(metrics)}
{_fig(figures, "dropped_growth")}
{_dropped_split_text(split, diag["growing_pct"])}
{_dropped_profile(metrics)}
{_dropped_table(detail)}
""", figures


def _dataset_definitions(metrics):
    """Definícia oboch množín účtov, ktoré graf porovnáva.

    Popisuje menovateľ KPI, nie surový dataset — počty zákazníkov v exporte sú
    pre tento graf bez významu, KPI z nich vidí len zlomok.
    """
    full = metrics["account_growth_summary"]
    filtered = metrics["filtered_summary"]

    return f"""
<p><b>Celý dataset</b> — účty, ktoré KPI posudzuje: staršie ako
{C.ACCOUNT_GROWTH_MIN_AGE_MONTHS} mesiacov a s nenulovým GMV aspoň v jednom z dvoch
{C.GMV_WINDOW_MONTHS}-mesačných okien. Spolu ich je {NUM(full["accounts"])}.</p>
<p><b>Bez spodných extrémov</b> — tie isté účty, ale bez zákazníkov, ktorí za celý
život minuli menej než {EUR(C.SMALL_VETERAN_LIFETIME_GMV)}. Zostane
{NUM(filtered["accounts"])} účtov, teda o {NUM(full["accounts"] - filtered["accounts"])}
menej.</p>
<p><b>Prečo tu nie je variant „bez účtov s jedinou objednávkou“.</b> Taký filter by
nemal čo odfiltrovať — účet s jedinou objednávkou v menovateli KPI nikdy nie je.
Musel by naraz spĺňať dve podmienky, ktoré sa pri jedinej objednávke vylučujú:
prvá objednávka staršia než {C.ACCOUNT_GROWTH_MIN_AGE_MONTHS} mesiacov a zároveň
objednávka aspoň v jednom z dvoch okien. Ak tá jediná objednávka padne do okna,
účet je príliš mladý; ak je dosť stará, do okna nepadne.</p>
"""


def _filtered_text(metrics):
    """Jediný záver, ktorý z porovnania oboch sérií plynie."""
    full_breakdown = metrics["diag_by_order_count"]
    filtered_breakdown = metrics["filtered_by_order_count"]
    full = metrics["account_growth_summary"]
    filtered = metrics["filtered_summary"]

    changed = _changed_buckets(full_breakdown, filtered_breakdown)
    first_untouched = _first_untouched_bucket(full_breakdown, changed)

    return f"""
<p><b>Dataset bez spodných extrémov má horšie KPI v košoch {_bucket_list(changed)}</b> —
od koša {first_untouched} vyššie sú obe série totožné. Celkovo
{PCT(full["growing_pct"])} oproti {PCT(filtered["growing_pct"])}.</p>
"""


def _changed_buckets(full_breakdown, filtered_breakdown):
    """Koše, v ktorých sa podiel rastúcich po filtri zmenil.

    Porovnáva sa na jedno desatinné miesto, teda na presnosť, s akou je hodnota
    v reporte vidieť — inak by sa medzi „zmenené“ dostali koše líšiace sa
    v stotinách, ktoré v grafe nikto nerozozná.
    """
    changed = []
    for bucket in full_breakdown.index:
        before = round(full_breakdown.loc[bucket, "growing_pct"], 1)
        after = round(filtered_breakdown.loc[bucket, "growing_pct"], 1)
        if before != after:
            changed.append(bucket)
    return changed


def _first_untouched_bucket(full_breakdown, changed):
    """Prvý kôš, od ktorého sa už obe série prekrývajú."""
    for bucket in full_breakdown.index:
        if bucket not in changed:
            continue
        position = list(full_breakdown.index).index(bucket)
        if position + 1 < len(full_breakdown.index):
            candidate = full_breakdown.index[position + 1]
            if candidate not in changed:
                return candidate
    return full_breakdown.index[-1]


def _bucket_list(buckets):
    """Zoznam popiskov košov do vety."""
    if len(buckets) == 1:
        return buckets[0]
    return ", ".join(buckets[:-1]) + f" a {buckets[-1]}"


def _dropped_intro(metrics):
    """Veľkosť a váha skupiny vyradenej z menovateľa."""
    detail = metrics["dropped_accounts"]
    full = metrics["full_quality"]
    filtered = metrics["filtered_quality"]

    dropped_customers = full["customers"] - filtered["customers"]

    return f"""
<p>Filter vyradí z databázy {NUM(dropped_customers)} zákazníkov, ale drvivá väčšina
z nich v menovateli KPI nikdy nebola. Zaujímavých je
<b>{NUM(len(detail))} účtov, ktoré v ňom boli a vypadli z neho</b> — len tie hýbu
hodnotou KPI. Za celý život, teda od začiatku dát, majú spolu
{EUR(detail["lifetime_gmv"].sum())}; za posledných {C.KPI_DIAG_WINDOW_MONTHS} mesiacov
{EUR(detail["gmv_window"].sum())}. Žiadny z nich nemá viac ako
{NUM(detail["lifetime_orders"].max())} objednávok za život, medián je
{NUM(detail["lifetime_orders"].median())}.</p>
"""


def _dropped_split_text(split, reference_pct):
    """Prečo filter KPI nezdvihne, ale zrazí."""
    growing = split.loc[MD.DROPPED_GROWING]
    declining = split.loc[MD.DROPPED_DECLINING]

    return f"""
<p>Z {NUM(int(split["customers"].sum()))} vyradených účtov je
{NUM(growing["customers"])} rastúcich a {NUM(declining["customers"])} klesajúcich,
teda <b>{PCT(growing["share_pct"])} rastúcich oproti celkovému KPI
{PCT(reference_pct)}</b>. Filter teda neodoberá mŕtvu váhu — odoberá skupinu,
ktorá je nadpriemerne rastúca.</p>
"""


def _dropped_profile(metrics):
    """Kto tie účty sú a akú majú váhu."""
    detail = metrics["dropped_accounts"]
    countries = metrics["dropped_by_country"]

    monthly = detail["gmv_window"].sum() / C.KPI_DIAG_WINDOW_MONTHS

    return f"""
<h3>Čo sú zač</h3>
<p>Fitness centrá, telocvične a malé e-shopy s doplnkami — v zozname nižšie sú názvy
ako gym či sport. <b>Ani jedna firma, ktorá by vyzerala ako
veľkoodberateľ.</b> Za posledných {C.KPI_DIAG_WINDOW_MONTHS} mesiacov minuli spolu
{EUR(detail["gmv_window"].sum())}, teda {EUR(monthly)} mesačne.</p>
<p><b>Nikto z nich nemá viac než
{NUM(detail["lifetime_orders"].max())} objednávok za celý život</b>, typicky
{NUM(detail["lifetime_orders"].median())}, a to za obdobie niekoľkých rokov. Sú to
zákazníci, ktorí si nás dvakrát-trikrát vyskúšali a nezostali.</p>
<p>Geograficky: {_country_list(countries)}.</p>
"""


def _country_list(countries):
    """Krajiny vyradených účtov ako veta, od najpočetnejšej."""
    parts = []
    for country, row in countries.iterrows():
        parts.append(f"{NUM(row['customers'])}× {R.escape(country)}")
    return ", ".join(parts)


def _dropped_table(detail):
    """Zroloateľný zoznam vyradených účtov."""
    table = detail.copy()
    table.index = table["name"]
    rendered = R.render_table(
        table,
        [("country", "Krajina", str),
         ("lifetime_gmv", "Lifetime GMV", EUR),
         ("gmv_window", f"GMV za posledných {C.KPI_DIAG_WINDOW_MONTHS} mes.", EUR),
         ("lifetime_orders", "Obj. celkom", NUM),
         ("orders_window", f"Obj. za posledných {C.KPI_DIAG_WINDOW_MONTHS} mes.", NUM),
         ("last_order", "Posledná objednávka", lambda value: f"{value:%-d. %-m. %Y}"),
         ("growing", "Rastie", lambda value: "áno" if value else "nie")],
        index_label="Účet",
    )
    return R.render_rollup(f"Zoznam všetkých {NUM(len(detail))} účtov", rendered)


def single_order_section(metrics):
    """Zákazníci, ktorí za celý život objednali práve raz."""
    single = metrics["single_orders"]
    repeat_first = metrics["single_repeat_first"]

    figures = [charts.order_value_mix(metrics["single_value_mix"])]

    return f"""
<h2>2. Zákazníci s jedinou objednávkou</h2>
{_single_intro(metrics)}
{_fig(figures, "order_value_mix")}
{_single_value_text(single, repeat_first)}
{_single_big_orders_table(single)}
""", figures


def _single_intro(metrics):
    """Veľkosť skupiny a aká je jej váha v tržbách."""
    single = metrics["single_orders"]
    quality = metrics["full_quality"]

    return f"""
<p>Zákazníci, ktorí za celý život objednali práve raz. Počítajú sa len tí,
ktorých objednávka je staršia ako {C.SINGLE_ORDER_MIN_AGE_MONTHS} mesiacov.
<b>Je ich {NUM(len(single))}, teda {PCT(len(single) / quality["customers"] * 100)}
databázy, ale len {EUR(single["gmv"].sum())} GMV</b>, čo je
{PCT(single["gmv"].sum() / quality["gmv"] * 100)} tržieb.</p>
"""


def _single_value_text(single, repeat_first):
    """Prečo sa jednorazový zákazník nedá spoznať z prvej objednávky."""
    return f"""
<p><b>Z prvej objednávky sa nedá povedať, kto sa vráti.</b> Medián jedinej objednávky
je {EUR(single["gmv"].median())}, medián prvej objednávky zákazníka, ktorý sa neskôr
vrátil, {EUR(repeat_first["gmv"].median())}. Rozdiel je
{EUR(abs(single["gmv"].median() - repeat_first["gmv"].median()))} a tvary oboch
rozdelení sa prekrývajú vo všetkých košoch. Jednorazový zákazník nie je iný typ
zákazníka — pri prvom nákupe vyzerá rovnako ako každý iný.</p>
"""


def _single_big_orders_table(single):
    """Najväčšie jednorazové objednávky."""
    big = single.loc[single["gmv"] >= C.ORDER_VALUE_EDGES[-1]].sort_values(
        "gmv", ascending=False).copy()
    big["label"] = big["company_bill"].fillna(big["customer_email"])
    big = big.set_index("label")

    table = R.render_table(
        big,
        [("increment_id", "Objednávka", str),
         ("customer_email", "E-mail", str),
         ("gmv", "Hodnota", EUR),
         ("country", "Krajina", str),
         ("created_at", "Dátum", lambda value: f"{value:%-d. %-m. %Y}")],
        index_label="Účet",
    )

    return f"""
<h3>Najväčšie stratené objednávky</h3>
<p>{NUM(len(big))} zákazníkov urobilo jedinú objednávku nad
{EUR(C.ORDER_VALUE_EDGES[-1])} a už sa nevrátili. Spolu je to
{EUR(big["gmv"].sum())}, teda {PCT(big["gmv"].sum() / single["gmv"].sum() * 100)}
GMV celej skupiny pri {PCT(len(big) / len(single) * 100)} zákazníkov.</p>
{R.render_rollup(f"Zoznam všetkých {NUM(len(big))} objednávok", table)}
"""


def zero_accounts_section(metrics):
    """Účty, ktoré v aktuálnom okne nenakúpili."""
    return _account_group_section(
        metrics,
        prefix="zero",
        heading="5. Účty, ktoré odišli do nuly",
        group_note="účty, ktoré odišli do nuly",
        intro=_zero_intro(metrics),
    )


def churned_accounts_section(metrics):
    """Účty, ktoré nenakúpili už KPI_DIAG_CHURN_DAYS dní."""
    # Presmerované na novú funkciu špecifickú pre churn
    return _churned_group_section(
        metrics,
        prefix="churned",
        heading="6. Churnuté účty",
        group_note="churnuté účty",
        intro=_churned_intro(metrics),
    )


# --- NOVÁ FUNKCIA PRIDANÁ POD PÔVODNÚ _account_group_section ---
def _churned_group_section(metrics, prefix, heading, group_note, intro):
    """Špeciálna sekcia pre churnuté účty s dodatočnými grafmi správania."""
    accounts = metrics[f"{prefix}_accounts"]
    cluster = metrics[f"{prefix}_cluster"]
    chars = metrics[f"{prefix}_characteristics"]

    timeline_id = f"{prefix}_gmv_timeline"
    cluster_id = f"{prefix}_last_order_cluster"
    tenure_id = f"{prefix}_tenure"
    orders_id = f"{prefix}_orders"
    country_id = f"{prefix}_country"

    figures = [
        charts.account_gmv_timeline(metrics[f"{prefix}_monthly"],
                                    metrics[f"{prefix}_monthly_orders"],
                                    accounts, timeline_id, group_note),
        charts.last_order_cluster(cluster, cluster_id, group_note),
        charts.churn_tenure_chart(chars["tenure"], tenure_id, group_note, len(accounts)),
        charts.churn_orders_chart(chars["orders"], orders_id, group_note, len(accounts)),
        charts.churn_country_chart(chars["country"], country_id, group_note, len(accounts)),
    ]

    return f"""
<h2>{heading}</h2>
{intro}

<h3>Vyhľadanie konkrétneho účtu</h3>
{_fig(figures, timeline_id)}

<h3>Kto sú títo zákazníci a ako sa správali?</h3>
{_fig(figures, tenure_id)}
{_long_tenure_block(chars["long_tenure"], accounts)}
{_fig(figures, orders_id)}
{_fig(figures, country_id)}

<h3>Kedy naposledy nakúpili</h3>
{_fig(figures, cluster_id)}
{_cluster_text(cluster)}

{R.render_rollup(f"Zoznam všetkých {NUM(len(accounts))} účtov", _accounts_table(accounts))}
""", figures


def _account_group_section(metrics, prefix, heading, group_note, intro):
    """Sekcia o jednej skupine účtov: graf v čase, zhluk odchodov a zoznam."""
    accounts = metrics[f"{prefix}_accounts"]
    cluster = metrics[f"{prefix}_cluster"]
    timeline_id = f"{prefix}_gmv_timeline"
    cluster_id = f"{prefix}_last_order_cluster"

    figures = [
        charts.account_gmv_timeline(metrics[f"{prefix}_monthly"],
                                    metrics[f"{prefix}_monthly_orders"],
                                    accounts, timeline_id, group_note),
        charts.last_order_cluster(cluster, cluster_id, group_note),
    ]

    return f"""
<h2>{heading}</h2>
{intro}
{_fig(figures, timeline_id)}

<h3>Kedy naposledy nakúpili</h3>
{_fig(figures, cluster_id)}
{_cluster_text(cluster)}
{R.render_rollup(f"Zoznam všetkých {NUM(len(accounts))} účtov", _accounts_table(accounts))}
""", figures

def _zero_intro(metrics):
    """Kto sú účty, ktoré prestali nakupovať."""
    accounts = metrics["zero_accounts"]
    summary = metrics["account_growth_summary"]
    top_ten = accounts.nlargest(10, "previous")["previous"].sum()
    fresh = accounts.loc[accounts["months_silent"] <= 6]

    return f"""
<p>Účty s nenulovým GMV v minuloročnom okne a nulovým v aktuálnom. Je ich
<b>{NUM(len(accounts))}, teda {PCT(len(accounts) / summary["accounts"] * 100)}
posudzovaných účtov</b>. V minuloročnom okne mali {EUR(accounts["previous"].sum())}.</p>
{_decathlon_note()}
"""


def _decathlon_note():
    """Najväčší účet skupiny odišiel do nuly len zdanlivo.

    Zákazník je e-mail, takže zmena kontaktnej osoby vyzerá ako odchod jedného
    účtu a akvizícia druhého. Decathlon je najviditeľnejší prípad, ale ten istý
    mechanizmus môže byť aj za ďalšími účtami v zozname.
    """
    return R.render_note(
        "<b>Najväčší účet skupiny neodišiel — len zmenil e-mail.</b> "
        "Decathlon SK prešiel na inú kontaktnú osobu a nakupuje ďalej pod novou "
        "adresou.")


def _churned_intro(metrics):
    """Ako sa churnuté účty líšia od širšej skupiny odídených."""
    accounts = metrics["churned_accounts"]
    zero = metrics["zero_accounts"]

    alive = len(zero) - len(accounts)
    alive_gmv = zero["previous"].sum() - accounts["previous"].sum()

    return f"""
<p>Podmnožina predchádzajúcej skupiny: účty, ktoré nenakúpili už
<b>{C.KPI_DIAG_CHURN_DAYS}+ dní</b>. Je ich {NUM(len(accounts))} z
{NUM(len(zero))} odídených a v minuloročnom okne mali
{EUR(accounts["previous"].sum())}, teda
{PCT(accounts["previous"].sum() / zero["previous"].sum() * 100)} GMV odídenej skupiny.</p>
"""


def _cluster_text(cluster):
    """Či sa odchody zhlukujú v čase."""
    peak = cluster["customers"].idxmax()
    peak_row = cluster.loc[peak]
    share = peak_row["customers"] / cluster["customers"].sum() * 100

    return f"""
<p>Najviac účtov naposledy nakúpilo v {peak} — {NUM(peak_row["customers"])} účtov
({PCT(share)} skupiny) s minuloročným GMV {EUR(peak_row["previous_gmv"])}. Ak sa
niektorý vrchol kryje s prevádzkovou zmenou na našej strane, máme kandidáta
na spoločnú príčinu; inak je to rozptýlený odchod bez jedného spúšťača.</p>
"""


def _long_tenure_block(long_tenure, accounts):
    """Najvyšší kôš grafu dĺžky života rozpísaný po účtoch."""
    if long_tenure.empty:
        return ""
    return f"""
{_long_tenure_text(long_tenure, accounts)}
{R.render_rollup(f"Zoznam {NUM(len(long_tenure))} účtov z koša "
                 f"{MD.CHURN_TENURE_BUCKETS[-1]}", _long_tenure_table(long_tenure))}
"""


def _long_tenure_text(long_tenure, accounts):
    """Čo najvyšší kôš znamená v peniazoch."""
    count_share = len(long_tenure) / len(accounts) * 100
    gmv_share = long_tenure["lifetime_gmv"].sum() / accounts["lifetime_gmv"].sum() * 100

    top_count = min(LONG_TENURE_TOP, len(long_tenure))
    top_share = (long_tenure["lifetime_gmv"].head(top_count).sum()
                 / long_tenure["lifetime_gmv"].sum() * 100)

    return f"""
<p>{_long_tenure_lead(count_share, gmv_share)} <b>{NUM(len(long_tenure))} účtov, ktoré
u nás nakupovali dlhšie než {YEARS(MD.CHURN_LONG_TENURE_MONTHS, 0)} roky</b>, je
{PCT(count_share)} skupiny a drží {PCT(gmv_share)} jej lifetime GMV
({EUR(long_tenure["lifetime_gmv"].sum())}).
Medián dĺžky života je tu {YEARS(long_tenure["tenure_months"].median())} roka,
takže zlý onboarding to nevysvetlí — títo zákazníci boli zabehnutí.</p>
<p>Ani v rámci koša nie sú si účty rovné: <b>top {NUM(top_count)} z nich drží
{PCT(top_share)} jeho lifetime GMV</b>. Medián ticha je
{NUM(long_tenure["months_silent"].median(), 1)} mesiacov — čím kratšie mlčia, tým
väčšiu šancu má oslovenie.</p>
"""


def _long_tenure_lead(count_share, gmv_share):
    """Úvodná veta odseku. Mení sa podľa dát, aby netvrdila viac, než v nich je."""
    if gmv_share > count_share:
        return "Najvyšší kôš váži v peniazoch viac, než napovedá jeho počet."
    return "Najvyšší kôš má na GMV menšiu váhu, než by jeho počet napovedal."


def _long_tenure_table(long_tenure):
    """Účty z najvyššieho koša, od najväčšieho lifetime GMV."""
    table = long_tenure.copy()
    table.index = table["name"]
    return R.render_table(
        table,
        [("country", "Krajina", str),
         ("tenure_months", "Nakupovali (rokov)", YEARS),
         ("lifetime_orders", "Obj. za život", NUM),
         ("orders_per_month", "Obj./mesiac", lambda value: NUM(value, 1)),
         ("lifetime_gmv", "Lifetime GMV", EUR),
         ("previous", "GMV pred rokom", EUR),
         ("mean_order", "Priemerná obj.", EUR),
         ("last_order", "Posledná objednávka", lambda value: f"{value:%-d. %-m. %Y}"),
         ("months_silent", "Mesiacov ticho", lambda value: NUM(value, 1))],
        index_label="Účet",
    )


def _accounts_table(accounts):
    """Zoznam účtov skupiny."""
    table = accounts.copy()
    table.index = table["name"]
    return R.render_table(
        table,
        [("country", "Krajina", str),
         ("previous", "GMV pred rokom", EUR),
         ("lifetime_gmv", "Lifetime GMV", EUR),
         ("lifetime_orders", "Obj. za život", NUM),
         ("mean_order", "Priemerná obj.", EUR),
         ("median_order", "Mediánová obj.", EUR),
         ("orders_per_month", "Obj./mesiac", lambda value: NUM(value, 1)),
         ("last_order", "Posledná objednávka", lambda value: f"{value:%-d. %-m. %Y}"),
         ("months_silent", "Mesiacov ticho", lambda value: NUM(value, 1))],
        index_label="Účet",
    )


def credit_memo_section(metrics):
    """Objednávky s dobropisom a to, čo sa k nim našlo v Slacku."""
    memos = metrics["credit_memos"]
    causes = metrics["credit_memo_causes"]

    figures = [charts.credit_memo_causes(causes)]

    return f"""
<h2>3. One-time objednávky s dobropisom</h2>
{_credit_memo_intro(memos, metrics["single_orders"])}
{_fig(figures, "credit_memo_causes")}
{_credit_memo_causes_table(causes)}
{_credit_memo_text(causes)}
{R.render_rollup(f"Zoznam všetkých {NUM(len(memos))} objednávok",
                 _credit_memo_table(memos))}
""", figures


def _credit_memo_intro(memos, single):
    """Odkiaľ zoznam je a čo sa s ním dá a nedá robiť.

    Za nájdené sa počíta objednávka s odkazom na vlákno, nie objednávka mimo
    skupiny „bez zmienky“ — nerelevantné objednávky sú zaradené z dát, nie
    z Slacku, a medzi nálezy nepatria.
    """
    found = int((memos["link"] != "").sum())

    return f"""
<p>Východiskom je zoznam objednávok účtov, ktoré za
celý život urobili práve jednu objednávku — je ich
{NUM(len(single))}. Tie sa preverili v Magente a <b>{NUM(len(memos))} z nich má
vystavený dobropis</b>. Ku každej z nich sa potom
prehľadal Slack a LaDesk a z toho, čo sa našlo, je odvodený dôvod dobropisu.</p>
<p>Spolu je to {EUR(memos["gmv"].sum())}, dobropisovaných z toho bolo
{EUR(memos["total_refund"].sum())}, teda
{PCT(memos["total_refund"].sum() / memos["gmv"].sum() * 100)}.</p>
{_credit_memo_coverage_note(memos, single, found)}
"""


def _credit_memo_coverage_note(memos, single, found):
    """Aký zlomok stratených účtov táto sekcia vôbec vysvetľuje.

    Najdôležitejšia veta celej sekcie. Bez nej sa rozdelenie príčin číta ako
    obraz toho, prečo zákazníci odchádzajú — pritom je to obraz úzkeho výseku,
    ktorý po sebe zanechal písomnú stopu.
    """
    memo_pct = len(memos) / len(single) * 100
    found_pct = found / len(single) * 100
    unknown = len(single) - found

    return R.render_note(
        f"<b>Tento graf vysvetľuje {PCT(found_pct)} skupiny.</b> "
        f"Účtov s jedinou objednávkou za život je {NUM(len(single))}. Dobropis "
        f"má z nich {NUM(len(memos))} ({PCT(memo_pct)}) a písomnú stopu sme "
        f"našli pri {NUM(found)} ({PCT(found_pct)}). "
        f"<b>Pri zvyšných {NUM(unknown)} účtoch nevieme o dôvode nevrátenia sa "
        f"vôbec nič</b> — nesťažovali sa, nereklamovali.<br>"
    )


def _memo_link(url):
    """Odkaz do vlákna, popísaný podľa toho, odkiaľ vedie."""
    return R.render_link(url, metrics_credit_memos.link_source(url))


def _credit_memo_causes_table(causes):
    """Súhrn skupín: počet, GMV a výška dobropisu."""
    return R.render_table(
        causes,
        [("orders", "Objednávok", NUM),
         ("gmv", "GMV objednávok", EUR),
         ("refund", "Dobropisované", EUR),
         ("refund_pct", "Podiel dobropisu", PCT)],
        index_label="Príčina",
    )


def _credit_memo_text(causes):
    """Čo z rozdelenia príčin plynie."""
    explained = metrics_credit_memos.explained(causes)
    top = explained["orders"].idxmax()
    top_row = explained.loc[top]

    return f"""
<p><b>Najpočetnejšia zistená príčina je „{top.lower()}“ — {NUM(top_row["orders"])}
objednávok za {EUR(top_row["gmv"])}</b>, teda
{PCT(top_row["gmv"] / causes["gmv"].sum() * 100)} GMV celého zoznamu:
{C.CREDIT_MEMO_DESCRIPTIONS[top]}.</p>
{_credit_memo_costliest(explained, causes, top)}
{_credit_memo_rest(explained, top)}
"""


def _credit_memo_costliest(explained, causes, top):
    """Veta o najdrahšej príčine, ak to nie je tá najpočetnejšia.

    Počet a peniaze sa nemusia kryť — jedna veľká objednávka prebije desať
    malých. Veta sa preto neopakuje zbytočne, keď je to tá istá skupina.
    """
    costliest = explained["gmv"].idxmax()
    share = explained.loc[costliest, "gmv"] / causes["gmv"].sum() * 100

    if costliest == top:
        return (f"<p>Je to zároveň najdrahšia skupina zoznamu.</p>")
    return f"""
<p>V peniazoch však vedie „{costliest.lower()}“ —
{NUM(explained.loc[costliest, "orders"])} objednávok za
{EUR(explained.loc[costliest, "gmv"])}, teda {PCT(share)} GMV zoznamu.</p>
"""


def _credit_memo_rest(explained, top):
    """Zvyšné zistené príčiny ako veta. Skladá sa z dát, nie natvrdo."""
    rest = explained.drop(index=top)
    if rest.empty:
        return ""

    items = []
    for cause, row in rest.sort_values("orders", ascending=False).iterrows():
        items.append(f"<li><b>{cause}</b> — {NUM(row['orders'])} obj., "
                     f"{EUR(row['gmv'])}: {C.CREDIT_MEMO_DESCRIPTIONS[cause]}</li>")
    return f"<p>Zvyšné zistené príčiny:</p>\n<ul>{''.join(items)}</ul>"


def _credit_memo_table(memos):
    """Zoznam objednávok s dobropisom, príčinou a odkazom do Slacku."""
    table = memos.copy()
    table.index = table["label"]
    return R.render_table(
        table,
        [("order_number", "Objednávka", str),
         ("order_date", "Dátum", lambda value: f"{value:%-d. %-m. %Y}"),
         ("gmv", "GMV", EUR),
         ("total_refund", "Dobropis", EUR),
         ("category", "Príčina", str),
         ("note", "Čo sa našlo v Slacku", str),
         ("link", "Vlákno", _memo_link)],
        index_label="Zákazník",
    )


SINGLE_ITEMS = "single_items"
REGULAR_ITEMS = "regular_items"


def order_items_section(metrics):
    """Čo nakupujú jednorazoví a čo bežní zákazníci, vedľa seba.

    Obe skupiny sú v jednej sekcii a v dvoch stĺpcoch zámerne — rebríčky produktov
    dávajú zmysel hlavne v porovnaní a pod sebou sa porovnávajú zle.
    """
    if metrics[SINGLE_ITEMS] is None or metrics[REGULAR_ITEMS] is None:
        return _order_items_missing(), []

    left, left_figures = _order_items_column(
        metrics, SINGLE_ITEMS,
        heading="Jednorazoví zákazníci",
        group_note=GROUPS.GROUPS[GROUPS.SINGLE]["note"],
        lead=(f"Položky objednávok jednorázových zákazníkov, rozpadnuté na produkty; "
              f"{GROUPS.period_note()}."),
    )
    right, right_figures = _order_items_column(
        metrics, REGULAR_ITEMS,
        heading="Bežní zákazníci",
        group_note=GROUPS.GROUPS[GROUPS.REGULAR]["note"],
        lead=(f"Zákazníci, ktorí za život nakúpili viac než raz; "
              f"{GROUPS.period_note()}."),
    )

    return f"""
<h2>4. Čo kto nakupuje</h2>
{_order_items_lead()}
{R.render_columns(list(zip(left, right)))}
""", left_figures + right_figures


def _order_items_lead():
    """Prečo sú obe skupiny vedľa seba."""
    return """
<p>Vľavo tí, čo sa nevrátili, vpravo tí, čo sa vracajú.</p>
"""


def _order_items_column(metrics, prefix, heading, group_note, lead):
    """Bloky jedného stĺpca porovnania, v poradí zhora nadol.

    Vracia zoznam, nie hotové HTML — každý blok je jedna bunka mriežky a musí
    mať svoj náprotivok v druhom stĺpci, aby si riadky držali výšku.
    """
    sku_totals = metrics[f"{prefix}_by_sku"]
    gmv_id = f"{prefix}_top_skus_gmv"
    orders_id = f"{prefix}_top_skus_orders"

    figures = [
        charts.top_skus_by_gmv(sku_totals, C.SINGLE_ORDER_ITEMS_TOP, gmv_id, group_note),
        charts.top_skus_by_orders(sku_totals, C.SINGLE_ORDER_ITEMS_TOP, orders_id, group_note),
    ]

    blocks = [
        f"<h3>{heading}</h3>",
        _order_items_intro(metrics, prefix, lead),
        _fig(figures, gmv_id),
        _fig(figures, orders_id),
        _order_items_concentration(metrics, prefix),
        R.render_rollup(f"Top {C.SINGLE_ORDER_ITEMS_TOP} produktov podľa GMV v tabuľke",
                        _order_items_table(sku_totals, "gmv")),
        R.render_rollup(f"Top {C.SINGLE_ORDER_ITEMS_TOP} produktov podľa počtu "
                        f"objednávok v tabuľke",
                        _order_items_table(sku_totals, "orders")),
    ]
    return blocks, figures


def _order_items_missing():
    """Sekcia bez dát. Vysvetlí, čo treba spustiť, a nespadne."""
    return f"""
<h2>4. Čo kto nakupuje</h2>
{R.render_note(
    "<b>Dáta o položkách nie sú načítané.</b> Zdrojový súbor "
    f"<code>{pathlib.Path(C.ORDER_ITEMS_CSV).name}</code> má cez 4 GB a report "
    "ho nečíta — číta len odloženú cache. Vyrob ju spustením "
    "<code>python3 -m src.drill_in.build_order_items</code> a report vygeneruj znova.")}
"""


def _order_items_intro(metrics, prefix, lead):
    """Veľkosť skupiny a profil košíka."""
    profile = metrics[f"{prefix}_profile"]

    return f"""
<p>{lead} Je to {NUM(profile["orders"])} objednávok a
<b>{NUM(profile["skus"])} rôznych produktov</b>.</p>
<p>Medián objednávky: {NUM(profile["median_products"])} produktov,
{NUM(profile["median_units"])} kusov, {EUR(profile["median_gmv"])}.
Jediný produkt malo {PCT(profile["single_product_pct"])} objednávok.</p>
{_gift_text(metrics[f"{prefix}_gift"], prefix)}
{_sku_names_note(metrics[f"{prefix}_by_sku"])}
"""


def _gift_text(gift, prefix):
    """Aká časť skupiny mala v objednávke darček alebo vzorku.

    Pri jednorazových zákazníkoch je objednávka a účet to isté, preto sa dá
    hovoriť o podiele účtov; pri bežných zákazníkoch len o podiele objednávok.
    """
    unit = "účtov" if prefix == SINGLE_ITEMS else "objednávok"

    return f"""
<p><b>Darček alebo vzorku obsahovalo {PCT(gift["share_pct"])} {unit}</b>
({NUM(gift["orders_with_gift"])} z {NUM(gift["orders"])}). Ide o produkty
„Darček — nechám sa prekvapiť“ a „Vzorka — nechám sa prekvapiť“.</p>
"""


def _sku_names_note(sku_totals):
    """Upozorní, ak zobrazené SKU ešte nemajú doplnený názov produktu."""
    displayed = MOI.displayed_skus(sku_totals)
    unnamed = int((displayed["label"] == displayed.index).sum())
    if unnamed == 0:
        return ""

    return f"""
<p class="small">{NUM(unnamed)} z {NUM(len(displayed))} zobrazených produktov
zatiaľ nemá doplnený názov a je v grafe uvedený svojím kódom. Názvy sa dopĺňajú
do <code>{pathlib.Path(C.SKU_NAMES_CSV).name}</code>.</p>
"""


def _order_items_concentration(metrics, prefix):
    """Či sa GMV skupiny sústreďuje do zopár SKU."""
    concentration = metrics[f"{prefix}_concentration"]
    top = concentration.iloc[0]

    return f"""
<p>{top.name} tvorí {PCT(top["gmv_share_pct"])} GMV skupiny.
{_concentration_list(concentration)}</p>
"""


def _concentration_list(concentration):
    """Ostatné úrovne koncentrácie do vety."""
    parts = []
    for label, row in concentration.iloc[1:].iterrows():
        parts.append(f"{label} {PCT(row['gmv_share_pct'])}")
    if not parts:
        return ""
    return "Ďalej: " + ", ".join(parts) + "."


def _order_items_table(sku_totals, column):
    """Najsilnejšie produkty v tabuľke, zoradené podľa zvolenej veličiny."""
    return R.render_table(
        sku_totals.sort_values(column, ascending=False).head(C.SINGLE_ORDER_ITEMS_TOP),
        [("label", "Produkt", str),
         ("gmv", "GMV", EUR),
         ("gmv_share_pct", "Podiel na GMV", PCT),
         ("orders", "Objednávok", NUM),
         ("orders_share_pct", "Podiel objednávok", PCT),
         ("qty", "Kusov", NUM)],
        index_label="Kód",
    )


SECTION_BUILDERS = [
    header,
    order_count_section,
    single_order_section,
    credit_memo_section,
    order_items_section,
    zero_accounts_section,
    churned_accounts_section,
]


def build_all(metrics):
    """Poskladá HTML všetkých sekcií a zoznam grafov."""
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
