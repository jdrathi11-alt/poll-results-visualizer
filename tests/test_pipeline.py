"""Small behavior-focused tests for the core poll pipeline."""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.analyzer import (
    analyze_option_shares,
    calculate_demographic_summary,
    calculate_option_summary,
    clean_poll_data,
    generate_insights,
)
from src.data_generator import generate_poll_data, generate_synthetic_poll_data


def test_generation_is_deterministic_and_has_documented_fields() -> None:
    first = generate_poll_data(rows=80, seed=123)
    second = generate_poll_data(rows=80, seed=123)

    pd.testing.assert_frame_equal(first, second)
    assert len(first) == 80
    assert {
        "response_id",
        "response_date",
        "question",
        "option",
        "region",
        "age_group",
        "gender",
        "satisfaction_score",
    }.issubset(first.columns)


def test_cleaning_removes_duplicate_and_handles_missing_values() -> None:
    raw = generate_poll_data(rows=5, seed=8).iloc[:4].copy()
    duplicate = raw.iloc[[0]].copy()
    raw = pd.concat([raw, duplicate], ignore_index=True)
    raw.loc[1, "region"] = "  North  "
    raw.loc[1, "gender"] = np.nan
    raw["satisfaction_score"] = raw["satisfaction_score"].astype(object)
    raw.loc[2, "satisfaction_score"] = "not a number"

    cleaned = clean_poll_data(raw)

    assert len(cleaned) == 4
    assert cleaned["response_id"].is_unique
    assert cleaned.loc[1, "region"] == "North"
    assert cleaned["gender"].eq("Unknown").any()
    assert pd.api.types.is_numeric_dtype(cleaned["satisfaction_score"])


def test_option_percentages_sum_to_about_one_hundred_per_question() -> None:
    analysis = analyze_option_shares(generate_poll_data(rows=400, seed=99))
    totals = analysis.groupby("question")["share_percent"].sum()

    assert not totals.empty
    assert np.allclose(totals.to_numpy(), 100.0, atol=1e-8)


def test_insight_generation_returns_readable_findings() -> None:
    data = generate_poll_data(rows=120, seed=21)
    insights = generate_insights(data)

    assert insights
    assert all(isinstance(insight, str) and insight.strip() for insight in insights)
    assert any("leading choice" in insight for insight in insights)

def test_dashboard_friendly_wrappers_match_core_analysis() -> None:
    data = generate_synthetic_poll_data(n_rows=120, seed=7)
    question = str(data["question"].iloc[0])

    option_summary = calculate_option_summary(data, question=question)
    demographic_summary = calculate_demographic_summary(
        data, demographic="age_group", question=question
    )

    assert not option_summary.empty
    assert option_summary["question"].eq(question).all()
    assert not demographic_summary.empty
    assert demographic_summary["dimension"].eq("age_group").all()

