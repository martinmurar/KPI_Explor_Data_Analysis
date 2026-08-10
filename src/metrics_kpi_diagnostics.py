# -*- coding: utf-8 -*-
"""Diagnostika interného KPI account growth — prečo je nízke a čo ho posunie.

Tento modul nepočíta KPI, to robí metrics_account_growth. Odpovedá na inú
otázku: ktorá časť 18-bodového odstupu od cieľa je vlastnosť biznisu a ktorá
je vlastnosť definície metriky.

Všetko vychádza z jednej tabuľky metrics_account_growth.account_table, takže
každé číslo tu je konzistentné s tým, čo vykazuje hlavný report.
"""

import numpy as np
import pandas as pd

from src import constants as C
import data
import metrics_account_growth


# Popisky skupín podľa zmeny počtu objednávok. Poradie je od najlepšej.
FREQUENCY_MORE = "Viac objednávok"
FREQUENCY_SAME = "Rovnaký počet"
FREQUENCY_FEWER = "Menej objednávok"
FREQUENCY_ORDER = [FREQUENCY_MORE, FREQUENCY_SAME, FREQUENCY_FEWER]

# Popisky variantov v teste okno vs populácia.
WINDOW_SHORT = "Krátke okno, vlastný menovateľ"
WINDOW_LONG_SAME = "Dlhé okno, len tie isté účty"
WINDOW_LONG = "Dlhé okno, vlastný menovateľ"
WINDOW_LONG_EXTRA = "Účty, ktoré pridá až dlhé okno"
WINDOW_ORDER = [WINDOW_SHORT, WINDOW_LONG_SAME, WINDOW_LONG, WINDOW_LONG_EXTRA]

# Popisky scenárov v grafe aritmetickej steny.
WALL_TODAY = "Dnes"
WALL_ZERO_CHURN = "Scenár nulový churn"
WALL_TARGET = "Cieľ"
WALL_ORDER = [WALL_TODAY, WALL_ZERO_CHURN, WALL_TARGET]


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
        rows.append(_segment_row(label, active.loc[groups[label]]))
    return pd.DataFrame(rows).set_index("segment")


def _active_in_both(table):
    """Účty s nenulovým GMV v oboch oknách."""
    return table.loc[(table["previous"] > 0) & (table["current"] > 0)]


def _segment_row(label, members):
    """Jeden riadok rezu: počet účtov, podiel rastúcich a netto zmena GMV."""
    return {
        "segment": label,
        "customers": len(members),
        "growing": int(members["growing"].sum()),
        "growing_pct": members["growing"].mean() * 100 if len(members) else float("nan"),
        "net_delta": members["current"].sum() - members["previous"].sum(),
    }


# ── 2. padnuté účty: mŕtve alebo len mimo okna ────────────────────────────────
def dropped_recency(table, df):
    """Účty s nulovým GMV v aktuálnom okne, rozdelené podľa poslednej objednávky.

    Účet, ktorý nakúpil po skončení minuloročného okna, nie je churnutý — len
    neobjednal práve v porovnávanom okne. KPI ho aj tak počíta ako klesajúci.
    """
    dropped = table.loc[table["current"] == 0]
    last_order = data.last_order_per_customer(df, as_of=C.AS_OF).reindex(dropped.index)
    recent_cutoff = C.AS_OF - pd.DateOffset(months=C.KPI_DIAG_RECENT_MONTHS)
    alive_cutoff = _alive_cutoff()

    groups = {
        C.KPI_DIAG_RECENCY_LABELS[0]: last_order >= recent_cutoff,
        C.KPI_DIAG_RECENCY_LABELS[1]: (last_order < recent_cutoff) & (last_order >= alive_cutoff),
        C.KPI_DIAG_RECENCY_LABELS[2]: last_order < alive_cutoff,
    }

    rows = []
    for label in C.KPI_DIAG_RECENCY_LABELS:
        members = dropped.loc[groups[label]]
        rows.append({
            "segment": label,
            "customers": len(members),
            "previous_gmv": members["previous"].sum(),
            "is_alive": label != C.KPI_DIAG_RECENCY_LABELS[-1],
        })
    return pd.DataFrame(rows).set_index("segment")


