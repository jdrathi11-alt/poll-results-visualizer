"""Interactive Streamlit dashboard for the Poll Results Visualizer.

Run this file from the project root with ``streamlit run dashboard.py``.
The dashboard deliberately keeps the UI logic here and delegates cleaning and
analysis to the functions in :mod:`src`.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any

import pandas as pd

try:
    import streamlit as st
except ImportError:  # Keep module-level imports usable for syntax checks.
    st = None

from src.analyzer import (
    calculate_demographic_summary,
    calculate_option_summary,
    calculate_region_summary,
    calculate_trend_summary,
    clean_poll_data,
    generate_insights,
    load_poll_data,
)
from src.data_generator import generate_synthetic_poll_data

try:
    import plotly.express as px
except ImportError:  # Plotly is optional for the dashboard.
    px = None


DATA_PATH = Path(__file__).resolve().parent / "data" / "raw_poll_responses.csv"


def _non_empty_values(frame: pd.DataFrame, column: str) -> list[str]:
    """Return sorted, display-ready values for a filter column."""

    if column not in frame.columns:
        return []

    values = frame[column].dropna().astype(str).str.strip()
    values = values[values != ""]
    return sorted(values.unique().tolist())


def _load_data(path: Path) -> pd.DataFrame:
    """Load the CSV, or use a repeatable sample when no CSV is available."""

    if path.exists():
        try:
            # ``load_poll_data`` validates and cleans the normal CSV path.
            return clean_poll_data(load_poll_data(path))
        except Exception as error:
            st.warning(
                f"We could not read `{path}` ({error}). "
                "The dashboard is showing the deterministic sample instead."
            )
    else:
        st.info(
            "No `data/raw_poll_responses.csv` file was found, so a deterministic "
            "sample of 2,000 responses is being displayed."
        )

    try:
        sample = generate_synthetic_poll_data(n_rows=2000, seed=42)
        return clean_poll_data(sample)
    except Exception as error:
        st.error(f"The sample data could not be prepared: {error}")
        return pd.DataFrame()


def _sidebar_filters(frame: pd.DataFrame) -> tuple[str | None, dict[str, list[str] | None]]:
    """Draw available sidebar filters and return the user's selections."""

    st.sidebar.header("Filters")

    questions = _non_empty_values(frame, "question")
    if questions:
        question_choice = st.sidebar.selectbox(
            "Question",
            ["All questions", *questions],
            index=0,
        )
        selected_question = None if question_choice == "All questions" else question_choice
    else:
        st.sidebar.caption("Question: unavailable")
        selected_question = None

    selected_filters: dict[str, list[str] | None] = {}
    for column, label in (
        ("region", "Region"),
        ("age_group", "Age group"),
        ("gender", "Gender"),
    ):
        values = _non_empty_values(frame, column)
        if not values:
            st.sidebar.caption(f"{label}: unavailable")
            selected_filters[column] = None
            continue

        # Starting with every value selected makes the unfiltered dashboard
        # useful immediately while still allowing a user to clear a filter.
        selected_filters[column] = st.sidebar.multiselect(
            label,
            values,
            default=values,
        )

    return selected_question, selected_filters


def _apply_filters(
    frame: pd.DataFrame,
    selected_question: str | None,
    selected_filters: dict[str, list[str] | None],
) -> pd.DataFrame:
    """Apply sidebar choices without assuming every optional column exists."""

    filtered = frame.copy()

    if selected_question is not None and "question" in filtered.columns:
        filtered = filtered[filtered["question"].astype(str) == selected_question]

    for column, choices in selected_filters.items():
        if choices is None or column not in filtered.columns:
            continue
        # An explicitly cleared multiselect means that no rows match.
        filtered = filtered[filtered[column].astype(str).isin(choices)]

    return filtered.reset_index(drop=True)


