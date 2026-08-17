#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""EDA rastu GMV v B2B — vstupný bod.

Použitie:
    python3 main.py [--input b2b_orders_cleaned.xlsx] [--output b2b_gmv_eda.html]
"""

import argparse
import sys

from src.common import constants as C
from src.common import data
from src.common import metrics_account_growth
from src.common import metrics_bridge
from src.main_report import metrics_churn
from src.common import metrics_kpi_diagnostics
from src.main_report import metrics_concentration
from src.main_report import metrics_trend
from src.common import report
from src.main_report import sections


def compute_metrics(df):
    """Vypočíta všetky metriky použité v reporte."""
    metrics = _base_metrics(df)
    metrics.update(_account_growth_metrics(df))
    return metrics


def _account_growth_metrics(df):
    """Metriky interného KPI account growth.

    Základná tabuľka sa počíta raz a všetky rezy sa robia z nej.
    """
    table = metrics_account_growth.account_table(df, C.AS_OF)
    return {
        "account_growth_summary": metrics_account_growth.kpi_summary(table),
        "account_growth_composition": metrics_account_growth.composition(table),
        "account_growth_history": metrics_account_growth.history(df),
        "diag_summary": metrics_kpi_diagnostics.diagnostics_summary(table, df),
        "diag_frequency": metrics_kpi_diagnostics.frequency_effect(table),
        "diag_activity_split": metrics_kpi_diagnostics.activity_split(table, df),
        "diag_regular_scenario": metrics_kpi_diagnostics.regular_ordering_scenario(table, df),
        "diag_churn_sensitivity": metrics_kpi_diagnostics.churn_prevented_sensitivity(table, df),
    }


def _displayed_orders(df):
    """Objednávky zo zobrazovaného obdobia.

    Hlavička reportu uvádza rozsah od C.DISPLAY_START_YEAR, takže aj počty
    a GMV v nej musia byť za to isté obdobie — inak by tvrdila rozsah, ktorý
    k svojim číslam nepatrí.
    """
    return df.loc[df["year"] >= C.DISPLAY_START_YEAR]


def _base_metrics(df):
    """Metriky ostatných sekcií reportu."""
    return {
        "quality_displayed": data.data_quality(_displayed_orders(df)),

        "monthly": metrics_trend.monthly_gmv(df),
        "seasonality": metrics_trend.seasonality(df),
        "seasonality_customers": metrics_trend.seasonality_customers(df),
        "yearly": metrics_trend.yearly_summary(df),
        "yoy_growth": metrics_trend.yearly_yoy_growth(df),

        "bridge": metrics_bridge.yearly_bridge(df),

        "concentration": metrics_concentration.concentration_by_year(df),

        "churn_curves": metrics_churn.churn_curves(df),
        "growth_by_band": metrics_churn.growth_by_band(df),
        "band_window": metrics_churn.band_window(),
        "top_band_detail": metrics_churn.top_band_detail(df),
        "single_order": metrics_churn.single_order_share(df),
        "frequency": metrics_churn.frequency_histogram(df),
        "frequency_window": metrics_churn.frequency_window(),
    }


def build_report(metrics):
    """Zloží HTML report z metrík."""
    body_html, figures = sections.build_all(metrics)
    return report.render_document("Exploratívna dátová analýza — account growth B2B",
                                  body_html, figures), len(figures)


def parse_arguments():
    parser = argparse.ArgumentParser(description="EDA rastu GMV v B2B")
    parser.add_argument("--input", default=C.INPUT_XLSX)
    parser.add_argument("--output", default=C.OUTPUT_HTML)
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