def _alive_cutoff():
    """Koniec minuloročného okna. Kto nakúpil po ňom, je preukázateľne živý."""
    _, current_end = _gmv_window()
    return current_end - pd.DateOffset(years=1)


def _gmv_window():
    """Aktuálne porovnávacie okno KPI."""
    import metrics_bridge
    return metrics_bridge.gmv_window(C.AS_OF, C.GMV_WINDOW_MONTHS)


def alive_effect(table, df):
    """KPI ako sa vykazuje vs KPI bez živých účtov mimo okna."""
    last_order = data.last_order_per_customer(df, as_of=C.AS_OF).reindex(table.index)
    alive_outside = (table["current"] == 0) & (last_order >= _alive_cutoff())
    kept = table.loc[~alive_outside]

    rows = [
        {"segment": C.KPI_DIAG_ALIVE_LABELS[0],
         "customers": len(table), "growing_pct": table["growing"].mean() * 100},
        {"segment": C.KPI_DIAG_ALIVE_LABELS[1],
         "customers": len(kept), "growing_pct": kept["growing"].mean() * 100},
    ]
    result = pd.DataFrame(rows).set_index("segment")
    result["excluded"] = int(alive_outside.sum())
    return result


# ── 3. šum z časovania objednávok ─────────────────────────────────────────────
def monthly_noise(df):
    """To isté KPI merané s oknom posunutým po mesiacoch.

    Rozptyl týchto meraní je dolná hranica šumu metriky — biznis sa medzi
    dvoma susednými mesiacmi nemení tak, ako sa mení toto číslo.
    """
    rows = []
    for month_end in _noise_points():
        table = metrics_account_growth.account_table(df, month_end)
        rows.append({
            "date": month_end,
            "growing_pct": table["growing"].mean() * 100,
            "accounts": len(table),
        })
    return pd.DataFrame(rows).set_index("date")


def _noise_points():
    """Konce mesiacov v okne šumu, od najstaršieho."""
    offset = pd.DateOffset(months=C.KPI_DIAG_NOISE_MONTHS - 1)
    start = (C.AS_OF - offset) + pd.offsets.MonthEnd(0)
    return pd.date_range(start=start, end=C.AS_OF, freq="ME")


# ── 4. dĺžka okna: meranie alebo populácia ────────────────────────────────────
def window_vs_population(df):
    """Rozloží efekt dlhšieho okna na efekt merania a efekt populácie.

    Ak dlhé okno pustím na tých istých účtoch, vidím čistý efekt merania.
    Rozdiel voči vlastnému menovateľu dlhého okna je efekt populácie.
    """
    short = metrics_account_growth.account_table(df, C.AS_OF)
    long = metrics_account_growth.account_table(
        df, C.AS_OF, window_months=C.KPI_DIAG_LONG_WINDOW_MONTHS)
    long_same = long.loc[long.index.intersection(short.index)]
    long_extra = long.loc[long.index.difference(short.index)]

    variants = {
        WINDOW_SHORT: short,
        WINDOW_LONG_SAME: long_same,
        WINDOW_LONG: long,
        WINDOW_LONG_EXTRA: long_extra,
    }

    rows = []
    for label in WINDOW_ORDER:
        members = variants[label]
        rows.append({
            "segment": label,
            "customers": len(members),
            "growing_pct": members["growing"].mean() * 100,
        })
    return pd.DataFrame(rows).set_index("segment")


# ── 5. distribúcia medziročnej zmeny ──────────────────────────────────────────
def change_histogram(table):
    """Rozdelenie medziročnej zmeny GMV u účtov aktívnych v oboch oknách.

    Krajné hodnoty sú orezané na hranice krajných košov, aby jeden účet
    s rastom o tisíce percent nezdeformoval os.
    """
    active = _active_in_both(table)
    edges = C.KPI_DIAG_CHANGE_EDGES
    change = ((active["current"] / active["previous"] - 1) * 100).clip(edges[0], edges[-1])

    rows = []
    for index in range(len(edges) - 1):
        low, high = edges[index], edges[index + 1]
        if index == 0:
            members = change.loc[change <= high]
        else:
            members = change.loc[(change > low) & (change <= high)]
        rows.append({
            "segment": _change_bin_label(low, high),
            "customers": len(members),
            "is_positive": low >= 0,
        })
    result = pd.DataFrame(rows).set_index("segment")
    result["median_change_pct"] = change.median()
    return result