def _safe_summary(
    label: str,
    function: Callable[..., pd.DataFrame],
    frame: pd.DataFrame,
    question: str | None = None,
    **kwargs: Any,
) -> pd.DataFrame:
    """Call an analysis helper and turn an unexpected input into a UI message."""

    if frame.empty:
        return pd.DataFrame()

    try:
        result = function(frame, question=question, **kwargs)
    except Exception as error:
        st.error(f"Could not calculate the {label} summary: {error}")
        return pd.DataFrame()

    if result is None:
        return pd.DataFrame()
    if isinstance(result, pd.DataFrame):
        return result

    try:
        return pd.DataFrame(result)
    except Exception as error:
        st.error(f"The {label} summary had an unexpected format: {error}")
        return pd.DataFrame()


def _find_column(frame: pd.DataFrame, names: Iterable[str]) -> str | None:
    """Find the first matching column, allowing small naming differences."""

    columns = {str(column).strip().lower().replace(" ", "_"): column for column in frame.columns}
    for name in names:
        key = name.strip().lower().replace(" ", "_")
        if key in columns:
            return str(columns[key])
    return None


def _standard_summary(frame: pd.DataFrame) -> pd.DataFrame:
    """Copy common summary aliases to the names used by the chart builders."""

    if frame.empty:
        return frame.copy()

    result = frame.copy()
    aliases = {
        "question": ("question", "question_text"),
        "option": ("option", "answer", "choice"),
        "region": ("region", "area", "location"),
        "group": ("group", "age_group", "gender", "demographic"),
        "dimension": ("dimension", "demographic"),
        "response_date": ("response_date", "date", "day"),
        "votes": ("votes", "count", "responses", "response_count", "n"),
        "share_percent": (
            "share_percent",
            "share_percentage",
            "percentage",
            "percent",
            "share",
            "proportion",
        ),
    }
    for standard_name, possible_names in aliases.items():
        if standard_name not in result.columns:
            source = _find_column(result, possible_names)
            if source is not None:
                result[standard_name] = result[source]

    if "votes" in result.columns:
        result["votes"] = pd.to_numeric(result["votes"], errors="coerce")

    if "share_percent" in result.columns:
        result["share_percent"] = pd.to_numeric(result["share_percent"], errors="coerce")
        share_name = _find_column(
            frame,
            ("share", "proportion", "percentage", "percent", "share_percentage"),
        )
        if share_name is not None and share_name != "share_percent":
            values = result["share_percent"].dropna()
            if not values.empty and float(values.abs().max()) <= 1.0:
                result["share_percent"] = result["share_percent"] * 100

    # Some lightweight analysis implementations return counts but not shares.
    # Calculate a percentage using the most specific available denominator.
    if "share_percent" not in result.columns and "votes" in result.columns:
        group_keys = [
            key
            for key in ("region", "group", "response_date", "question")
            if key in result.columns
        ]
        if group_keys:
            totals = result.groupby(group_keys, dropna=False)["votes"].transform("sum")
        else:
            totals = pd.Series(result["votes"].sum(), index=result.index)
        result["share_percent"] = (result["votes"] / totals.replace(0, pd.NA)) * 100

    return result


def _leading_option(frame: pd.DataFrame) -> str:
    """Return a compact leading-option label for the KPI row."""

    if frame.empty or "option" not in frame.columns:
        return "—"

    options = frame["option"].dropna().astype(str)
    if options.empty:
        return "—"

    counts = options.value_counts()
    option = str(counts.index[0])
    share = float(counts.iloc[0]) / len(options) * 100
    return f"{option} ({share:.1f}%)"


def _region_count(frame: pd.DataFrame) -> int:
    """Count regions only when the optional region field is present."""

    if "region" not in frame.columns:
        return 0
    return int(frame["region"].dropna().astype(str).replace("", pd.NA).nunique())


