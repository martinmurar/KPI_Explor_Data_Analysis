#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Diagnostika KPI account growth — samostatný report.

Druhý vstupný bod projektu. Hlavný report (main.py) sa nemení a tento skript
ho nespúšťa — každý zapisuje do svojho HTML.

Použitie:
    python3 main_kpi_diagnostics.py [--input ...] [--output ...]
"""

import argparse
import sys

from src import constants as C
import data
import metrics_account_growth
import metrics_kpi_diagnostics
import report
import sections_kpi_diagnostics


def compute_metrics(df):
    """Vypočíta metriky diagnostického reportu.

    Základná tabuľka účtov sa počíta raz a všetky rezy vychádzajú z nej, takže
    každé číslo v reporte je konzistentné s hlavným reportom.
    """
    table = metrics_account_growth.account_table(df, C.AS_OF)
    return {
        "quality": data.data_quality(df),
        "diag_summary": metrics_kpi_diagnostics.diagnostics_summary(table, df),
        "diag_frequency": metrics_kpi_diagnostics.frequency_effect(table),
        "diag_activity_split": metrics_kpi_diagnostics.activity_split(table, df),
        "diag_regular_scenario": metrics_kpi_diagnostics.regular_ordering_scenario(table, df),
        "diag_churn_sensitivity": metrics_kpi_diagnostics.churn_prevented_sensitivity(table, df),
        "diag_combined_pct": metrics_kpi_diagnostics.combined_scenario_pct(table, df),
    }


def build_report(metrics):
    """Zloží HTML report z metrík."""
    body_html, figures = sections_kpi_diagnostics.build_all(metrics)
    title = "Account growth — diagnostika KPI"
    return report.render_document(title, body_html, figures), len(figures)


def parse_arguments():
    parser = argparse.ArgumentParser(description="Diagnostika KPI account growth")
    parser.add_argument("--input", default=C.INPUT_XLSX)
    parser.add_argument("--output", default=C.OUTPUT_HTML_KPI_DIAGNOSTICS)
    return parser.parse_args()


def main():
    arguments = parse_arguments()

    print(f"načítavam {arguments.input} ...")
    df = data.load_orders(arguments.input)

    print("počítam diagnostiku ...")
    metrics = compute_metrics(df)

    print("skladám report ...")
    html, figure_count = build_report(metrics)

    with open(arguments.output, "w", encoding="utf-8") as output_file:
        output_file.write(html)

    print(f"hotovo: {arguments.output} ({figure_count} grafov, {len(html):,} znakov)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
