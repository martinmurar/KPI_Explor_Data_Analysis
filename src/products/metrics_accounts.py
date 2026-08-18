# -*- coding: utf-8 -*-
"""Rezy nad položkami objednávok podľa účtu.

Zužovanie sortimentu pred odchodom a závislosť účtu na jedinom produkte.
Oboje stojí na jednej tabuľke položiek doplnenej o zákazníka a dátum
objednávky.
"""

import pandas as pd

from src.common import constants as C
from src.common import data


def with_orders(items, df):
    """Položky doplnené o zákazníka a dátum objednávky."""
    orders = df[["increment_id", "cust", "created_at"]].drop_duplicates("increment_id")
    return items.merge(orders, on="increment_id", how="inner")


# ── zužovanie sortimentu pred odchodom ────────────────────────────────────────
def assortment_before_end(joined, accounts, reference_dates):
    """Priemerný počet rôznych produktov v oknách pred referenčným dátumom.

    Referenčným dátumom je posledná objednávka účtu pri odídených a C.AS_OF pri
    tých, čo nakupujú ďalej. Vďaka tomu sa obe skupiny porovnávajú na rovnakej
    časovej škále — „tri mesiace pred koncom“ proti „posledné tri mesiace“.
    """
    window = joined.loc[joined["cust"].isin(accounts)].copy()
    window["reference"] = window["cust"].map(reference_dates)
    window["months_before"] = ((window["reference"] - window["created_at"]).dt.days
                               / 30.44)

    rows = []
    for start in C.NARROWING_WINDOWS_MONTHS:
        end = start - 3
        inside = window.loc[(window["months_before"] > end)
                            & (window["months_before"] <= start)]
        per_account = inside.groupby("cust")["sku"].nunique().reindex(accounts).fillna(0)
        rows.append({
            "segment": f"{start}–{end} mes. pred koncom" if end else "posledné 3 mes.",
            "products": per_account.mean(),
            "accounts": int((per_account > 0).sum()),
        })
    return pd.DataFrame(rows).set_index("segment")


def last_order_dates(df, accounts):
    """Dátum poslednej objednávky pre zadané účty."""
    return data.last_order_per_customer(df).reindex(accounts)


# ── závislosť účtu na jedinom produkte ────────────────────────────────────────
def account_dependence(joined):
    """Pre každý dosť veľký účet podiel jeho najsilnejšieho produktu na GMV."""
    account_gmv = joined.groupby("cust")["gmv"].sum()
    big = account_gmv.index[account_gmv >= C.PRODUCT_MIN_ACCOUNT_GMV]

    subset = joined.loc[joined["cust"].isin(big)]
    by_product = subset.groupby(["cust", "sku"])["gmv"].sum()
    top_product = by_product.groupby("cust").max()

    result = pd.DataFrame({"gmv": account_gmv.reindex(big)})
    result["top_product_gmv"] = top_product
    result["top_share_pct"] = result["top_product_gmv"] / result["gmv"] * 100
    result["top_sku"] = by_product.groupby("cust").idxmax().map(lambda pair: pair[1])
    result["products"] = subset.groupby("cust")["sku"].nunique()
    return result.sort_values("gmv", ascending=False)


def dependence_split(dependence):
    """Rozdelenie účtov podľa toho, akú časť GMV im drží jeden produkt."""
    rows = []
    for label in C.PRODUCT_DEPENDENCE_BUCKETS:
        members = dependence.loc[dependence["top_share_pct"].map(_dependence_bucket) == label]
        rows.append({
            "segment": label,
            "accounts": len(members),
            "gmv": members["gmv"].sum(),
        })
    table = pd.DataFrame(rows).set_index("segment")
    table["gmv_share_pct"] = table["gmv"] / dependence["gmv"].sum() * 100
    return table


def _dependence_bucket(share_pct):
    """Popisok koša pre daný podiel najsilnejšieho produktu."""
    for edge, label in zip(C.PRODUCT_DEPENDENCE_EDGES, C.PRODUCT_DEPENDENCE_BUCKETS):
        if share_pct <= edge:
            return label
    return C.PRODUCT_DEPENDENCE_BUCKETS[-1]


def account_flags(accounts, df, table):
    """Štyri príznaky ku každému účtu, na zaradenie do zvyšku analýzy.

    Prvé dva sa dajú povedať o každom účte. Druhé dva platia len pre účty
    v menovateli KPI — pri ostatných vyjde NaN, lebo KPI ich neposudzuje
    a odpoveď „nie“ by tvrdila viac, než vieme.
    """
    orders = df.groupby("cust").size()
    last_order = data.last_order_per_customer(df)
    churn_cutoff = C.AS_OF - pd.Timedelta(days=C.KPI_DIAG_CHURN_DAYS)
    dropped = (table["previous"] > 0) & (table["current"] == 0)

    flags = pd.DataFrame(index=accounts)
    flags["single_order"] = orders.reindex(accounts) == 1
    flags["churned"] = last_order.reindex(accounts) < churn_cutoff
    flags["growing"] = table["growing"].reindex(accounts)
    flags["dropped_to_zero"] = dropped.reindex(accounts)
    return flags