def _change_bin_label(low, high):
    """Popisok koša histogramu, napríklad „−25 až −10“."""
    return f"{_signed(low)} až {_signed(high)}"


def _signed(value):
    """Číslo so znamienkom a s pomlčkou namiesto mínusu."""
    if value < 0:
        return "−" + str(abs(int(value)))
    return "+" + str(int(value))


# ── 6. aritmetická stena ──────────────────────────────────────────────────────
def retention_wall(table):
    """KPI dnes, pri nulovom churne a cieľ.

    Scenár nulový churn: ani jeden účet nespadol do nuly a všetky sa chovajú
    ako priemerný účet aktívny v oboch oknách. Je to horná hranica toho, čo sa
    dá dosiahnuť čistou retenciou.
    """
    scenarios = {
        WALL_TODAY: table["growing"].mean() * 100,
        WALL_ZERO_CHURN: _zero_churn_pct(table),
        WALL_TARGET: float(C.ACCOUNT_GROWTH_TARGET_PCT),
    }

    rows = []
    for label in WALL_ORDER:
        rows.append({"segment": label, "growing_pct": scenarios[label],
                     "customers": len(table)})
    return pd.DataFrame(rows).set_index("segment")


def _zero_churn_pct(table):
    """KPI, keby žiadny účet nespadol do nuly."""
    active = _active_in_both(table)
    reactivated = table.loc[table["previous"] == 0]
    dropped = table.loc[table["current"] == 0]
    growing = len(reactivated) + active["growing"].sum() + _growth_rate(table) * len(dropped)
    return growing / len(table) * 100


def _growth_rate(table):
    """Podiel rastúcich medzi účtami aktívnymi v oboch oknách."""
    return _active_in_both(table)["growing"].mean()


def paths_to_target(table, dormant_count):
    """Tri samostatné cesty k cieľu a to, či na ne vôbec je materiál.

    dormant_count sa predáva zvonku — počet dormantných účtov sa počíta z celého
    df, nie z menovateľa KPI, a nemá zmysel ho tu počítať druhýkrát.
    """
    needed = C.ACCOUNT_GROWTH_TARGET_PCT / 100 * len(table) - table["growing"].sum()
    rate = _growth_rate(table)
    active = _active_in_both(table)
    reactivated = len(table.loc[table["previous"] == 0])

    rows = [
        {"path": C.KPI_DIAG_PATH_LABELS[0],
         "needed": needed / rate,
         "available": float(len(table.loc[table["current"] == 0])),
         "unit": "účtov"},
        {"path": C.KPI_DIAG_PATH_LABELS[1],
         "needed": (C.ACCOUNT_GROWTH_TARGET_PCT / 100 * len(table) - reactivated)
                   / len(active) * 100,
         "available": rate * 100,
         "unit": "% rastúcich"},
        {"path": C.KPI_DIAG_PATH_LABELS[2],
         "needed": float(_reactivations_needed(table["growing"].sum(), len(table))),
         "available": float(dormant_count),
         "unit": "účtov"},
    ]
    result = pd.DataFrame(rows).set_index("path")
    result["feasible"] = result["needed"] <= result["available"]
    return result


def _reactivations_needed(growing, accounts):
    """Koľko reaktivácií dormantných účtov samo o sebe dosiahne cieľ.

    Reaktivovaný účet pridá jeden rastúci účet aj jeden účet do menovateľa,
    takže rovnica nie je lineárna a rieši sa cez podiel.
    """
    target = C.ACCOUNT_GROWTH_TARGET_PCT / 100
    missing = target * accounts - growing
    if missing <= 0:
        return 0
    return int(np.ceil(missing / (1 - target)))


def dormant_accounts(df):
    """Účty, ktoré sú dosť staré na KPI, ale nenakúpili ani v jednom okne.

    Sú to kandidáti na reaktiváciu — do menovateľa dnes nepatria, ale ktorýkoľvek
    z nich sa po jednej objednávke stane rastúcim účtom.
    """
    everyone = metrics_account_growth.account_table(df, C.AS_OF)
    mature = _mature_accounts(df)
    return mature.drop(index=everyone.index, errors="ignore")


