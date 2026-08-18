# -*- coding: utf-8 -*-
"""Skupiny objednávok, pre ktoré sa rozoberajú nakúpené produkty.

Každá skupina je len tri veci: názov, cesta k odloženej cache a funkcia, ktorá
z exportu objednávok vyberie jej čísla objednávok. Pridať štvrtú skupinu (napr.
churnuté účty) znamená dopísať sem jeden záznam — načítavač aj sekcia reportu
zostanú nedotknuté.
"""

import pandas as pd

from src.common import constants as C
from src.common import metrics_kpi_diagnostics

SINGLE = "single"
REGULAR = "regular"
ALL = "all"


def single_order_numbers(df):
    """Objednávky zákazníkov, ktorí za celý život objednali práve raz."""
    return metrics_kpi_diagnostics.single_order_accounts(df)["increment_id"]


def regular_order_numbers(df):
    """Objednávky bežných zákazníkov od C.ORDER_ITEMS_START_YEAR.

    Bežný zákazník je tu ten, ktorý za život objednal viac než raz — teda
    priamy protipól jednorazovej skupiny. Obmedzenie na posledné roky nie je
    kozmetické: sortiment sa mení a porovnávať dnešný nákup s tým z roku 2019
    by nedávalo zmysel.
    """
    orders_per_customer = df.groupby("cust").size()
    repeat = orders_per_customer.index[orders_per_customer > 1]

    start = pd.Timestamp(year=C.ORDER_ITEMS_START_YEAR, month=1, day=1)
    window = df.loc[(df["created_at"] >= start) & df["cust"].isin(repeat)]
    return window["increment_id"]


def all_order_numbers(df):
    """Všetky objednávky v očistenom datasete.

    Najširšia skupina — z jej cache sa dajú odvodiť všetky ostatné rezy bez
    ďalšieho prechodu 4 GB súborom. Používa ju report analýzy produktov.
    """
    return df["increment_id"]


GROUPS = {
    ALL: {
        "cache": C.ALL_ORDER_ITEMS_CSV,
        "numbers": all_order_numbers,
        "note": "všetky B2B objednávky",
    },
    SINGLE: {
        "cache": C.SINGLE_ORDER_ITEMS_CSV,
        "numbers": single_order_numbers,
        "note": "zákazníci s jedinou objednávkou za život",
    },
    REGULAR: {
        "cache": C.REGULAR_ORDER_ITEMS_CSV,
        "numbers": regular_order_numbers,
        "note": (f"zákazníci s viac než jednou objednávkou, "
                 f"objednávky od {C.ORDER_ITEMS_START_YEAR}"),
    },
}


def cache_path(group):
    """Kam sa odkladá výsledok filtrovania danej skupiny."""
    return GROUPS[group]["cache"]


def order_numbers(group, df):
    """Čísla objednávok danej skupiny."""
    return GROUPS[group]["numbers"](df)
