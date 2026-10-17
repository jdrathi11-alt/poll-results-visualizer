"""Cleaning, validation, analysis, and insight helpers for poll responses."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Final

import numpy as np
import pandas as pd


REQUIRED_COLUMNS: Final[tuple[str, ...]] = (
    "response_id",
    "response_date",
    "question",
    "option",
    "region",
    "age_group",
    "gender",
)
OPTIONAL_COLUMNS: Final[tuple[str, ...]] = ("satisfaction_score",)
DOCUMENTED_COLUMNS: Final[tuple[str, ...]] = REQUIRED_COLUMNS + OPTIONAL_COLUMNS

COLUMN_ALIASES: Final[dict[str, str]] = {
    "id": "response_id",
    "responseid": "response_id",
    "date": "response_date",
    "responded_at": "response_date",
    "question_text": "question",
    "answer": "option",
    "choice": "option",
    "area": "region",
    "location": "region",
    "age": "age_group",
    "agegroup": "age_group",
    "sex": "gender",
    "satisfaction": "satisfaction_score",
    "satisfaction_rating": "satisfaction_score",
}

OPTION_ANALYSIS_COLUMNS: Final[tuple[str, ...]] = (
    "question",
    "option",
    "votes",
    "total_votes",
    "share_percent",
)
REGION_ANALYSIS_COLUMNS: Final[tuple[str, ...]] = (
    "region",
    "question",
    "option",
    "votes",
    "region_question_total",
    "share_percent",
)
DEMOGRAPHIC_ANALYSIS_COLUMNS: Final[tuple[str, ...]] = (
    "dimension",
    "group",
    "question",
    "option",
    "votes",
    "group_question_total",
    "share_percent",
)
TREND_ANALYSIS_COLUMNS: Final[tuple[str, ...]] = (
    "response_date",
    "question",
    "option",
    "votes",
    "date_question_total",
    "share_percent",
)


def _normalise_column_name(name: object) -> str:
    """Convert a user-facing column label to a predictable snake_case name."""

    value = re.sub(r"[^a-z0-9]+", "_", str(name).strip().lower()).strip("_")
    value = re.sub(r"_+", "_", value)
    return COLUMN_ALIASES.get(value, value)


def _normalise_columns(data: pd.DataFrame) -> pd.DataFrame:
    """Return a copy with canonical column names, rejecting collisions."""

    renamed = [_normalise_column_name(column) for column in data.columns]
    duplicates = sorted({column for column in renamed if renamed.count(column) > 1})
    if duplicates:
        joined = ", ".join(duplicates)
        raise ValueError(f"Multiple input columns map to the same name: {joined}")
    frame = data.copy()
    frame.columns = renamed
    return frame


def validate_columns(data: pd.DataFrame) -> bool:
    """Validate the required poll columns and return ``True`` when present.

    Column labels are normalized for this check, so inputs such as
    ``Response Date`` and ``response_date`` are treated equivalently.  The
    optional satisfaction score is deliberately not required.
    """

    if not isinstance(data, pd.DataFrame):
        raise TypeError("data must be a pandas DataFrame")
    normalized = _normalise_columns(data)
    missing = [column for column in REQUIRED_COLUMNS if column not in normalized.columns]
    if missing:
        raise ValueError("Missing required poll columns: " + ", ".join(missing))
    return True


def _clean_text(series: pd.Series) -> pd.Series:
    """Trim text and collapse repeated whitespace while preserving missing values."""

    return series.astype("string").str.strip().str.replace(r"\s+", " ", regex=True)


def _normalise_option_map(
    valid_options: Mapping[str, Sequence[str]],
) -> dict[str, dict[str, str]]:
    """Make question/option validation case-insensitive but preserve labels."""

    normalized: dict[str, dict[str, str]] = {}
    for question, options in valid_options.items():
        question_key = " ".join(str(question).strip().casefold().split())
        normalized[question_key] = {"__question_label__": str(question).strip()}
        for option in options:
            option_label = " ".join(str(option).strip().split())
            normalized[question_key][option_label.casefold()] = option_label
    return normalized


def validate_options(
    data: pd.DataFrame,
    valid_options: Mapping[str, Sequence[str]] | None = None,
) -> pd.DataFrame:
    """Return rows whose question/option pair is valid.

    If ``valid_options`` is omitted, non-empty question and option values are
    accepted.  When a mapping is supplied, unknown questions and options are
    removed and accepted labels are replaced with the mapping's canonical
    spelling.  Removing invalid rows is friendlier for classroom datasets than
    allowing an unexpected category to distort charts silently.
    """

    frame = data.copy()
    if frame.empty or valid_options is None:
        return frame

    option_map = _normalise_option_map(valid_options)
    question_keys = frame["question"].astype("string").str.casefold().str.strip()
    option_keys = frame["option"].astype("string").str.casefold().str.strip()
    valid_mask = []
    canonical_questions: list[str | None] = []
    canonical_options: list[str | None] = []

    for question_key, option_key in zip(question_keys, option_keys):
        question_text = "" if pd.isna(question_key) else str(question_key)
        option_text = "" if pd.isna(option_key) else str(option_key)
        allowed = option_map.get(question_text)
        canonical_option = allowed.get(option_text) if allowed else None
        valid_mask.append(canonical_option is not None)
        canonical_questions.append(
            allowed["__question_label__"] if allowed and canonical_option is not None else None
        )
        canonical_options.append(canonical_option if canonical_option is not None else None)

    valid_positions = [position for position, is_valid in enumerate(valid_mask) if is_valid]
    frame = frame.iloc[valid_positions].copy()
    frame["question"] = pd.array(
        [canonical_questions[position] for position in valid_positions], dtype="string"
    )
    frame["option"] = pd.array(
        [canonical_options[position] for position in valid_positions], dtype="string"
    )
    return frame


def clean_poll_data(
    data: pd.DataFrame,
    valid_options: Mapping[str, Sequence[str]] | None = None,
) -> pd.DataFrame:
    """Normalize types, remove duplicate/ unusable rows, and fill missing fields.

    Essential identifiers, dates, questions, and options must be present for a
    row to be analyzable and are dropped when missing or invalid.  Missing
    region, age group, and gender values become ``"Unknown"``.  If a
    satisfaction column exists, values are coerced to numbers and missing
    values are filled with the column median when a median is available.
    """

    if not isinstance(data, pd.DataFrame):
        raise TypeError("data must be a pandas DataFrame")
    frame = _normalise_columns(data)
    validate_columns(frame)

    # Keep the documented columns first, while retaining extra columns for a
    # user's own notes or identifiers.
    documented = [column for column in DOCUMENTED_COLUMNS if column in frame.columns]
    extras = [column for column in frame.columns if column not in documented]
    frame = frame[documented + extras].copy()

    frame["response_id"] = _clean_text(frame["response_id"])
    frame["question"] = _clean_text(frame["question"])
    frame["option"] = _clean_text(frame["option"])
    for column in ("region", "age_group", "gender"):
        frame[column] = _clean_text(frame[column]).fillna("Unknown").replace("", "Unknown")

    frame["response_date"] = pd.to_datetime(frame["response_date"], errors="coerce")
    frame = frame.dropna(subset=["response_id", "response_date", "question", "option"])
    frame = frame[
        (frame["response_id"] != "")
        & (frame["question"] != "")
        & (frame["option"] != "")
    ].copy()

    # A response should answer a question once. Exact duplicate rows are also
    # removed by this subset, while allowing a response ID to answer different
    # questions in a multi-question export.
    frame = frame.drop_duplicates(subset=["response_id", "question"], keep="first")
    frame = validate_options(frame, valid_options)

    if "satisfaction_score" in frame.columns:
        frame["satisfaction_score"] = pd.to_numeric(frame["satisfaction_score"], errors="coerce")
        if frame["satisfaction_score"].notna().any():
            median = float(frame["satisfaction_score"].median())
            frame["satisfaction_score"] = frame["satisfaction_score"].fillna(median)

    return frame.reset_index(drop=True)


def load_poll_data(path: str | Path) -> pd.DataFrame:
    """Load a CSV and return a validated, cleaned poll-response frame."""

    source = Path(path)
    if not source.exists():
        raise FileNotFoundError(f"Poll input file does not exist: {source}")
    if source.stat().st_size == 0:
        raise ValueError(f"Poll input file is empty: {source}")
    try:
        raw = pd.read_csv(source)
    except (pd.errors.EmptyDataError, pd.errors.ParserError) as exc:
        raise ValueError(f"Could not read poll CSV {source}: {exc}") from exc
    if raw.empty:
        raise ValueError(f"Poll input file has no rows: {source}")
    return clean_poll_data(raw)


def _clean_for_analysis(data: pd.DataFrame) -> pd.DataFrame:
    """Use the same safeguards for direct analysis calls as for CSV loading."""

    return clean_poll_data(data)


def _empty_frame(columns: Sequence[str]) -> pd.DataFrame:
    """Create an empty analysis frame with a stable schema."""

    return pd.DataFrame({column: pd.Series(dtype="object") for column in columns})


def analyze_option_shares(data: pd.DataFrame) -> pd.DataFrame:
    """Count each option and calculate its percentage within each question."""

    frame = _clean_for_analysis(data)
    if frame.empty:
        return _empty_frame(OPTION_ANALYSIS_COLUMNS)

    counts = (
        frame.groupby(["question", "option"], as_index=False, dropna=False)
        .size()
        .rename(columns={"size": "votes"})
    )
    counts["total_votes"] = counts.groupby("question")["votes"].transform("sum")
    counts["share_percent"] = counts["votes"] / counts["total_votes"] * 100
    return counts.sort_values(
        ["question", "votes", "option"], ascending=[True, False, True]
    ).reset_index(drop=True)[list(OPTION_ANALYSIS_COLUMNS)]


def analyze_region_shares(data: pd.DataFrame) -> pd.DataFrame:
    """Calculate option shares for every region and question."""

    frame = _clean_for_analysis(data)
    if frame.empty:
        return _empty_frame(REGION_ANALYSIS_COLUMNS)

    counts = (
        frame.groupby(["region", "question", "option"], as_index=False, dropna=False)
        .size()
        .rename(columns={"size": "votes"})
    )
    counts["region_question_total"] = counts.groupby(["region", "question"])["votes"].transform("sum")
    counts["share_percent"] = counts["votes"] / counts["region_question_total"] * 100
    return counts.sort_values(
        ["region", "question", "votes", "option"], ascending=[True, True, False, True]
    ).reset_index(drop=True)[list(REGION_ANALYSIS_COLUMNS)]


def analyze_demographics(data: pd.DataFrame) -> pd.DataFrame:
    """Compare option shares across age groups and genders."""

    frame = _clean_for_analysis(data)
    if frame.empty:
        return _empty_frame(DEMOGRAPHIC_ANALYSIS_COLUMNS)

    pieces: list[pd.DataFrame] = []
    for dimension in ("age_group", "gender"):
        counts = (
            frame.groupby([dimension, "question", "option"], as_index=False, dropna=False)
            .size()
            .rename(columns={dimension: "group", "size": "votes"})
        )
        counts.insert(0, "dimension", dimension)
        counts["group_question_total"] = counts.groupby(["group", "question"])["votes"].transform("sum")
        counts["share_percent"] = counts["votes"] / counts["group_question_total"] * 100
        pieces.append(counts[list(DEMOGRAPHIC_ANALYSIS_COLUMNS)])

    return pd.concat(pieces, ignore_index=True).sort_values(
        ["dimension", "group", "question", "votes", "option"],
        ascending=[True, True, True, False, True],
    ).reset_index(drop=True)


def analyze_time_trends(data: pd.DataFrame) -> pd.DataFrame:
    """Count responses by date and option and calculate daily question shares."""

    frame = _clean_for_analysis(data)
    if frame.empty:
        return _empty_frame(TREND_ANALYSIS_COLUMNS)

    frame = frame.copy()
    frame["response_date"] = frame["response_date"].dt.normalize()
    counts = (
        frame.groupby(["response_date", "question", "option"], as_index=False, dropna=False)
        .size()
        .rename(columns={"size": "votes"})
    )
    counts["date_question_total"] = counts.groupby(["response_date", "question"])["votes"].transform("sum")
    counts["share_percent"] = counts["votes"] / counts["date_question_total"] * 100
    return counts.sort_values(
        ["response_date", "question", "option"]
    ).reset_index(drop=True)[list(TREND_ANALYSIS_COLUMNS)]


def generate_insights(
    data: pd.DataFrame,
    option_analysis: pd.DataFrame | None = None,
    region_analysis: pd.DataFrame | None = None,
    trend_analysis: pd.DataFrame | None = None,
) -> list[str]:
    """Generate short, readable findings from the poll data and analyses."""

    frame = _clean_for_analysis(data)
    if frame.empty:
        return ["No usable poll responses were available for analysis."]

    options = option_analysis if option_analysis is not None else analyze_option_shares(frame)
    regions = region_analysis if region_analysis is not None else analyze_region_shares(frame)
    trends = trend_analysis if trend_analysis is not None else analyze_time_trends(frame)
    insights = [f"The cleaned dataset contains {len(frame):,} responses across {frame['question'].nunique()} questions."]

    top_rows = options.sort_values(["question", "votes", "option"], ascending=[True, False, True])
    for question, group in top_rows.groupby("question", sort=True):
        top = group.iloc[0]
        insights.append(
            f"{question}: {top['option']} was the leading choice with "
            f"{int(top['votes'])} votes ({float(top['share_percent']):.1f}%)."
        )

    if not regions.empty and not top_rows.empty:
        leading_question = str(top_rows.iloc[0]["question"])
        leading_option = str(top_rows.iloc[0]["option"])
        regional = regions[
            (regions["question"] == leading_question) & (regions["option"] == leading_option)
        ]
        if len(regional) >= 2:
            regional = regional.sort_values("share_percent", ascending=False).reset_index(drop=True)
            high = regional.iloc[0]
            low = regional.iloc[-1]
            if high["region"] != low["region"]:
                difference = float(high["share_percent"]) - float(low["share_percent"])
                insights.append(
                    f"For {leading_question}, {leading_option} was most popular in {high['region']} "
                    f"({float(high['share_percent']):.1f}%), {difference:.1f} percentage points above {low['region']}."
                )

    if "satisfaction_score" in frame.columns and frame["satisfaction_score"].notna().any():
        insights.append(
            f"Average satisfaction was {frame['satisfaction_score'].mean():.1f} out of 10 "
            f"(median {frame['satisfaction_score'].median():.1f})."
        )

    if not trends.empty:
        daily = trends.groupby("response_date", as_index=False)["votes"].sum()
        busiest = daily.loc[daily["votes"].idxmax()]
        date_value = pd.Timestamp(busiest["response_date"]).strftime("%Y-%m-%d")
        insights.append(f"The busiest response date was {date_value}, with {int(busiest['votes'])} responses.")

    return insights


# Beginner-friendly aliases for the most common wording of these operations.
clean_data = clean_poll_data
analyze_options = analyze_option_shares
analyze_regions = analyze_region_shares
analyze_demographic = analyze_demographics
analyze_time_trend = analyze_time_trends


def _filter_question(data: pd.DataFrame, question: str | None) -> pd.DataFrame:
    """Return a copy filtered to one question when a question was selected."""

    if question is None or "question" not in data.columns:
        return data
    return data[data["question"].astype(str) == str(question)].copy()


def calculate_option_summary(
    data: pd.DataFrame,
    question: str | None = None,
) -> pd.DataFrame:
    """Dashboard-friendly option summary wrapper."""

    return analyze_option_shares(_filter_question(data, question))


def calculate_region_summary(
    data: pd.DataFrame,
    question: str | None = None,
) -> pd.DataFrame:
    """Dashboard-friendly regional summary wrapper."""

    return analyze_region_shares(_filter_question(data, question))


def calculate_demographic_summary(
    data: pd.DataFrame,
    demographic: str | None = None,
    question: str | None = None,
) -> pd.DataFrame:
    """Return demographic shares, optionally limited to one dimension."""

    summary = analyze_demographics(_filter_question(data, question))
    if demographic is not None and not summary.empty:
        summary = summary[summary["dimension"] == demographic].copy()
    return summary.reset_index(drop=True)


def calculate_trend_summary(
    data: pd.DataFrame,
    question: str | None = None,
) -> pd.DataFrame:
    """Dashboard-friendly response-trend wrapper."""

    return analyze_time_trends(_filter_question(data, question))
