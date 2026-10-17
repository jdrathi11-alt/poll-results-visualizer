"""Deterministic synthetic poll-response data generation.

The generated rows represent one answer to one poll question.  The small,
explicit probability adjustments make the sample useful for demonstrations:
regions and demographic groups have different preferences instead of every
choice being equally likely.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Final

import numpy as np
import pandas as pd


DEFAULT_OPTION_MAP: Final[dict[str, tuple[str, ...]]] = {
    "Preferred Study Format": ("In-person", "Online", "Hybrid"),
    "Campus Event Interest": ("Very interested", "Somewhat interested", "Not interested"),
    "Best Study Time": ("Morning", "Afternoon", "Evening"),
}

REGIONS: Final[tuple[str, ...]] = ("North", "South", "East", "West", "Central")
AGE_GROUPS: Final[tuple[str, ...]] = ("18-24", "25-34", "35-44", "45+")
GENDERS: Final[tuple[str, ...]] = ("Female", "Male", "Non-binary", "Prefer not to say")

QUESTION_WEIGHTS: Final[tuple[float, ...]] = (0.42, 0.30, 0.28)
REGION_WEIGHTS: Final[tuple[float, ...]] = (0.20, 0.21, 0.19, 0.22, 0.18)
AGE_WEIGHTS: Final[tuple[float, ...]] = (0.40, 0.28, 0.18, 0.14)
GENDER_WEIGHTS: Final[tuple[float, ...]] = (0.47, 0.45, 0.04, 0.04)

# Baseline probabilities are intentionally not uniform.  The adjustments below
# are small enough to remain realistic while making subgroup differences visible.
BASE_PROBABILITIES: Final[dict[str, tuple[float, ...]]] = {
    "Preferred Study Format": (0.36, 0.27, 0.37),
    "Campus Event Interest": (0.34, 0.44, 0.22),
    "Best Study Time": (0.29, 0.38, 0.33),
}

REGION_ADJUSTMENTS: Final[dict[str, dict[str, tuple[float, ...]]]] = {
    "Preferred Study Format": {
        "North": (0.08, -0.03, -0.05),
        "South": (-0.04, 0.06, -0.02),
        "East": (-0.03, 0.09, -0.06),
        "West": (0.02, -0.02, 0.00),
        "Central": (0.05, -0.04, -0.01),
    },
    "Campus Event Interest": {
        "North": (0.05, -0.02, -0.03),
        "South": (-0.02, 0.04, -0.02),
        "East": (0.02, 0.00, -0.02),
        "West": (-0.03, 0.00, 0.03),
        "Central": (0.00, -0.03, 0.03),
    },
    "Best Study Time": {
        "North": (0.05, -0.03, -0.02),
        "South": (-0.03, 0.00, 0.03),
        "East": (0.00, 0.04, -0.04),
        "West": (-0.04, 0.03, 0.01),
        "Central": (0.02, -0.04, 0.02),
    },
}

AGE_ADJUSTMENTS: Final[dict[str, tuple[float, ...]]] = {
    "Preferred Study Format": {
        "18-24": (-0.04, 0.08, -0.04),
        "25-34": (-0.01, 0.03, -0.02),
        "35-44": (0.03, -0.02, -0.01),
        "45+": (0.08, -0.06, -0.02),
    },
    "Campus Event Interest": {
        "18-24": (0.05, 0.00, -0.05),
        "25-34": (0.02, 0.02, -0.04),
        "35-44": (-0.02, 0.03, -0.01),
        "45+": (-0.04, 0.00, 0.04),
    },
    "Best Study Time": {
        "18-24": (0.08, -0.03, -0.05),
        "25-34": (-0.02, 0.03, -0.01),
        "35-44": (-0.05, 0.02, 0.03),
        "45+": (-0.08, -0.01, 0.09),
    },
}

GENDER_ADJUSTMENTS: Final[dict[str, tuple[float, ...]]] = {
    "Preferred Study Format": {
        "Female": (0.01, 0.00, -0.01),
        "Male": (-0.01, 0.01, 0.00),
        "Non-binary": (0.00, 0.02, -0.02),
        "Prefer not to say": (0.00, 0.00, 0.00),
    },
    "Campus Event Interest": {
        "Female": (0.02, 0.00, -0.02),
        "Male": (-0.01, 0.01, 0.00),
        "Non-binary": (0.01, 0.01, -0.02),
        "Prefer not to say": (0.00, 0.00, 0.00),
    },
    "Best Study Time": {
        "Female": (0.00, 0.02, -0.02),
        "Male": (0.01, -0.01, 0.00),
        "Non-binary": (0.00, 0.01, -0.01),
        "Prefer not to say": (0.00, 0.00, 0.00),
    },
}


def _normalised_probabilities(values: Sequence[float]) -> np.ndarray:
    """Return non-negative probabilities that sum to one."""

    probabilities = np.asarray(values, dtype=float)
    probabilities = np.clip(probabilities, 0.001, None)
    return probabilities / probabilities.sum()


def _answer_probabilities(question: str, region: str, age_group: str, gender: str) -> np.ndarray:
    """Build probabilities for one respondent's question and demographics."""

    probabilities = np.asarray(BASE_PROBABILITIES[question], dtype=float)
    probabilities += REGION_ADJUSTMENTS[question][region]
    probabilities += AGE_ADJUSTMENTS[question][age_group]
    probabilities += GENDER_ADJUSTMENTS[question][gender]
    return _normalised_probabilities(probabilities)


