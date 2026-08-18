# -*- coding: utf-8 -*-
"""Načítanie položiek objednávok zo súboru orders_sku.csv.

Súbor má cez 4 GB a takmer 95 miliónov riadkov — do pamäte sa celý nezmestí,
preto sa číta po častiach a každá časť sa hneď zahodí až na riadky, ktoré nás
zaujímajú. Modul nič neanalyzuje a nie je súčasťou pipeline ani jedného
reportu; je to stavebný kameň pre ad-hoc analýzy nad ľubovoľnou skupinou
objednávok.

Dve pasce v zdrojovom súbore:
- Stĺpec `entity_id` napriek názvu obsahuje `increment_id`, teda to isté číslo
  objednávky, aké má export objednávok v stĺpci `increment_id`. Stĺpec
  `order_id` je interné ID a s exportom sa nespája.
- Časť SKU obsahuje čiarku a je v úvodzovkách (napr. "77953-3-64,5g"), takže
  súbor treba čítať poriadnym CSV parserom, nie delením podľa čiarky.
"""

import os

import pandas as pd

from src.common import constants as C

# Mapovanie na názvy, ktoré sedia so zvyškom projektu. increment_id je kľúč,
# na ktorý sa dá napojiť export objednávok.
COLUMN_NAMES = {
    "order_id": "order_id",
    "entity_id": "increment_id",
    "GMV": "gmv",
    "qty_ordered": "qty",
    "sku": "sku",
}

COLUMN_TYPES = {
    "order_id": "string",
    "entity_id": "string",
    "GMV": "float64",
    "qty_ordered": "float64",
    "sku": "string",
}

# Tie isté typy, ale pod menami po premenovaní — pre čítanie odloženej cache.
CACHE_TYPES = {COLUMN_NAMES[column]: dtype for column, dtype in COLUMN_TYPES.items()}


def load_items_for_orders(order_numbers, path=None, chunk_rows=None):
    """Položky objednávok, ktorých increment_id je v order_numbers.

    order_numbers môže byť čokoľvek iterovateľné — zoznam, Index aj Series.
    Porovnáva sa ako text, lebo čísla objednávok majú aj tvary s pomlčkou
    (napr. "202267836-1") a ako číslo by sa stratili.
    """
    groups = load_items_for_groups({"": order_numbers}, path, chunk_rows)
    return groups[""]


def load_items_for_groups(order_numbers_by_group, path=None, chunk_rows=None):
    """To isté pre viac skupín naraz, jedným prechodom zdrojovým súborom.

    Prechod 4 GB súborom trvá jednotky minút a je to úplne celý náklad tejto
    operácie — filtrovanie na viac skupín v tom istom prechode je preto
    prakticky zadarmo oproti spusteniu dvakrát.
    """
    wanted = {
        group: {str(number) for number in numbers}
        for group, numbers in order_numbers_by_group.items()
    }
    kept = {group: [] for group in wanted}

    for chunk in _read_chunks(path, chunk_rows):
        for group, numbers in wanted.items():
            kept[group].append(chunk.loc[chunk["increment_id"].isin(numbers)])

    return {group: pd.concat(parts, ignore_index=True)
            for group, parts in kept.items()}


def _read_chunks(path, chunk_rows):
    """Zdrojový súbor po častiach, s premenovanými stĺpcami."""
    reader = pd.read_csv(
        path or C.ORDER_ITEMS_CSV,
        dtype=COLUMN_TYPES,
        chunksize=chunk_rows or C.ORDER_ITEMS_CHUNK_ROWS,
    )
    for chunk in reader:
        yield chunk.rename(columns=COLUMN_NAMES)


def cached_items(cache_path):
    """Odložený výsledok filtrovania, alebo None ak ešte nie je."""
    if not os.path.exists(cache_path):
        return None
    return pd.read_csv(cache_path, dtype=CACHE_TYPES)


def save_items(cache_path, items):
    """Odloží výsledok filtrovania na disk."""
    items.to_csv(cache_path, index=False)
