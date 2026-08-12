# -*- coding: utf-8 -*-
"""Diagnostika interného KPI account growth — prečo je nízke a čo ho posunie.

Tento modul nepočíta KPI, to robí metrics_account_growth. Odpovedá na inú
otázku: ktorá časť odstupu od cieľa je vlastnosť biznisu a ktorá je vlastnosť
definície metriky.

Všetko vychádza z jednej tabuľky metrics_account_growth.account_table, takže
každé číslo tu je konzistentné s tým, čo vykazuje hlavný report.

Scenáre v tomto module sú kontrafaktuálna aritmetika, nie prognózy. Ukazujú,
koľko priestoru v KPI leží v danom mechanizme, nie koľko sa z neho získa.
"""

import pandas as pd

from src import constants as C
import data
import metrics_bridge


# Popisky skupín podľa zmeny počtu objednávok. Poradie je od najlepšej.
FREQUENCY_MORE = "Viac objednávok"
FREQUENCY_SAME = "Rovnaký počet"
FREQUENCY_FEWER = "Menej objednávok"
FREQUENCY_ORDER = [FREQUENCY_MORE, FREQUENCY_SAME, FREQUENCY_FEWER]


# ── 1. frekvencia objednávok ──────────────────────────────────────────────────
def frequency_effect(table):
    """Podiel rastúcich podľa toho, či účet objednal viac/rovnako/menejkrát.

    Len účty aktívne v oboch oknách — pri účte, ktorý v jednom okne nenakúpil,
    je porovnanie počtu objednávok bezobsažné.
    """
    active = _active_in_both(table)
    groups = {
        FREQUENCY_MORE: active["current_orders"] > active["previous_orders"],
        FREQUENCY_SAME: active["current_orders"] == active["previous_orders"],
        FREQUENCY_FEWER: active["current_orders"] < active["previous_orders"],
    }

    rows = []
    for label in FREQUENCY_ORDER:
        rows.append(_frequency_row(label, active.loc[groups[label]]))
    return pd.DataFrame(rows).set_index("segment")


def _active_in_both(table):
    """Účty s nenulovým GMV v oboch oknách."""
    return table.loc[(table["previous"] > 0) & (table["current"] > 0)]


def kpi_by_order_count(table, df):
    """KPI počítané osobitne pre každý kôš podľa počtu objednávok za rok.

    Kôš určuje počet objednávok za posledných FREQUENCY_WINDOW_MONTHS mesiacov,
    teda za aktuálne obdobie. Kôš 0 preto vyjde nutne 0 % — kto za rok nenakúpil,
    nemá GMV ani v kratšom okne KPI a je automaticky klesajúci. Nie je to chyba
    rezu, ale jeho hlavný nález: ukazuje, koľko posudzovaných účtov je mŕtvych.
    """
    buckets = _orders_last_year(table, df).map(_order_count_bucket)

    rows = []
    for label in C.KPI_ORDER_COUNT_BUCKETS:
        members = table.loc[buckets == label]
        if len(members) == 0:
            continue
        rows.append(_frequency_row(label, members))
    return pd.DataFrame(rows).set_index("segment")


def _orders_last_year(table, df):
    """Počet objednávok každého posudzovaného účtu za posledný rok."""
    start, end = metrics_bridge.gmv_window(C.AS_OF, C.FREQUENCY_WINDOW_MONTHS)
    window = data.orders_in_window(df, start, end)
    counts = window.groupby("cust").size()
    return counts.reindex(table.index).fillna(0).astype(int)


def _order_count_bucket(count):
    """Popisok koša pre daný počet objednávok.

    KPI_ORDER_COUNT_EDGES sú horné hranice prvých košov; čo sa do žiadnej
    nezmestí, patrí do posledného, otvoreného koša.
    """
    for edge, label in zip(C.KPI_ORDER_COUNT_EDGES, C.KPI_ORDER_COUNT_BUCKETS):
        if count <= edge:
            return label
    return C.KPI_ORDER_COUNT_BUCKETS[-1]


def _frequency_row(label, members):
    """Jeden riadok rezu: počet účtov, podiel rastúcich a netto zmena GMV."""
    return {
        "segment": label,
        "customers": len(members),
        "growing": int(members["growing"].sum()),
        "growing_pct": members["growing"].mean() * 100 if len(members) else float("nan"),
        "net_delta": members["current"].sum() - members["previous"].sum(),
    }


# ── 2. kedy účty naposledy nakúpili ───────────────────────────────────────────
def activity_split(table, df):
    """Všetky posudzované účty rozdelené podľa toho, kedy naposledy nakúpili.

    Churnutý je účet, ktorý nenakúpil KPI_DIAG_CHURN_DAYS dní. Prostredná
    skupina je jadro problému — sú to živé účty, ktoré len netrafili okno, a KPI
    ich aj tak počíta ako klesajúce.
    """
    groups = _activity_groups(table, df)

    rows = []
    for index, label in enumerate(C.KPI_DIAG_ACTIVITY_LABELS):
        members = table.loc[groups[label]]
        rows.append({
            "segment": label,
            "customers": len(members),
            "share_pct": len(members) / len(table) * 100,
            "growing_pct": members["growing"].mean() * 100 if len(members) else 0.0,
            "previous_gmv": members["previous"].sum(),
            "status": index,
        })
    return pd.DataFrame(rows).set_index("segment")


