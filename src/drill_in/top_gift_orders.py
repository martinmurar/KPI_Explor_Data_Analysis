#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Najväčšie objednávky, ktoré obsahovali darček alebo vzorku.

Ad-hoc skript, nie súčasť pipeline ani jedného reportu. Číta odloženú cache
položiek (tú vyrobí build_order_items.py) a export objednávok — zdrojový 4 GB
súbor neotvára.

Darček a vzorka sú dva bežné produkty s vlastným kódom (C.GIFT_SAMPLE_SKUS);
skript len vyberá objednávky, v ktorých sa niektorý z nich objavil. Podľa názvu
sa hľadať nedajú — „+ darček“ má v názve aj iný tovar.

Použitie:
    python3 -m src.drill_in.top_gift_orders [--group all|single|regular] [--top 15]
"""

import argparse
import sys

import pandas as pd

from src.common import constants as C
from src.common import data
from src.common import formatting
from src.drill_in import metrics_order_items as MOI
from src.drill_in import order_item_groups as GROUPS

DEFAULT_TOP = 15
# Staršie objednávky sa nepozerajú — sortiment aj ceny sú inde. Objednávka,
# ktorá v exporte nie je, vypadne s nimi (dátum nemá odkiaľ zobrať).
DEFAULT_SINCE = "2024-01-01"
SINCE_ALL = "all"
GIFT_MARK = "*"
SKU_WIDTH = 24
LABEL_WIDTH = 46

EUR = formatting.format_eur
NUM = formatting.format_number


def gift_orders(items, gift_skus):
    """Súčty za objednávky, ktoré obsahovali aspoň jeden darček alebo vzorku."""
    with_gift = items.loc[items["sku"].isin(gift_skus), "increment_id"].unique()
    inside = items.loc[items["increment_id"].isin(with_gift)]

    totals = inside.groupby("increment_id").agg(
        order_id=("order_id", "first"),
        gmv=("gmv", "sum"),
        lines=("sku", "size"),
        qty=("qty", "sum"),
    )
    return totals.sort_values("gmv", ascending=False)


def order_lines(items, increment_id, names, gift_skus):
    """Položky jednej objednávky, od najdrahšej, s názvom a príznakom darčeka."""
    lines = items.loc[items["increment_id"] == increment_id].copy()
    lines["label"] = [names.get(sku) or sku for sku in lines["sku"]]
    lines["gift"] = lines["sku"].isin(gift_skus)
    return lines.sort_values("gmv", ascending=False)


def order_meta(df):
    """Zákazník, dátum a krajina ku každému číslu objednávky."""
    meta = df.drop_duplicates("increment_id").set_index("increment_id")
    meta["label"] = meta["company_bill"].fillna(meta["customer_email"])
    return meta


def print_order(position, increment_id, totals_row, lines, meta):
    """Jedna objednávka: hlavička a jej položky."""
    print(f"\n── {position}. objednávka {increment_id} "
          f"(order_id {totals_row['order_id']}) — "
          f"{EUR(totals_row['gmv'], 2)} v položkách ──")
    _print_meta(increment_id, meta)
    print(f"   {NUM(totals_row['lines'])} riadkov, "
          f"{NUM(totals_row['qty'])} kusov")
    _print_lines(lines)


def _print_meta(increment_id, meta):
    """Riadok o zákazníkovi. Objednávka mimo exportu ho nemá."""
    if increment_id not in meta.index:
        print("   zákazník: neznámy (objednávka nie je v exporte)")
        return

    row = meta.loc[increment_id]
    print(f"   zákazník: {row['label']} <{row['customer_email']}>, "
          f"{row['country']}, {row['created_at']:%-d. %-m. %Y}, "
          f"GMV objednávky {EUR(row['gmv'], 2)}")


def _print_lines(lines):
    """Položky objednávky. Hviezdička označuje darček alebo vzorku."""
    print(f"     {'kód':<{SKU_WIDTH}} {'názov':<{LABEL_WIDTH}} "
          f"{'kusov':>7} {'GMV':>12}")
    for row in lines.itertuples():
        mark = GIFT_MARK if row.gift else " "
        print(f"   {mark} {row.sku:<{SKU_WIDTH}} {row.label[:LABEL_WIDTH]:<{LABEL_WIDTH}} "
              f"{NUM(row.qty):>7} {EUR(row.gmv, 2):>12}")


def orders_since(df, since):
    """Čísla objednávok vytvorených od zadaného dátumu."""
    return set(df.loc[df["created_at"] >= since, "increment_id"])


def parse_since(value):
    """Hodnota --since ako dátum. SINCE_ALL znamená bez filtra, teda None."""
    if value == SINCE_ALL:
        return None
    return pd.Timestamp(value)


def items_since(items, df, since):
    """Položky objednávok od zadaného dátumu. Pri since=None sa nefiltruje."""
    if since is None:
        return items
    return items.loc[items["increment_id"].isin(orders_since(df, since))]


def print_scope(since, kept, total):
    """Na akej časti dát rebríček stojí."""
    if since is None:
        print(f"objednávok od začiatku dát: {NUM(kept)}")
        return
    print(f"objednávok od {since:%-d. %-m. %Y}: {NUM(kept)} z {NUM(total)}")


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Najväčšie objednávky s darčekom alebo vzorkou")
    parser.add_argument("--group", default=GROUPS.ALL, choices=sorted(GROUPS.GROUPS))
    parser.add_argument("--top", type=int, default=DEFAULT_TOP)
    parser.add_argument("--since", default=DEFAULT_SINCE,
                        help=(f"len objednávky od tohto dátumu (predvolene "
                              f"{DEFAULT_SINCE}), „{SINCE_ALL}“ vypne filter"))
    return parser.parse_args()


def main():
    arguments = parse_arguments()

    items = MOI.load_cached_items(GROUPS.cache_path(arguments.group))
    if items is None:
        print("chýba cache položiek — spusti najprv:")
        print(f"  python3 -m src.drill_in.build_order_items --group {arguments.group}")
        return 1

    print(f"načítavam {C.INPUT_XLSX} ...")
    df = data.load_orders(C.INPUT_XLSX)
    meta = order_meta(df)

    since = parse_since(arguments.since)
    before = items["increment_id"].nunique()
    items = items_since(items, df, since)

    gift_skus = MOI.gift_sample_skus(items)
    totals = gift_orders(items, gift_skus)
    names = MOI.load_sku_names()

    print(f"\nskupina: {GROUPS.GROUPS[arguments.group]['note']}")
    print_scope(since, items["increment_id"].nunique(), before)
    print(f"z toho s darčekom alebo vzorkou: {NUM(len(totals))}")
    print(f"rozpoznaných darčekových produktov: {NUM(len(gift_skus))}")

    for position, increment_id in enumerate(totals.head(arguments.top).index, start=1):
        print_order(position, increment_id, totals.loc[increment_id],
                    order_lines(items, increment_id, names, gift_skus), meta)

    print(f"\n{GIFT_MARK} = darček alebo vzorka")
    return 0


if __name__ == "__main__":
    sys.exit(main())