def _mature_accounts(df):
    """Účty starší ako vekový filter KPI, bez ohľadu na aktivitu."""
    first_order = data.first_order_per_customer(df)
    cutoff = C.AS_OF - pd.DateOffset(months=C.ACCOUNT_GROWTH_MIN_AGE_MONTHS)
    mature = first_order.loc[first_order <= cutoff]
    return pd.DataFrame({"first_order": mature})


# ── 7. rebrík pák ─────────────────────────────────────────────────────────────
def lever_ladder(table, df):
    """Kumulatívny efekt troch pák na KPI.

    Nie je to prognóza. Je to kontrafaktuálna aritmetika, ktorá ukazuje pomer
    sily pák a to, že reaktivácia je doplnok, nie stratégia.
    """
    growing = float(table["growing"].sum())
    accounts = float(len(table))
    rate = _growth_rate(table)

    steps = [_ladder_step(C.KPI_DIAG_LADDER_LABELS[0], growing, accounts, 0.0)]

    frequency_gain = _frequency_gain(table)
    growing += frequency_gain
    steps.append(_ladder_step(C.KPI_DIAG_LADDER_LABELS[1], growing, accounts, frequency_gain))

    saved = int(len(table.loc[table["current"] == 0]) * C.KPI_DIAG_SAVED_SHARE)
    saved_gain = saved * rate
    growing += saved_gain
    steps.append(_ladder_step(C.KPI_DIAG_LADDER_LABELS[2], growing, accounts, saved_gain))

    reactivations = _reactivations_needed(growing, accounts)
    steps.append(_ladder_step(C.KPI_DIAG_LADDER_LABELS[3], growing + reactivations,
                              accounts + reactivations, reactivations))

    result = pd.DataFrame(steps).set_index("step")
    result["saved"] = saved
    result["reactivations"] = reactivations
    result["fewer_accounts"] = len(_fewer_orders(table))
    return result


def _ladder_step(label, growing, accounts, gain):
    """Jeden krok rebríka."""
    return {"step": label, "growing_pct": growing / accounts * 100, "gain": gain}


def _frequency_gain(table):
    """Koľko rastúcich účtov pridá udržanie frekvencie u účtov, ktoré ju stratili."""
    active = _active_in_both(table)
    fewer = _fewer_orders(table)
    same = active.loc[active["current_orders"] == active["previous_orders"]]
    return len(fewer) * (same["growing"].mean() - fewer["growing"].mean())


def _fewer_orders(table):
    """Účty aktívne v oboch oknách, ktoré objednali menejkrát než pred rokom."""
    active = _active_in_both(table)
    return active.loc[active["current_orders"] < active["previous_orders"]]


# ── zhrnutie pre karty a text ─────────────────────────────────────────────────
def diagnostics_summary(table, df):
    """Čísla, na ktoré sa odvoláva text sekcií."""
    dropped = table.loc[table["current"] == 0]
    fewer = _fewer_orders(table)
    noise = monthly_noise(df)
    lifetime_gmv = df.groupby("cust")["gmv"].sum()
    dormant = dormant_accounts(df)

    return {
        "growing_pct": table["growing"].mean() * 100,
        "accounts": len(table),
        "growing": int(table["growing"].sum()),
        "gmv_growing_pct": table.loc[table["growing"], "current"].sum()
                           / table["current"].sum() * 100,
        "noise_sd": float(noise["growing_pct"].std()),
        "noise_min": float(noise["growing_pct"].min()),
        "noise_max": float(noise["growing_pct"].max()),
        "thin_pct": _thin_share(table),
        "dropped": len(dropped),
        "dropped_gmv": dropped["previous"].sum(),
        "fewer_accounts": len(fewer),
        "fewer_delta": fewer["current"].sum() - fewer["previous"].sum(),
        "dormant": len(dormant),
        "dormant_median_ltv": float(lifetime_gmv.reindex(dormant.index).median()),
        "active_growing_pct": _growth_rate(table) * 100,
    }


def _thin_share(table):
    """Podiel menovateľa, ktorý má v oboch oknách najviac KPI_DIAG_THIN_ORDERS objednávok."""
    limit = C.KPI_DIAG_THIN_ORDERS
    thin = table.loc[(table["previous_orders"] <= limit) & (table["current_orders"] <= limit)]
    return len(thin) / len(table) * 100
