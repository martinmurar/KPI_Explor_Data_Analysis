# -*- coding: utf-8 -*-
"""Trend GMV, sezónnosť a hodnota objednávky."""

import pandas as pd

from src import constants as C
import data


def monthly_gmv(df):
    """Mesačné GMV s klzavým priemerom.

    Vracia DataFrame indexovaný mesiacom so stĺpcami gmv a moving_average,
    zoradený od C.DISPLAY_START_YEAR. Klzavý priemer sa počíta z dát od
    FIRST_TREND_YEAR (aj spred DISPLAY_START_YEAR), aby mal prvý zobrazený
    mesiac plnú 12-mesačnú históriu — bez toho by v grafe pred začiatkom
    trendovej čiary zbytočne trčala medzera.
    """
    monthly = df.loc[df["year"] >= C.FIRST_TREND_YEAR].groupby("month")["gmv"].sum()
    table = pd.DataFrame({"gmv": monthly})
    table["moving_average"] = monthly.rolling(C.MOVING_AVERAGE_MONTHS).mean()
    table = table.dropna(subset=["moving_average"])
    return table.loc[table.index.year >= C.DISPLAY_START_YEAR]


def seasonality(df):
    """Priemerný podiel mesiaca na ročnom GMV, len z kompletných rokov."""
    first_year, last_year = C.SEASONALITY_YEARS
    in_range = (df["year"] >= first_year) & (df["year"] <= last_year)
    subset = df.loc[in_range]

    shares = []
    for year in range(first_year, last_year + 1):
        year_orders = subset.loc[subset["year"] == year]
        by_month = year_orders.groupby(year_orders["created_at"].dt.month)["gmv"].sum()
        shares.append(by_month / by_month.sum() * 100)

    return pd.concat(shares, axis=1).mean(axis=1)


def seasonality_customers(df):
    """Počet zákazníkov, z ktorých je spočítaný sezónny profil."""
    first_year, last_year = C.SEASONALITY_YEARS
    in_range = (df["year"] >= first_year) & (df["year"] <= last_year)
    return int(df.loc[in_range, "cust"].nunique())


def yearly_summary(df):
    """Ročný prehľad: objednávky, GMV, zákazníci, hodnota objednávky."""
    rows = []
    for year in data.trend_years(df):
        year_orders = df.loc[df["year"] == year]
        rows.append({
            "year": year,
            "label": data.year_label(year),
            "orders": len(year_orders),
            "gmv": year_orders["gmv"].sum(),
            "customers": year_orders["cust"].nunique(),
            "mean_order": year_orders["gmv"].mean(),
            "median_order": year_orders["gmv"].median(),
            "p95_order": year_orders["gmv"].quantile(0.95),
        })

    table = pd.DataFrame(rows).set_index("year")
    table["orders_per_customer"] = table["orders"] / table["customers"]
    table["gmv_per_customer"] = table["gmv"] / table["customers"]
    table["mean_to_median"] = table["mean_order"] / table["median_order"]
    return table


def yearly_yoy_growth(df):
    """Medziročný rast GMV v %. Nekompletný rok sa porovnáva rovnakým oknom."""
    rows = []
    for year in data.trend_years(df):
        if year - 1 < C.FIRST_TREND_YEAR:
            continue
        previous = _comparable_gmv(df, year - 1, year)
        current = _comparable_gmv(df, year, year)
        if previous == 0:
            continue
        rows.append({
            "year": year,
            "label": data.year_label(year),
            "growth_pct": (current / previous - 1) * 100,
        })
    return pd.DataFrame(rows).set_index("year")


def _comparable_gmv(df, year, reference_year):
    """GMV roku, orezané na rovnaké mesiace ako referenčný rok.

    Ak je referenčný rok nekompletný, oreže sa aj porovnávaný rok — inak by
    sa čiastočný rok porovnával s celým.
    """
    year_orders = df.loc[df["year"] == year]
    if reference_year == C.PARTIAL_YEAR:
        months = year_orders["created_at"].dt.month
        year_orders = year_orders.loc[months <= C.PARTIAL_YEAR_LAST_MONTH]
    return year_orders["gmv"].sum()


def order_value_distribution(df):
    """Priemer, medián a p95 hodnoty objednávky po rokoch."""
    summary = yearly_summary(df)
    return summary[["label", "mean_order", "median_order", "p95_order", "mean_to_median"]]


def interpurchase_gap(df):
    """Medián a priemer dní medzi po sebe idúcimi objednávkami, po rokoch."""
    ordered = df.sort_values(["cust", "created_at"])
    ordered = ordered.copy()
    ordered["gap_days"] = ordered.groupby("cust")["created_at"].diff().dt.days
    with_gap = ordered.dropna(subset=["gap_days"])
    return with_gap.groupby("year")["gap_days"].agg(median="median", mean="mean", count="size")