def _activity_groups(table, df):
    """Masky troch skupín posudzovaných účtov podľa poslednej objednávky."""
    in_window = table["current"] > 0
    alive = _alive_mask(table, df)
    return {
        C.KPI_DIAG_ACTIVITY_LABELS[0]: in_window,
        C.KPI_DIAG_ACTIVITY_LABELS[1]: ~in_window & alive,
        C.KPI_DIAG_ACTIVITY_LABELS[2]: ~in_window & ~alive,
    }


def _alive_mask(table, df):
    """Účty, ktoré nakúpili za posledných KPI_DIAG_CHURN_DAYS dní."""
    last_order = data.last_order_per_customer(df, as_of=C.AS_OF).reindex(table.index)
    return last_order >= C.AS_OF - pd.Timedelta(days=C.KPI_DIAG_CHURN_DAYS)


def outside_window_accounts(table, df):
    """Živé účty, ktoré v aktuálnom okne nenakúpili."""
    return table.loc[(table["current"] == 0) & _alive_mask(table, df)]


def churned_accounts(table, df):
    """Churnuté účty medzi posudzovanými."""
    return table.loc[(table["current"] == 0) & ~_alive_mask(table, df)]


def regular_ordering_scenario(table, df):
    """KPI dnes vs KPI, keby živé účty objednávali aspoň raz za okno.

    Živý účet s nulovým GMV v aktuálnom okne sa v scenári počíta ako rastúci.
    Je to horná hranica — účet, ktorý začne objednávať, je rastúci len ak
    prekročí svoje minuloročné GMV, a všetky tieto účty ho majú nenulové.
    """
    converted = len(outside_window_accounts(table, df))
    scenario_growing = table["growing"].sum() + converted
    return _scenario_table(table, C.KPI_DIAG_REGULAR_LABELS,
                           scenario_growing, converted)


# ── 3. čo ak by sme zabránili churnu ──────────────────────────────────────────
def churn_prevented_sensitivity(table, df):
    """KPI, keby churnuté účty boli aktívne v okne, pri troch predpokladoch rastu.

    Skúša sa KPI_DIAG_CHURN_PROBABILITIES — od 0 (zachránený účet nikdy
    nerastie, teda dnešný stav) po 1 (rastie vždy). Nepoužíva sa náhodná
    simulácia, počíta sa priamo očakávaná hodnota.

    Posudzovaná skupina sa nemení — churnuté účty v nej už sú, mení sa len to, či sa
    počítajú ako rastúce.
    """
    prevented = len(churned_accounts(table, df))
    growing = table["growing"].sum()

    rows = []
    for probability in C.KPI_DIAG_CHURN_PROBABILITIES:
        rows.append({
            "segment": _probability_label(probability),
            "probability_pct": probability * 100,
            "customers": len(table),
            "growing_pct": (growing + prevented * probability) / len(table) * 100,
        })
    result = pd.DataFrame(rows).set_index("segment")
    result["prevented"] = prevented
    return result


def _probability_label(probability):
    """Popisok scenára podľa predpokladanej pravdepodobnosti rastu."""
    percent = int(round(probability * 100))
    if probability == 0:
        return f"{percent} % — dnešný stav"
    return f"{percent} % zachránených rastie"
def _scenario_table(table, labels, scenario_growing, converted):
    """Dvojriadková tabuľka: KPI dnes a KPI v scenári.

    Posudzovaná skupina sa v scenári nemení — účty v nej už sú, mení sa len
    to, či sa počítajú ako rastúce.
    """
    rows = [
        {"segment": labels[0],
         "customers": len(table),
         "growing_pct": table["growing"].mean() * 100},
        {"segment": labels[1],
         "customers": len(table),
         "growing_pct": scenario_growing / len(table) * 100},
    ]
    result = pd.DataFrame(rows).set_index("segment")
    result["converted"] = converted
    return result


# ── zhrnutie pre karty a text ─────────────────────────────────────────────────
def diagnostics_summary(table, df):
    """Čísla, na ktoré sa odvoláva text sekcií."""
    in_window = table.loc[table["current"] > 0]
    both = _active_in_both(table)

    return {
        "growing_pct": table["growing"].mean() * 100,
        "active_in_both_growing_pct": both["growing"].mean() * 100,
        "accounts": len(table),
        "growing": int(table["growing"].sum()),
        "gmv_growing_pct": table.loc[table["growing"], "current"].sum()
                           / table["current"].sum() * 100,
        "thin_pct": _thin_share(table),
        "in_window": len(in_window),
        "in_window_growing_pct": in_window["growing"].mean() * 100,
        "outside_window": len(outside_window_accounts(table, df)),
        "churned": len(churned_accounts(table, df)),
        "cannot_grow": len(table.loc[table["current"] == 0]),
    }


def _thin_share(table):
    """Podiel posudzovaných účtov s najviac KPI_DIAG_THIN_ORDERS objednávkami v oboch oknách."""
    limit = C.KPI_DIAG_THIN_ORDERS
    thin = table.loc[(table["previous_orders"] <= limit) & (table["current_orders"] <= limit)]
    return len(thin) / len(table) * 100
