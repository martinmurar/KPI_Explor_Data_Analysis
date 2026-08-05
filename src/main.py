#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""EDA rastu GMV v B2B — vstupný bod.

Použitie:
    python3 main.py [--input b2b_orders_cleaned.xlsx] [--output b2b_gmv_eda.html]
"""

import argparse
import sys

from src import constants as C
import data
import metrics_bridge
import metrics_churn
import metrics_concentration
import metrics_trend
import report
import sections


def compute_metrics(df):
    """Vypočíta všetky metriky použité v reporte."""
    return {
        "quality": data.data_quality(df),
        "status_table": data.gmv_by_status(df),
        "orders_2018": df.loc[df["year"] < C.FIRST_TREND_YEAR],

        "monthly": metrics_trend.monthly_gmv(df),
        "seasonality": metrics_trend.seasonality(df),
        "yearly": metrics_trend.yearly_summary(df),
        "yoy_growth": metrics_trend.yearly_yoy_growth(df),

        "bridge": metrics_bridge.yearly_bridge(df),

        "concentration": metrics_concentration.concentration_by_year(df),
        "portfolio_structure": metrics_concentration.portfolio_structure(df, C.PARTIAL_YEAR),
        "market_gmv": metrics_concentration.gmv_by_market_and_year(df),
        "market_summary": metrics_concentration.market_summary(df),
        "market_growth": metrics_concentration.market_growth_for_chart(df),

        "churn_curves": metrics_churn.churn_curves(df),
        "churn_by_band": metrics_churn.churn_by_band(df),
        "growth_by_band": metrics_churn.growth_by_band(df),
        "single_order": metrics_churn.single_order_share(df),
        "frequency": metrics_churn.frequency_histogram(df),
        "frequency_max": metrics_churn.max_frequency(df),
        "reactivation_histogram": metrics_churn.reactivation_histogram(df),
        "repeat_reactivation": metrics_churn.repeat_reactivation_by_year(df),
        "reactivation_value": metrics_churn.reactivation_value(df),
    }


def build_report(metrics):
    """Zloží HTML report z metrík."""
    body_html, figures = sections.build_all(metrics)
    return report.render_document("EDA — rast GMV v B2B", body_html, figures), len(figures)


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
