# -*- coding: utf-8 -*-
"""Rozklad medziročnej zmeny GMV na komponenty (bridge).

Komponenty na úrovni zákazníka:
    new         — nula v porovnávacom období A prvá objednávka v aktuálnom období
    reactivated — nula v porovnávacom období, ale nakupoval už predtým
    expansion   — aktívny v oboch obdobiach, teraz viac
    contraction — aktívny v oboch obdobiach, teraz menej (ale nie nula)
    churn       — aktívny v porovnávacom období, teraz nula

Komponenty sú vzájomne vylučujúce a ich súčet sa presne rovná celkovej zmene.
"""

import numpy as np
import pandas as pd

from src import constants as C
import data


def customer_comparison(df, current_start, current_end):
    """Tabuľka zákazník × (previous, current, first_order, delta, component)."""
    previous_start = current_start - pd.DateOffset(years=1)
    previous_end = current_end - pd.DateOffset(years=1)

    current = data.gmv_per_customer(df, current_start, current_end)
    previous = data.gmv_per_customer(df, previous_start, previous_end)

    table = pd.DataFrame({"previous": previous, "current": current}).fillna(0.0)
    table["first_order"] = data.first_order_per_customer(df)
    table["delta"] = table["current"] - table["previous"]
    table["component"] = _classify(table, current_start)
    return table


def _classify(table, current_start):
    """Priradí každému zákazníkovi komponentu zmeny."""
    is_new = (table["previous"] == 0) & (table["current"] > 0) & (table["first_order"] >= current_start)
    is_reactivated = (table["previous"] == 0) & (table["current"] > 0) & (table["first_order"] < current_start)
    is_expansion = (table["previous"] > 0) & (table["current"] > table["previous"])
    is_contraction = (table["previous"] > 0) & (table["current"] < table["previous"]) & (table["current"] > 0)
    is_churn = (table["previous"] > 0) & (table["current"] == 0)

    conditions = [is_new, is_reactivated, is_expansion, is_contraction, is_churn]
    names = ["new", "reactivated", "expansion", "contraction", "churn"]
    return pd.Series(np.select(conditions, names, default="flat"), index=table.index)


def bridge_for_period(df, current_start, current_end):
    """Agregovaný bridge pre jedno obdobie: sumy delt a počty zákazníkov."""
    table = customer_comparison(df, current_start, current_end)

    result = {
        "previous_gmv": table["previous"].sum(),
        "current_gmv": table["current"].sum(),
        "customers_previous": int((table["previous"] > 0).sum()),
        "customers_current": int((table["current"] > 0).sum()),
    }
    for component in C.BRIDGE_COMPONENTS:
        members = table.loc[table["component"] == component]
        result[component] = members["delta"].sum()
        result[f"n_{component}"] = len(members)

    result["delta"] = result["current_gmv"] - result["previous_gmv"]
    return result


def yearly_bridge(df):
    """Bridge po kalendárnych rokoch.

    Nekompletný rok sa porovnáva rovnakým oknom (Jan–Júl vs Jan–Júl), inak by
    sa čiastočný rok porovnával s celým.
    """
    rows = []
    for year in data.trend_years(df):
        # Rok 2019 sa nedá porovnať s pilotným 2018.
        if year - 1 < C.FIRST_TREND_YEAR:
            continue
        start, end = _year_window(year)
        row = bridge_for_period(df, start, end)
        row["year"] = year
        row["label"] = data.year_label(year)
        rows.append(row)

    table = pd.DataFrame(rows).set_index("year")
    _assert_components_sum_to_delta(table)
    return table


def _year_window(year):
    """Interval [start, end) pre daný rok, orezaný ak je rok nekompletný."""
    start = pd.Timestamp(year=year, month=1, day=1)
    if year == C.PARTIAL_YEAR:
        end = pd.Timestamp(year=year, month=C.PARTIAL_YEAR_LAST_MONTH + 1, day=1)
    else:
        end = pd.Timestamp(year=year + 1, month=1, day=1)
    return start, end


def _assert_components_sum_to_delta(table):
    """Kontrola, že komponenty sú vzájomne vylučujúce a nič nechýba."""
    components_sum = table[C.BRIDGE_COMPONENTS].sum(axis=1)
    if not np.allclose(components_sum, table["delta"]):
        raise AssertionError("komponenty bridge sa nesčítajú do celkovej zmeny")


def gmv_window(as_of, months):
    """Interval [start, end) končiaci dňom as_of a dlhý `months` mesiacov."""
    end = as_of + pd.Timedelta(days=1)
    start = end - pd.DateOffset(months=months)
    return start, end