def _render_chart(
    title: str,
    summary: pd.DataFrame,
    chart_builder: Callable[[pd.DataFrame], Any],
) -> None:
    """Render a Plotly chart, or leave a useful table/message when it fails."""

    st.subheader(title)
    if summary.empty:
        st.info("No matching data is available for this chart.")
        return

    if px is None:
        st.info("Plotly is not installed, so the summary table is shown instead.")
        st.dataframe(summary, use_container_width=True, hide_index=True)
        return

    try:
        figure = chart_builder(summary)
        st.plotly_chart(figure, use_container_width=True)
    except Exception as error:
        st.error(f"The {title.lower()} could not be rendered: {error}")
        st.dataframe(summary, use_container_width=True, hide_index=True)


def _option_chart(summary: pd.DataFrame) -> Any:
    chart = _standard_summary(summary)
    required = {"option", "share_percent"}
    if not required.issubset(chart.columns):
        raise ValueError("the option summary needs option and share columns")

    chart = chart.dropna(subset=["option", "share_percent"]).copy()
    if chart.empty:
        raise ValueError("the option summary has no usable rows")
    chart["option_label"] = chart["option"].astype(str)
    if "question" in chart.columns and chart["question"].nunique() > 1:
        chart["option_label"] = chart["question"].astype(str) + " — " + chart["option_label"]

    return px.bar(
        chart.sort_values("share_percent"),
        x="share_percent",
        y="option_label",
        color="question" if "question" in chart.columns and chart["question"].nunique() > 1 else None,
        orientation="h",
        labels={"share_percent": "Share of responses (%)", "option_label": "Option"},
        title="Option share",
    )


def _region_chart(summary: pd.DataFrame) -> Any:
    chart = _standard_summary(summary)
    required = {"region", "option", "share_percent"}
    if not required.issubset(chart.columns):
        raise ValueError("the region summary needs region, option, and share columns")
    chart = chart.dropna(subset=["region", "option", "share_percent"])
    if chart.empty:
        raise ValueError("the region summary has no usable rows")

    return px.bar(
        chart,
        x="region",
        y="share_percent",
        color="option",
        barmode="group",
        labels={"share_percent": "Share of responses (%)", "region": "Region"},
        title="Regional comparison",
    )


def _demographic_chart(summary: pd.DataFrame) -> Any:
    chart = _standard_summary(summary)
    required = {"group", "option", "share_percent"}
    if not required.issubset(chart.columns):
        raise ValueError("the demographic summary needs group, option, and share columns")
    chart = chart.dropna(subset=["group", "option", "share_percent"])
    if chart.empty:
        raise ValueError("the demographic summary has no usable rows")

    return px.bar(
        chart,
        x="group",
        y="share_percent",
        color="option",
        barmode="group",
        labels={"share_percent": "Share of responses (%)", "group": "Group"},
        title="Demographic comparison",
    )


def _trend_chart(summary: pd.DataFrame) -> Any:
    chart = _standard_summary(summary)
    if "response_date" not in chart.columns:
        raise ValueError("the trend summary needs a response_date column")

    value_column = "votes" if "votes" in chart.columns else "share_percent"
    if value_column not in chart.columns:
        raise ValueError("the trend summary needs votes or share columns")
    chart = chart.dropna(subset=["response_date", value_column]).copy()
    if chart.empty:
        raise ValueError("the trend summary has no usable rows")
    chart["response_date"] = pd.to_datetime(chart["response_date"], errors="coerce")
    chart = chart.dropna(subset=["response_date"])
    if chart.empty:
        raise ValueError("the trend summary has no valid dates")

    color_column = "option" if "option" in chart.columns else (
        "question" if "question" in chart.columns else None
    )
    return px.line(
        chart.sort_values("response_date"),
        x="response_date",
        y=value_column,
        color=color_column,
        markers=True,
        labels={
            "response_date": "Response date",
            value_column: "Responses" if value_column == "votes" else "Share of responses (%)",
        },
        title="Responses over time",
    )


