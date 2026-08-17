# -*- coding: utf-8 -*-
"""Interné KPI „account growth“ — podiel účtov s vyššími tržbami než pred rokom.

Definícia zhodná s firemným reportingom:
    GMV účtu za posledné GMV_WINDOW_MONTHS mesiacov sa porovná s GMV za to isté
    okno o rok skôr. Účet rastie, ak je aktuálne GMV vyššie, klesá ak nižšie.

Posudzuje sa účet, ktorý splní dve podmienky:
    1. Účet je starší ako ACCOUNT_GROWTH_MIN_AGE_MONTHS. Hodnota 15 nie je
       náhodná — je to 12 + GMV_WINDOW_MONTHS, teda každý posudzovaný účet mal
       k dispozícii plné minuloročné okno.
    2. Účet bol aktívny aspoň v jednom z dvoch okien. Kto nenakúpil ani v jednom,
       nie je ani rastúci ani klesajúci a do KPI nepatrí.

Vedľa neváženého KPI sa počíta GMV-vážený variant = podiel GMV aktuálneho okna,
ktoré leží v rastúcich účtoch. Ukazuje, či nevážené KPI a tržby hovoria to isté.
"""

import pandas as pd

from src.common import constants as C
from src.common import data
from src.common import metrics_bridge


# Skupiny, na ktoré sa rozpadajú posudzované účty. Prvé dve sú rozhodnuté binárne —
# účet nakúpil alebo nenakúpil — a o rast v nich vôbec nejde.
#
# Prvá skupina sa zámerne nenazýva „reaktivované“. Jediná podmienka je nulové
# GMV v minuloročnom okne, čo o dĺžke medzery nehovorí nič — medián medzery je
# okolo štyroch mesiacov a väčšina týchto účtov nakúpila krátko pred oknom.
COMPOSITION_NO_PREVIOUS = "Bez GMV v minuloročnom okne (0 → +)"
COMPOSITION_DROPPED = "Odišli do nuly (+ → 0)"
COMPOSITION_BOTH = "Aktívne v oboch oknách"
COMPOSITION_ORDER = [COMPOSITION_NO_PREVIOUS, COMPOSITION_DROPPED, COMPOSITION_BOTH]

# ── základná tabuľka ──────────────────────────────────────────────────────────
def account_table(df, as_of, window_months=None, min_age_months=None):
    """Tabuľka posudzovaných účtov s ich GMV v oboch oknách.

    window_months a min_age_months sú parametrizovateľné pre prípadné ad-hoc
    porovnanie s inou definíciou KPI — report už takú tabuľku nemá, ale
    volanie s vlastnými hodnotami funguje. Predvolené hodnoty sú tie firemné.
    """
    if window_months is None:
        window_months = C.GMV_WINDOW_MONTHS
    if min_age_months is None:
        min_age_months = C.ACCOUNT_GROWTH_MIN_AGE_MONTHS

    table = _gmv_comparison(df, as_of, window_months)
    table = _attach_attributes(table, df)
    table = _apply_denominator(table, as_of, min_age_months)
    table["growing"] = table["current"] > table["previous"]
    table["declining"] = table["current"] < table["previous"]
    return table


def _gmv_comparison(df, as_of, window_months):
    """GMV a počet objednávok každého účtu v aktuálnom a minuloročnom okne."""
    current_start, current_end = metrics_bridge.gmv_window(as_of, window_months)
    previous_start = current_start - pd.DateOffset(years=1)
    previous_end = current_end - pd.DateOffset(years=1)

    table = pd.DataFrame({
        "previous": data.gmv_per_customer(df, previous_start, previous_end),
        "current": data.gmv_per_customer(df, current_start, current_end),
        "previous_orders": _order_count(df, previous_start, previous_end),
        "current_orders": _order_count(df, current_start, current_end),
    })
    all_accounts = pd.Index(df["cust"].unique(), name="cust")
    return table.reindex(all_accounts).fillna(0.0)


def _order_count(df, start, end):
    """Počet objednávok každého účtu v intervale [start, end)."""
    window = data.orders_in_window(df, start, end)
    return window.groupby("cust").size()