def generate_poll_data(
    rows: int = 500,
    seed: int = 42,
    start_date: str | pd.Timestamp = "2024-01-01",
    days: int = 120,
) -> pd.DataFrame:
    """Generate deterministic, patterned synthetic poll responses.

    Parameters
    ----------
    rows:
        Number of response rows to create.  A value of zero returns an empty
        frame with the documented columns.
    seed:
        Seed passed to NumPy's generator, making repeated runs reproducible.
    start_date:
        First possible response date.
    days:
        Number of calendar days covered by the sample.

    Returns
    -------
    pandas.DataFrame
        Columns are ``response_id``, ``response_date``, ``question``,
        ``option``, ``region``, ``age_group``, ``gender``, and the optional
        numeric ``satisfaction_score``.
    """

    if rows < 0:
        raise ValueError("rows must be zero or greater")
    if days < 1:
        raise ValueError("days must be at least 1")

    rng = np.random.default_rng(seed)
    questions = tuple(DEFAULT_OPTION_MAP)

    question_values = rng.choice(questions, size=rows, p=QUESTION_WEIGHTS)
    regions = rng.choice(REGIONS, size=rows, p=REGION_WEIGHTS)
    age_groups = rng.choice(AGE_GROUPS, size=rows, p=AGE_WEIGHTS)
    genders = rng.choice(GENDERS, size=rows, p=GENDER_WEIGHTS).astype(object)
    # A small amount of non-response is useful for demonstrating cleaning.
    if rows:
        genders[rng.random(rows) < 0.02] = np.nan

    date_offsets = rng.integers(0, days, size=rows)
    response_dates = pd.Timestamp(start_date) + pd.to_timedelta(date_offsets, unit="D")

    options = np.empty(rows, dtype=object)
    satisfaction = np.empty(rows, dtype=float)
    satisfaction[:] = np.nan

    satisfaction_option_effects = {
        "In-person": 0.20,
        "Online": -0.05,
        "Hybrid": 0.35,
        "Very interested": 0.55,
        "Somewhat interested": 0.10,
        "Not interested": -0.60,
        "Morning": 0.05,
        "Afternoon": 0.15,
        "Evening": 0.25,
    }
    satisfaction_region_effects = {"North": 0.15, "South": -0.10, "East": 0.05, "West": 0.20, "Central": -0.05}
    satisfaction_age_effects = {"18-24": 0.00, "25-34": 0.10, "35-44": 0.20, "45+": 0.30}

    for index, question in enumerate(question_values):
        gender = genders[index]
        gender_key = "Prefer not to say" if pd.isna(gender) else str(gender)
        options[index] = rng.choice(
            DEFAULT_OPTION_MAP[question],
            p=_answer_probabilities(question, regions[index], age_groups[index], gender_key),
        )
        satisfaction[index] = (
            6.1
            + satisfaction_option_effects[str(options[index])]
            + satisfaction_region_effects[regions[index]]
            + satisfaction_age_effects[age_groups[index]]
            + rng.normal(0, 0.85)
        )

    satisfaction = np.clip(np.round(satisfaction, 1), 1.0, 10.0)
    if rows:
        satisfaction[rng.random(rows) < 0.04] = np.nan

    return pd.DataFrame(
        {
            "response_id": [f"R{number:06d}" for number in range(1, rows + 1)],
            "response_date": pd.to_datetime(response_dates),
            "question": question_values,
            "option": options,
            "region": regions,
            "age_group": age_groups,
            "gender": genders,
            "satisfaction_score": satisfaction,
        }
    )


def save_generated_data(data: pd.DataFrame, path: str | Path) -> Path:
    """Create the parent directory and save generated responses as CSV."""

    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    data.to_csv(destination, index=False)
    return destination


def generate_synthetic_poll_data(
    n_rows: int = 2000,
    seed: int = 42,
    **kwargs: object,
) -> pd.DataFrame:
    """Compatibility wrapper with the name used by the Streamlit dashboard.

    ``generate_poll_data`` is the canonical function for the command-line
    pipeline. This small wrapper keeps the more conversational ``n_rows``
    spelling available for dashboard users and tutorial readers.
    """

    return generate_poll_data(rows=n_rows, seed=seed, **kwargs)
