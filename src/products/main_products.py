#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Report o produktoch v objednávkach — tretí, samostatný vstupný bod.

Stojí na cache položiek všetkých B2B objednávok, ktorú vyrobí
build_order_items.py. Zdrojový 4 GB súbor tento skript nečíta.

Použitie:
    python3 -m src.products.main_products [--output ...]
"""

import argparse
import sys

from src.common import constants as C
from src.common import data
from src.common import metrics_account_growth
from src.common import metrics_kpi_diagnostics
from src.common import order_items
from src.common import report
from src.drill_in import metrics_order_items
from src.drill_in import order_item_groups
from src.products import metrics_accounts
from src.products import metrics_first_order
from src.products import sections_products

ACTIVE_LABEL = "Nakupujú ďalej"
LEFT_LABEL = "Odišli do nuly"


def compute_metrics(df, items):
    """Všetky metriky reportu. Položky sú už načítané z cache."""
    joined = metrics_accounts.with_orders(items, df)
    table = metrics_account_growth.account_table(df, C.AS_OF)

    metrics = {
        "profile": metrics_order_items.basket_profile(items),
        "overall_return_pct": 0.0,
    }
    metrics.update(_first_order_metrics(df, items))
    metrics.update(_narrowing_metrics(df, joined, table))
    metrics.update(_dependence_metrics(df, joined, table))
    return metrics


def _first_order_metrics(df, items):
    """Vstupný produkt a šírka prvého košíka."""
    first_order_table = metrics_first_order.first_orders(df)
    first_items = metrics_first_order.first_order_items(items, first_order_table)

    entry = metrics_first_order.entry_product_retention(first_items, first_order_table)
    return {
        "overall_return_pct": metrics_first_order.overall_return_pct(first_order_table),
        "entry_products": metrics_order_items.with_labels(entry),
        "basket_width": metrics_first_order.basket_width(first_items),
    }


def _account_groups(df, table):
    """Dve porovnávané skupiny účtov: odídení do nuly a tí, čo nakupujú ďalej."""
    left = metrics_kpi_diagnostics.dropped_to_zero_accounts(table, df).index
    right = table.index[table["current"] > 0]
    return left, right


def _narrowing_metrics(df, joined, table):
    """Šírka sortimentu v oknách pred koncom, pre obe skupiny."""
    left, right = _account_groups(df, table)

    left_reference = metrics_accounts.last_order_dates(df, left)
    right_reference = {cust: C.AS_OF for cust in right}

    return {
        "narrowing_left": metrics_accounts.assortment_before_end(
            joined, left, left_reference),
        "narrowing_right": metrics_accounts.assortment_before_end(
            joined, right, right_reference),
        "narrowing_left_label": LEFT_LABEL,
        "narrowing_right_label": ACTIVE_LABEL,
    }


def _dependence_metrics(df, joined, table):
    """Závislosť účtov na jedinom produkte a zoznam najkrehkejších."""
    dependence = metrics_accounts.account_dependence(joined)
    fragile = dependence.loc[dependence["top_share_pct"] > C.PRODUCT_DEPENDENCE_EDGES[-1]]

    names = data.company_names(df)
    labels = metrics_order_items.load_sku_names()

    fragile = fragile.head(C.PRODUCT_TOP * 2).copy()
    fragile["top_label"] = [labels.get(sku) or sku for sku in fragile["top_sku"]]
    fragile = fragile.join(metrics_accounts.account_flags(fragile.index, df, table))
    fragile.index = [names.get(cust, cust) for cust in fragile.index]

    return {
        "dependence": dependence,
        "dependence_split": metrics_accounts.dependence_split(dependence),
        "fragile_accounts": fragile,
    }


def update_sku_names(metrics):
    """Doplní do mapy kód → názov prázdne riadky pre produkty, ktoré report ukazuje.

    Rovnaká mapa ako v drill-in reporte, takže názov doplnený raz platí v oboch.
    Existujúce názvy sa neprepisujú a nič sa z mapy nemaže.
    """
    known = metrics_order_items.load_sku_names()
    for sku in _displayed_products(metrics):
        known.setdefault(sku, "")
    return metrics_order_items.save_sku_names(known)


def _displayed_products(metrics):
    """Kódy produktov, ktoré sa v reporte naozaj zobrazia.

    Sú to všetky posudzované vstupné produkty (tie sú aj v tabuľke) a produkty,
    na ktorých visia krehké účty. Zvyšok sortimentu sa v reporte nikde neukáže,
    takže mu netreba názov.
    """
    codes = list(metrics["entry_products"].index)
    codes += list(metrics["fragile_accounts"]["top_sku"])
    return list(dict.fromkeys(codes))


def build_report(metrics):
    """Zloží HTML report z metrík."""
    body_html, figures = sections_products.build_all(metrics)
    return report.render_document("Čo B2B zákazníci kupujú",
                                  body_html, figures), len(figures)


def parse_arguments():
    parser = argparse.ArgumentParser(description="Report o produktoch")
    parser.add_argument("--input", default=C.INPUT_XLSX)
    parser.add_argument("--output", default=C.OUTPUT_HTML_PRODUCTS)
    return parser.parse_args()


def main():
    arguments = parse_arguments()

    items = order_items.cached_items(order_item_groups.cache_path(order_item_groups.ALL))
    if items is None:
        print("chýba cache položiek objednávok — spusti najprv:")
        print("  python3 -m src.drill_in.build_order_items --group all")
        return 1

    print(f"načítavam {arguments.input} ...")
    df = data.load_orders(arguments.input)

    print("počítam metriky ...")
    metrics = compute_metrics(df, items)

    print("skladám report ...")
    html, figure_count = build_report(metrics)

    with open(arguments.output, "w", encoding="utf-8") as output_file:
        output_file.write(html)

    rows, missing = update_sku_names(metrics)
    print(f"hotovo: {arguments.output} ({figure_count} grafov, {len(html):,} znakov)")
    print(f"mapa kód → názov: {C.SKU_NAMES_CSV} "
          f"({rows} riadkov, z toho {missing} bez názvu)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
