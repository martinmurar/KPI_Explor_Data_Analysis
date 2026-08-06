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
import metrics_account_growth
import metrics_bridge
import metrics_churn
import metrics_concentration
import metrics_trend
import report
import sections


def compute_metrics(df):
    """Vypočíta všetky metriky použité v reporte."""
    metrics = _base_metrics(df)
    metrics.update(_account_growth_metrics(df))
    metrics["top_band_companies"] = _top_band_companies(df)
    return metrics


def _top_band_companies(df):
    """Názvy firiem v najvyššom GMV pásme, pre úvodný komentár.

    Zákazník bez vyplneného company_bill sa v zozname nahradí e-mailom.
    """
    top_customers = metrics_churn.top_band_customers(df)
    names = data.company_names(df)
    return [names.get(cust, cust) for cust in top_customers.index]


def _account_growth_metrics(df):
    """Metriky interného KPI account growth.

    Základná tabuľka sa počíta raz a všetky rezy sa robia z nej.
    """
    table = metrics_account_growth.account_table(df, C.AS_OF)
    return {
        "account_growth_summary": metrics_account_growth.kpi_summary(table),
        "account_growth_composition": metrics_account_growth.composition(table),
        "account_growth_history": metrics_account_growth.history(df),
        "account_growth_by_band": metrics_account_growth.by_size_band(table),
        "account_growth_by_group": metrics_account_growth.by_customer_group(table),
        "account_growth_by_country": metrics_account_growth.by_country(table),
        "account_growth_by_cohort": metrics_account_growth.by_cohort(table),
        "account_growth_by_orders": metrics_account_growth.by_previous_orders(table),
    }


def _base_metrics(df):
    """Metriky ostatných sekcií reportu."""
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
