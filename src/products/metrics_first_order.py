# -*- coding: utf-8 -*-
"""Čo bolo v prvej objednávke a či sa po nej zákazník vrátil.

Odpovedá na otázku, na ktorú hodnota prvej objednávky odpovedať nevie: dá sa
z obsahu prvého nákupu poznať, kto sa vráti? Obe metriky pracujú len so
zákazníkmi, ktorých prvá objednávka je staršia než C.SINGLE_ORDER_MIN_AGE_MONTHS
— mladší ešte mali čas vrátiť sa a ako „nevrátený“ by sa počítali nesprávne.
"""

import pandas as pd

from src.common import constants as C
from src.common import data


def first_orders(df):
    """Prvá objednávka každého dosť starého zákazníka a či sa vrátil."""
    first_order = data.first_order_per_customer(df)
    cutoff = C.AS_OF - pd.DateOffset(months=C.SINGLE_ORDER_MIN_AGE_MONTHS)
    mature = first_order.index[first_order < cutoff]

    orders = df.loc[df["cust"].isin(mature)]
    first_rows = orders.sort_values("created_at").groupby("cust").first()

    result = pd.DataFrame(index=first_rows.index)
    result["increment_id"] = first_rows["increment_id"]
    result["created_at"] = first_rows["created_at"]
    result["returned"] = orders.groupby("cust").size() > 1
    return result


def first_order_items(items, first_order_table):
    """Položky prvých objednávok, doplnené o zákazníka a jeho návrat."""
    wanted = first_order_table.reset_index()[["cust", "increment_id", "returned"]]
    return items.merge(wanted, on="increment_id", how="inner")


def entry_product_retention(first_items, first_order_table):
    """Podiel návratov podľa produktu, ktorý bol v prvej objednávke.

    Zákazník sa počíta ku každému produktu zo svojej prvej objednávky, takže
    súčet cez produkty je vyšší než počet zákazníkov. Nie je to chyba — otázka
    znie „ako dopadli tí, čo si toto kúpili ako prvé“, nie „koľkých je spolu“.
    """
    per_product = first_items.drop_duplicates(["cust", "sku"])
    grouped = per_product.groupby("sku").agg(
        customers=("cust", "size"),
        returned=("returned", "sum"),
        gmv=("gmv", "sum"),
    )
    grouped["returned_pct"] = grouped["returned"] / grouped["customers"] * 100
    grouped = grouped.loc[grouped["customers"] >= C.PRODUCT_MIN_CUSTOMERS]
    return grouped.sort_values("returned_pct")


def overall_return_pct(first_order_table):
    """Podiel zákazníkov, ktorí sa po prvej objednávke vrátili."""
    return first_order_table["returned"].mean() * 100


def basket_width(first_items):
    """Podiel návratov podľa počtu rôznych produktov v prvej objednávke."""
    per_customer = first_items.groupby("cust").agg(
        lines=("sku", "nunique"),
        returned=("returned", "first"),
        gmv=("gmv", "sum"),
    )
    per_customer["bucket"] = per_customer["lines"].map(_width_bucket)

    rows = []
    for label in C.BASKET_WIDTH_BUCKETS:
        members = per_customer.loc[per_customer["bucket"] == label]
        if len(members) == 0:
            continue
        rows.append({
            "segment": label,
            "customers": len(members),
            "returned_pct": members["returned"].mean() * 100,
            "median_gmv": members["gmv"].median(),
        })
    return pd.DataFrame(rows).set_index("segment")


def _width_bucket(lines):
    """Popisok koša pre daný počet rôznych produktov.

    BASKET_WIDTH_EDGES sú horné hranice prvých košov; čo sa do žiadnej
    nezmestí, patrí do posledného, otvoreného koša.
    """
    for edge, label in zip(C.BASKET_WIDTH_EDGES, C.BASKET_WIDTH_BUCKETS):
        if lines <= edge:
            return label
    return C.BASKET_WIDTH_BUCKETS[-1]