def main() -> None:
    """Build and run the Streamlit dashboard."""

    if st is None:
        raise RuntimeError(
            "Streamlit is required to run the dashboard. "
            "Install the project dependencies and retry with `streamlit run dashboard.py`."
        )

    st.set_page_config(
        page_title="Poll Results Visualizer",
        page_icon="📊",
        layout="wide",
    )
    st.title("Poll Results Visualizer")
    st.caption("Explore poll response patterns by option, region, demographic, and date.")

    data = _load_data(DATA_PATH)
    if data.empty:
        st.warning("There are no usable poll responses yet. Add a CSV to the data folder to begin.")

    selected_question, selected_filters = _sidebar_filters(data)
    filtered = _apply_filters(data, selected_question, selected_filters)

    source_name = "data/raw_poll_responses.csv" if DATA_PATH.exists() else "deterministic synthetic sample"
    st.caption(f"Showing {len(filtered):,} of {len(data):,} responses · Source: {source_name}")

    option_summary = _safe_summary(
        "option",
        calculate_option_summary,
        filtered,
        question=selected_question,
    )
    region_summary = _safe_summary(
        "region",
        calculate_region_summary,
        filtered,
        question=selected_question,
    ) if "region" in filtered.columns else pd.DataFrame()

    demographic_column = None
    if "age_group" in filtered.columns:
        demographic_column = "age_group"
    elif "gender" in filtered.columns:
        demographic_column = "gender"
    demographic_summary = (
        _safe_summary(
            "demographic",
            calculate_demographic_summary,
            filtered,
            question=selected_question,
            demographic=demographic_column,
        )
        if demographic_column is not None
        else pd.DataFrame()
    )
    trend_summary = (
        _safe_summary(
            "trend",
            calculate_trend_summary,
            filtered,
            question=selected_question,
        )
        if "response_date" in filtered.columns
        else pd.DataFrame()
    )

    kpi_columns = st.columns(4)
    with kpi_columns[0]:
        st.metric("Responses", f"{len(filtered):,}")
    with kpi_columns[1]:
        question_count = int(filtered["question"].nunique()) if "question" in filtered.columns else 0
        st.metric("Questions", f"{question_count:,}")
    with kpi_columns[2]:
        st.metric("Leading option / share", _leading_option(filtered))
    with kpi_columns[3]:
        st.metric("Regions", f"{_region_count(filtered):,}")

    chart_columns = st.columns(2)
    with chart_columns[0]:
        _render_chart("Option-share bar chart", option_summary, _option_chart)
    with chart_columns[1]:
        _render_chart("Region comparison chart", region_summary, _region_chart)

    chart_columns = st.columns(2)
    with chart_columns[0]:
        _render_chart("Demographic comparison chart", demographic_summary, _demographic_chart)
    with chart_columns[1]:
        _render_chart("Trend chart", trend_summary, _trend_chart)

    st.subheader("Generated insights")
    if filtered.empty:
        st.info("No insights are available for the current filters.")
    else:
        try:
            insights = generate_insights(filtered)
        except Exception as error:
            st.error(f"Could not generate insights: {error}")
            insights = []
        if isinstance(insights, str):
            insights = [insights]
        if insights:
            for insight in insights:
                st.markdown(f"- {insight}")
        else:
            st.info("No insights are available for the current filters.")

    st.subheader("Filtered summary tables")
    summary_tabs = st.tabs(["Options", "Regions", "Demographics", "Trend"])
    for tab, summary in zip(
        summary_tabs,
        (option_summary, region_summary, demographic_summary, trend_summary),
    ):
        with tab:
            if summary.empty:
                st.info("No matching summary rows.")
            else:
                st.dataframe(summary, use_container_width=True, hide_index=True)

    st.download_button(
        "Download filtered CSV",
        data=filtered.to_csv(index=False).encode("utf-8"),
        file_name="filtered_poll_responses.csv",
        mime="text/csv",
    )


if __name__ == "__main__":
    main()
