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