# -*- coding: utf-8 -*-
"""Koncentrácia portfólia a rozdelenie trhov."""

import numpy as np
import pandas as pd

from src import constants as C
import data


# ── koncentrácia ──────────────────────────────────────────────────────────────
def gini_coefficient(values):
    """Gini koeficient nerovnosti (0 = rovnomerné, 1 = všetko u jedného)."""
    sorted_values = np.sort(np.asarray(values, dtype=float))
    count = len(sorted_values)
    ranks = np.arange(1, count + 1)
    weighted_sum = np.sum(ranks * sorted_values)
    return (2 * weighted_sum / (count * sorted_values.sum())) - (count + 1) / count


def concentration_by_year(df):
    """Podiely top N zákazníkov, HHI a Gini pre každý rok."""
    rows = []
    for year in data.trend_years(df):
        customer_gmv = df.loc[df["year"] == year].groupby("cust")["gmv"].sum()
        rows.append(_concentration_row(year, customer_gmv))
    return pd.DataFrame(rows).set_index("year")


def _concentration_row(year, customer_gmv):
    """Metriky koncentrácie pre jeden rok."""
    sorted_gmv = customer_gmv.sort_values(ascending=False)
    shares = sorted_gmv / sorted_gmv.sum()

    row = {
        "year": year,
        "label": data.year_label(year),
        "customers": len(sorted_gmv),
        "gmv": sorted_gmv.sum(),
        "hhi": (shares ** 2).sum() * 10000,
        "gini": gini_coefficient(sorted_gmv.values),
    }
    for level in C.TOP_N_LEVELS:
        row[f"top{level}_pct"] = shares.iloc[:level].sum() * 100

    cumulative = shares.cumsum()
    row["customers_for_50pct"] = int((cumulative < 0.50).sum() + 1)
    row["customers_for_80pct"] = int((cumulative < 0.80).sum() + 1)
    return row


def portfolio_structure(df, year):
    """Podiel zákazníkov a podiel GMV podľa veľkostného pásma v danom roku."""
    customer_gmv = df.loc[df["year"] == year].groupby("cust")["gmv"].sum()
    bands = data.assign_bands(customer_gmv, C.PORTFOLIO_EDGES, C.PORTFOLIO_LABELS)

    rows = []
    for label in C.PORTFOLIO_LABELS:
        members = customer_gmv.loc[bands == label]
        rows.append({
            "band": label,
            "customers": len(members),
            "gmv": members.sum(),
        })

    result = pd.DataFrame(rows).set_index("band")
    result["customer_pct"] = result["customers"] / result["customers"].sum() * 100
    result["gmv_pct"] = result["gmv"] / result["gmv"].sum() * 100
    return result


# ── trhy ──────────────────────────────────────────────────────────────────────
def gmv_by_market_and_year(df):
    """GMV podľa vykazovaného trhu a roku."""
    years = data.trend_years(df)

    rows = []
    for market in C.MARKET_ORDER:
        market_orders = df.loc[df["market"] == market]
        row = {"market": market}
        for year in years:
            row[data.year_label(year)] = market_orders.loc[market_orders["year"] == year, "gmv"].sum()
        rows.append(row)

    return pd.DataFrame(rows).set_index("market")


def market_summary(df):
    """Prehľad trhov za nekompletný rok: GMV, zákazníci, hodnota objednávky, rast."""
    current = _same_period_gmv(df, C.PARTIAL_YEAR)
    previous = _same_period_gmv(df, C.PARTIAL_YEAR - 1)
    partial_year_orders = df.loc[df["year"] == C.PARTIAL_YEAR]

    rows = []
    for market in C.MARKET_ORDER:
        market_orders = partial_year_orders.loc[partial_year_orders["market"] == market]
        customers = market_orders["cust"].nunique()
        rows.append({
            "market": market,
            "gmv": current.get(market, 0.0),
            "orders": len(market_orders),
            "customers": customers,
            "mean_order": market_orders["gmv"].mean(),
            "median_order": market_orders["gmv"].median(),
            "gmv_per_customer": _safe_divide(current.get(market, 0.0), customers),
            "growth_pct": _growth_pct(previous.get(market, 0.0), current.get(market, 0.0)),
        })

    result = pd.DataFrame(rows).set_index("market")
    result["share_pct"] = result["gmv"] / result["gmv"].sum() * 100
    return result.sort_values("gmv", ascending=False)


def _same_period_gmv(df, year):
    """GMV podľa trhu za mesiace 1..PARTIAL_YEAR_LAST_MONTH daného roku."""
    in_year = df["year"] == year
    in_months = df["created_at"].dt.month <= C.PARTIAL_YEAR_LAST_MONTH
    subset = df.loc[in_year & in_months]
    return subset.groupby("market")["gmv"].sum()


def _growth_pct(previous, current):
    """Medziročný rast v %. Ak vlani nebolo GMV, rast sa nedá vyčísliť."""
    if previous == 0:
        return np.nan
    return (current / previous - 1) * 100


def _safe_divide(numerator, denominator):
    """Delenie, ktoré pri nulovom menovateli vráti NaN namiesto výnimky."""
    if denominator == 0:
        return np.nan
    return numerator / denominator


def market_growth_for_chart(df):
    """Medziročný rast trhov, zoradený pre graf."""
    summary = market_summary(df)
    result = summary.loc[summary["growth_pct"].notna(), ["growth_pct", "gmv"]]
    return result.sort_values("growth_pct")
