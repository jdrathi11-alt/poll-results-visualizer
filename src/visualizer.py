"""Static PNG charts for the poll analytics pipeline.

The Agg backend is selected before importing pyplot so this module is safe in
headless terminals, CI jobs, and servers.  Every public chart function writes a
PNG and returns its path; no GUI window is opened.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns


IMAGE_NAMES: dict[str, str] = {
    "option_share": "option_share_bar.png",
    "overall_pie": "overall_pie.png",
    "regional": "regional_stacked_bar.png",
    "demographic": "demographic_comparison.png",
    "trend": "date_trend.png",
}

sns.set_theme(style="whitegrid", context="notebook")


def _prepare_output(path: str | Path) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    return destination


def _save_figure(figure: plt.Figure, path: str | Path) -> Path:
    """Save and close a figure consistently."""

    destination = _prepare_output(path)
    figure.tight_layout()
    figure.savefig(destination, dpi=150, bbox_inches="tight", format="png")
    plt.close(figure)
    return destination


def _no_data_figure(title: str) -> tuple[plt.Figure, plt.Axes]:
    figure, axes = plt.subplots(figsize=(9, 5))
    axes.text(0.5, 0.5, "No data available", ha="center", va="center", fontsize=13)
    axes.set_title(title)
    axes.set_axis_off()
    return figure, axes


def plot_option_share_bar(option_analysis: pd.DataFrame, output_path: str | Path) -> Path:
    """Save a horizontal bar chart of option shares by question."""

    if option_analysis.empty:
        figure, _ = _no_data_figure("Option share by question")
        return _save_figure(figure, output_path)

    chart = option_analysis.copy()
    chart["label"] = chart["question"].astype(str) + " — " + chart["option"].astype(str)
    chart = chart.sort_values("share_percent", ascending=True)
    figure, axes = plt.subplots(figsize=(10, max(5, len(chart) * 0.35)))
    sns.barplot(
        data=chart,
        x="share_percent",
        y="label",
        hue="question",
        dodge=False,
        palette="deep",
        legend=False,
        ax=axes,
    )
    axes.set_title("Poll option share by question")
    axes.set_xlabel("Share of answers (%)")
    axes.set_ylabel("")
    axes.set_xlim(0, max(100, float(chart["share_percent"].max()) * 1.12))
    return _save_figure(figure, output_path)


def plot_overall_pie(option_analysis: pd.DataFrame, output_path: str | Path) -> Path:
    """Save a pie chart of total votes for each question/option pair."""

    if option_analysis.empty:
        figure, _ = _no_data_figure("Overall response share")
        return _save_figure(figure, output_path)

    totals = option_analysis.groupby(["question", "option"], as_index=False)["votes"].sum()
    labels = [f"{row.question}: {row.option}" for row in totals.itertuples()]
    figure, axes = plt.subplots(figsize=(8, 8))
    axes.pie(
        totals["votes"],
        labels=labels,
        autopct="%1.1f%%",
        startangle=90,
        colors=sns.color_palette("Set2", n_colors=len(totals)),
        wedgeprops={"linewidth": 0.6, "edgecolor": "white"},
    )
    axes.set_title("Overall response share")
    return _save_figure(figure, output_path)


def _select_question(data: pd.DataFrame, question: str | None = None) -> str | None:
    """Select a requested question or the question with the most votes."""

    if data.empty or "question" not in data.columns:
        return None
    if question is not None and question in set(data["question"].astype(str)):
        return question
    totals = data.groupby("question")["votes"].sum()
    return str(totals.idxmax()) if not totals.empty else None


def plot_regional_stacked_bar(
    region_analysis: pd.DataFrame,
    output_path: str | Path,
    question: str | None = None,
) -> Path:
    """Save a stacked regional chart for the largest or requested question."""

    if region_analysis.empty:
        figure, _ = _no_data_figure("Regional option share")
        return _save_figure(figure, output_path)

    selected = _select_question(region_analysis, question)
    chart = region_analysis[region_analysis["question"] == selected]
    pivot = chart.pivot_table(
        index="region", columns="option", values="share_percent", aggfunc="sum", fill_value=0
    )
    if pivot.empty:
        figure, _ = _no_data_figure("Regional option share")
        return _save_figure(figure, output_path)

    figure, axes = plt.subplots(figsize=(10, 6))
    pivot.plot(
        kind="bar",
        stacked=True,
        ax=axes,
        color=sns.color_palette("Set2", n_colors=len(pivot.columns)),
    )
    axes.set_title(f"Regional option share — {selected}")
    axes.set_xlabel("Region")
    axes.set_ylabel("Share of answers (%)")
    axes.set_ylim(0, 100)
    axes.legend(title="Option", bbox_to_anchor=(1.02, 1), loc="upper left")
    return _save_figure(figure, output_path)


def plot_demographic_comparison(
    demographic_analysis: pd.DataFrame,
    output_path: str | Path,
    question: str | None = None,
) -> Path:
    """Save a grouped comparison chart, preferring age groups when available."""

    if demographic_analysis.empty:
        figure, _ = _no_data_figure("Demographic comparison")
        return _save_figure(figure, output_path)

    selected = _select_question(demographic_analysis, question)
    chart = demographic_analysis[demographic_analysis["question"] == selected].copy()
    if chart.empty:
        figure, _ = _no_data_figure("Demographic comparison")
        return _save_figure(figure, output_path)

    # Age groups make a readable first comparison.  If an input only contains
    # gender data, the generic branch still produces a useful chart.
    dimension = "age_group" if "age_group" in set(chart["dimension"]) else str(chart["dimension"].iloc[0])
    chart = chart[chart["dimension"] == dimension]
    chart = chart.sort_values(["group", "votes"], ascending=[True, False])
    figure, axes = plt.subplots(figsize=(10, 6))
    sns.barplot(
        data=chart,
        x="group",
        y="share_percent",
        hue="option",
        palette="Set2",
        ax=axes,
    )
    axes.set_title(f"Demographic comparison — {selected}")
    axes.set_xlabel("Age group" if dimension == "age_group" else "Gender")
    axes.set_ylabel("Share of answers (%)")
    axes.set_ylim(0, 100)
    axes.legend(title="Option", bbox_to_anchor=(1.02, 1), loc="upper left")
    return _save_figure(figure, output_path)


def plot_date_trend(trend_analysis: pd.DataFrame, output_path: str | Path) -> Path:
    """Save a line chart of daily response volume by question."""

    if trend_analysis.empty:
        figure, _ = _no_data_figure("Responses over time")
        return _save_figure(figure, output_path)

    chart = (
        trend_analysis.groupby(["response_date", "question"], as_index=False)["votes"].sum()
        .sort_values("response_date")
    )
    figure, axes = plt.subplots(figsize=(11, 5))
    sns.lineplot(
        data=chart,
        x="response_date",
        y="votes",
        hue="question",
        marker="o",
        linewidth=2,
        ax=axes,
    )
    axes.set_title("Poll responses over time")
    axes.set_xlabel("Response date")
    axes.set_ylabel("Responses")
    axes.tick_params(axis="x", rotation=35)
    axes.legend(title="Question", bbox_to_anchor=(1.02, 1), loc="upper left")
    return _save_figure(figure, output_path)


def create_all_visualizations(
    option_analysis: pd.DataFrame,
    region_analysis: pd.DataFrame,
    demographic_analysis: pd.DataFrame,
    trend_analysis: pd.DataFrame,
    image_dir: str | Path = "images",
) -> Mapping[str, Path]:
    """Create all five stable-name PNGs and return their paths."""

    directory = Path(image_dir)
    directory.mkdir(parents=True, exist_ok=True)
    paths = {key: directory / filename for key, filename in IMAGE_NAMES.items()}
    plot_option_share_bar(option_analysis, paths["option_share"])
    plot_overall_pie(option_analysis, paths["overall_pie"])
    plot_regional_stacked_bar(region_analysis, paths["regional"])
    plot_demographic_comparison(demographic_analysis, paths["demographic"])
    plot_date_trend(trend_analysis, paths["trend"])
    return paths


# Concise aliases are convenient for students discovering the module by reading it.
plot_option_share = plot_option_share_bar
plot_regional_bar = plot_regional_stacked_bar
plot_demographic_chart = plot_demographic_comparison
plot_trend = plot_date_trend
