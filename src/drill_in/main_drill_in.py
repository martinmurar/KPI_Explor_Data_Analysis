#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Account growth drill-in — samostatný report.

Druhý vstupný bod projektu. Hlavný report (main.py) sa nemení a tento skript
ho nespúšťa — každý zapisuje do svojho HTML.

Použitie:
    python3 main_drill_in.py [--input ...] [--output ...]
"""

import argparse
import sys

from src.common import constants as C
from src.common import data
from src.common import metrics_account_growth
from src.common import metrics_kpi_diagnostics
from src.drill_in import metrics_credit_memos
from src.common import report
from src.drill_in import sections_drill_in


def compute_metrics(df):
    """Metriky nad plným aj odfiltrovaným datasetom.

    Tabuľka účtov sa počíta zvlášť pre každý dataset — filter mení množinu
    zákazníkov, takže sa nedá odvodiť z tej druhej.
    """
    table = metrics_account_growth.account_table(df, C.AS_OF)
    filtered_df = data.without_small_veterans(df)
    filtered_table = metrics_account_growth.account_table(filtered_df, C.AS_OF)
    dropped = metrics_kpi_diagnostics.dropped_accounts(table, filtered_table, df)

    return {
        "full_quality": data.data_quality(df),
        "account_growth_summary": metrics_account_growth.kpi_summary(table),
        "diag_summary": metrics_kpi_diagnostics.diagnostics_summary(table, df),
        "diag_by_order_count": metrics_kpi_diagnostics.kpi_by_order_count(table, df),

        "filtered_quality": data.data_quality(filtered_df),
        "filtered_summary": metrics_account_growth.kpi_summary(filtered_table),
        "filtered_by_order_count":
            metrics_kpi_diagnostics.kpi_by_order_count(filtered_table, filtered_df),

        "dropped_accounts": dropped,
        "dropped_activity": metrics_kpi_diagnostics.dropped_activity_split(dropped),
        "dropped_by_country": metrics_kpi_diagnostics.dropped_by_country(dropped),
        "largest_account": metrics_kpi_diagnostics.largest_account(table, df),

        **_single_order_metrics(df),
        **_zero_metrics(table, df),
        **_credit_memo_metrics(df),
        **_churned_metrics(table, df),
    }


def _zero_metrics(table, df):
    """Metriky účtov, ktoré odišli do nuly (Sekcia 4)."""
    zero = metrics_kpi_diagnostics.dropped_to_zero_accounts(table, df)
    return _account_group_metrics("zero", zero, df)

def _churned_metrics(table, df):
    """Metriky churnutých účtov s detailnými charakteristikami (Sekcia 5)."""
    zero = metrics_kpi_diagnostics.dropped_to_zero_accounts(table, df)
    churned = zero.loc[zero.index.intersection(
        metrics_kpi_diagnostics.churned_accounts(table, df).index)]

    metrics = _account_group_metrics("churned", churned, df)
    # Pridáme charakteristiky výhradne len pre churnuté účty
    metrics["churned_characteristics"] = metrics_kpi_diagnostics.churn_characteristics(churned, table)
    return metrics

def _account_group_metrics(prefix, accounts, df):
    """Zoznam účtov, ich mesačné rady a zhluk poslednej objednávky."""
    return {
        f"{prefix}_accounts": accounts,
        f"{prefix}_monthly":
            metrics_kpi_diagnostics.monthly_gmv_by_account(df, accounts.index),
        f"{prefix}_monthly_orders":
            metrics_kpi_diagnostics.monthly_orders_by_account(df, accounts.index),
        f"{prefix}_cluster": metrics_kpi_diagnostics.last_order_cluster(accounts),
    }


def _credit_memo_metrics(df):
    """Objednávky s dobropisom. Zoznam má vlastné CSV, df slúži na odfiltrovanie
    zrušených objednávok."""
    memos = metrics_credit_memos.load_credit_memos(df)
    return {
        "credit_memos": memos,
        "credit_memo_causes": metrics_credit_memos.causes(memos),
    }


def _single_order_metrics(df):
    """Metriky zákazníkov s jedinou objednávkou za život."""
    single = metrics_kpi_diagnostics.single_order_accounts(df)
    repeat_first = metrics_kpi_diagnostics.repeat_first_orders(df)
    return {
        "single_orders": single,
        "single_repeat_first": repeat_first,
        "single_value_mix": metrics_kpi_diagnostics.order_value_mix(single, repeat_first),
        "single_by_year": metrics_kpi_diagnostics.single_order_by_year(single),
    }


def build_report(metrics):
    """Zloží HTML report z metrík."""
    body_html, figures = sections_drill_in.build_all(metrics)
    return report.render_document("Account growth — drill-in",
                                  body_html, figures), len(figures)


def parse_arguments():
    parser = argparse.ArgumentParser(description="Account growth drill-in")
    parser.add_argument("--input", default=C.INPUT_XLSX)
    parser.add_argument("--output", default=C.OUTPUT_HTML_DRILL_IN)
    return parser.parse_args()


def main():
    arguments = parse_arguments()

    print(f"načítavam {arguments.input} ...")
    df = data.load_orders(arguments.input)

    print("počítam metriky ...")
    metrics = compute_metrics(df)

    print("skladám report ...")
    html, figure_count = build_report(metrics)

    with open(arguments.output, "w", encoding="utf-8") as output_file:
        output_file.write(html)

    print(f"hotovo: {arguments.output} ({figure_count} grafov, {len(html):,} znakov)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
