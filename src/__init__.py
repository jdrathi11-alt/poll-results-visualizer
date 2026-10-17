"""Core analytics pipeline for the Poll Results Visualizer.

The most commonly used functions are re-exported here so a beginner can
start with ``from src import generate_poll_data, clean_poll_data``.
"""

from .analyzer import (
    analyze_demographics,
    analyze_option_shares,
    analyze_region_shares,
    analyze_time_trends,
    calculate_demographic_summary,
    calculate_option_summary,
    calculate_region_summary,
    calculate_trend_summary,
    clean_poll_data,
    generate_insights,
    load_poll_data,
)
from .data_generator import (
    generate_poll_data,
    generate_synthetic_poll_data,
    save_generated_data,
)

__all__ = [
    "analyze_demographics",
    "analyze_option_shares",
    "analyze_region_shares",
    "analyze_time_trends",
    "calculate_demographic_summary",
    "calculate_option_summary",
    "calculate_region_summary",
    "calculate_trend_summary",
    "clean_poll_data",
    "generate_insights",
    "generate_poll_data",
    "generate_synthetic_poll_data",
    "load_poll_data",
    "save_generated_data",
]
