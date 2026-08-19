#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Postaví cache položiek objednávok pre skupiny zákazníkov.

Samostatný skript, nie súčasť pipeline ani jedného reportu. Prejde celý
orders_sku.csv (jednotky minút) a výsledok odloží; drill-in report potom číta
už len tie cache. Chýbajúce skupiny sa filtrujú jedným spoločným prechodom,
takže postaviť dve skupiny naraz stojí toľko, čo postaviť jednu.

Použitie:
    python3 -m src.drill_in.build_order_items [--group single|regular|all] [--rebuild]
"""

import argparse
import os
import sys

from src.common import constants as C
from src.common import data
from src.common import order_items
from src.drill_in import metrics_order_items as MOI
from src.drill_in import order_item_groups as GROUPS

ALL_GROUPS = "all"


def groups_to_build(names, rebuild):
    """Skupiny, ktorým cache chýba. Pri rebuild=True sa existujúca zahodí."""
    pending = []
    for name in names:
        path = GROUPS.cache_path(name)
        if rebuild and os.path.exists(path):
            os.remove(path)
        if not os.path.exists(path):
            pending.append(name)
    return pending


def build_caches(df, names):
    """Jedným prechodom zdrojovým súborom vyrobí cache všetkých skupín."""
    if not names:
        return

    numbers = {name: GROUPS.order_numbers(name, df) for name in names}
    for name, count in numbers.items():
        print(f"  {name}: {len(set(count)):,} objednávok")

    print(f"prechádzam {C.ORDER_ITEMS_CSV} ...")
    for name, items in order_items.load_items_for_groups(numbers).items():
        order_items.save_items(GROUPS.cache_path(name), items)
        print(f"  {name}: {len(items):,} riadkov -> {GROUPS.cache_path(name)}")


def update_sku_names(sku_totals_by_group):
    """Doplní do mapy SKU → názov prázdne riadky pre chýbajúce SKU.

    Existujúce názvy sa nikdy neprepisujú a riadky, ktoré už v mape sú, sa
    nemažú — mapa je ručná práca a smie prežiť zmenu dát.
    """
    known = MOI.load_sku_names()
    for sku_totals in sku_totals_by_group.values():
        for sku in MOI.displayed_skus(sku_totals).index:
            known.setdefault(sku, "")
    return MOI.save_sku_names(known)


def print_summary(name, items, top):
    """Prehľad skupiny na štandardný výstup."""
    profile = MOI.basket_profile(items)
    sku_totals = MOI.by_sku(items)

    print(f"\n── {name} ──")
    print(f"objednávok: {profile['orders']:,}   "
          f"rôznych produktov: {profile['skus']:,}")
    print(f"medián objednávky: {profile['median_products']:.0f} produktov, "
          f"{profile['median_units']:.0f} kusov, {profile['median_gmv']:.2f} €")
    print(f"objednávok s jediným produktom: {profile['single_product_pct']:.1f} %")

    print("\nkoncentrácia GMV:")
    print(MOI.concentration(sku_totals).round(1).to_string())

    print(f"\ntop {top} SKU podľa GMV:")
    print(sku_totals.head(top).round(2).to_string())

    print(f"\ntop {top} SKU podľa počtu objednávok:")
    print(sku_totals.sort_values("orders", ascending=False).head(top).round(2).to_string())

    return sku_totals


def parse_arguments():
    parser = argparse.ArgumentParser(description="Cache položiek objednávok")
    parser.add_argument("--group", default=ALL_GROUPS,
                        choices=sorted(GROUPS.GROUPS) + [ALL_GROUPS])
    parser.add_argument("--rebuild", action="store_true",
                        help="zahodí cache a prejde zdrojový súbor znova")
    parser.add_argument("--top", type=int, default=C.SINGLE_ORDER_ITEMS_TOP)
    return parser.parse_args()


def main():
    arguments = parse_arguments()
    names = sorted(GROUPS.GROUPS) if arguments.group == ALL_GROUPS else [arguments.group]

    print(f"načítavam {C.INPUT_XLSX} ...")
    df = data.load_orders(C.INPUT_XLSX)

    build_caches(df, groups_to_build(names, arguments.rebuild))

    sku_totals_by_group = {}
    for name in names:
        items = MOI.load_cached_items(GROUPS.cache_path(name))
        sku_totals_by_group[name] = print_summary(name, items, arguments.top)

    rows, missing = update_sku_names(sku_totals_by_group)
    print(f"\nmapa SKU → názov: {C.SKU_NAMES_CSV} "
          f"({rows} riadkov, z toho {missing} bez názvu)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