def _attach_attributes(table, df):
    """Doplní atribúty účtu použité v rezoch."""
    table = table.copy()
    table["first_order"] = data.first_order_per_customer(df)
    table["cohort_year"] = table["first_order"].dt.year
    table["country"] = _latest_value_per_customer(df, "country")
    table["customer_group_id"] = _latest_value_per_customer(df, "customer_group_id")
    return table


def _latest_value_per_customer(df, column):
    """Hodnota stĺpca z najnovšej objednávky účtu.

    Krajina ani skupina nie sú v dátach na úrovni zákazníka, len na objednávke,
    a v čase sa môžu zmeniť. Berie sa posledný stav.
    """
    ordered = df.sort_values("created_at")
    return ordered.groupby("cust")[column].last()


def _apply_denominator(table, as_of, min_age_months):
    """Nechá len účty, ktoré sa do KPI posudzujú."""
    age_cutoff = as_of - pd.DateOffset(months=min_age_months)
    is_mature = table["first_order"] <= age_cutoff
    is_active = (table["previous"] > 0) | (table["current"] > 0)
    return table.loc[is_mature & is_active].copy()


# ── prehľadové čísla ──────────────────────────────────────────────────────────
def kpi_summary(table):
    """Hlavné čísla KPI k jednému dátumu."""
    accounts = len(table)
    growing = int(table["growing"].sum())
    needed = _accounts_needed_for_target(accounts, growing)
    return {
        "accounts": accounts,
        "growing": growing,
        "growing_pct": growing / accounts * 100,
        "declining_pct": table["declining"].sum() / accounts * 100,
        "gmv_growing_pct": _gmv_growing_pct(table),
        "accounts_needed_for_target": needed,
    }


def _accounts_needed_for_target(accounts, growing):
    """Koľko ďalších rastúcich účtov treba na dosiahnutie cieľa."""
    target_count = accounts * C.ACCOUNT_GROWTH_TARGET_PCT / 100
    missing = target_count - growing
    if missing <= 0:
        return 0
    return int(missing) + 1


def _gmv_growing_pct(table):
    """Podiel GMV aktuálneho okna, ktoré leží v rastúcich účtoch."""
    total = table["current"].sum()
    if total == 0:
        return float("nan")
    return table.loc[table["growing"], "current"].sum() / total * 100


# ── rozklad posudzovaných účtov ───────────────────────────────────────────────
def composition(table):
    """Rozdelí posudzované účty na tri skupiny podľa aktivity v oknách."""
    groups = {
        COMPOSITION_NO_PREVIOUS: table.loc[table["previous"] == 0],
        COMPOSITION_DROPPED: table.loc[table["current"] == 0],
        COMPOSITION_BOTH: table.loc[(table["previous"] > 0) & (table["current"] > 0)],
    }

    rows = []
    for label in COMPOSITION_ORDER:
        rows.append(_composition_row(label, groups[label], len(table)))
    return pd.DataFrame(rows).set_index("group")


def _composition_row(label, members, total_accounts):
    """Jeden riadok rozkladu posudzovaných účtov."""
    growing = int(members["growing"].sum())
    return {
        "group": label,
        "customers": len(members),
        "share_pct": len(members) / total_accounts * 100,
        "growing": growing,
        "declining": len(members) - growing,
        "growing_pct": growing / len(members) * 100 if len(members) else float("nan"),
        "previous_gmv": members["previous"].sum(),
        "current_gmv": members["current"].sum(),
    }


# ── KPI v čase ────────────────────────────────────────────────────────────────
def history(df):
    """KPI v kvartálnych bodoch, vždy rovnakou definíciou."""
    rows = []
    for quarter_end in _history_points():
        table = account_table(df, quarter_end)
        summary = kpi_summary(table)
        summary["date"] = quarter_end
        rows.append(summary)
    return pd.DataFrame(rows).set_index("date")


def _history_points():
    """Konce kvartálov od začiatku histórie KPI do dátumu AS_OF."""
    return pd.date_range(start=C.ACCOUNT_GROWTH_HISTORY_START, end=C.AS_OF, freq="3ME")