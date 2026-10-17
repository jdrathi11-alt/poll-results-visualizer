"""Command-line entry point for the Poll Results Visualizer pipeline.

Run from the project root with ``python main.py``.  A missing, empty, or
invalid input CSV falls back to deterministic synthetic data and stores that
raw sample at ``data/raw_poll_responses.csv``.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

import pandas as pd

from src.analyzer import (
    analyze_demographics,
    analyze_option_shares,
    analyze_region_shares,
    analyze_time_trends,
    clean_poll_data,
    generate_insights,
    load_poll_data,
)
from src.data_generator import DEFAULT_OPTION_MAP, generate_poll_data, save_generated_data
from src.visualizer import create_all_visualizations


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_RAW_PATH = PROJECT_ROOT / "data" / "raw_poll_responses.csv"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "outputs"
DEFAULT_IMAGE_DIR = PROJECT_ROOT / "images"


def _non_negative_int(value: str) -> int:
    """Argparse converter for counts that cannot be negative."""

    number = int(value)
    if number < 0:
        raise argparse.ArgumentTypeError("must be zero or greater")
    return number


def build_parser() -> argparse.ArgumentParser:
    """Build the small, copy-paste-friendly command-line interface."""

    parser = argparse.ArgumentParser(description="Generate and analyze poll results.")
    parser.add_argument(
        "--input",
        type=Path,
        default=None,
        help="CSV input path; defaults to data/raw_poll_responses.csv",
    )
    parser.add_argument(
        "--rows",
        type=_non_negative_int,
        default=500,
        help="Synthetic rows when input is unavailable (default: 500)",
    )
    parser.add_argument("--seed", type=int, default=42, help="Synthetic data seed (default: 42)")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory for analysis CSVs and Markdown report",
    )
    parser.add_argument(
        "--image-dir",
        type=Path,
        default=DEFAULT_IMAGE_DIR,
        help="Directory for PNG charts",
    )
    return parser


def _write_report(
    path: Path,
    data_rows: int,
    question_count: int,
    source_label: str,
    insights: Sequence[str],
    table_names: Sequence[str],
    image_names: Sequence[str],
) -> Path:
    """Write a compact Markdown report that links the generated artifacts."""

    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Poll Results Summary",
        "",
        f"- **Source:** {source_label}",
        f"- **Cleaned responses:** {data_rows:,}",
        f"- **Questions:** {question_count}",
        "",
        "## Key insights",
        "",
    ]
    lines.extend(f"- {insight}" for insight in insights)
    lines.extend(["", "## Analysis tables", ""])
    lines.extend(f"- `{name}`" for name in table_names)
    lines.extend(["", "## Charts", ""])
    lines.extend(f"- `{name}`" for name in image_names)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _generate_fallback(rows: int, seed: int) -> tuple[pd.DataFrame, Path]:
    """Generate and save the fallback raw CSV, returning data and its path."""

    generated = generate_poll_data(rows=rows, seed=seed)
    raw_path = save_generated_data(generated, DEFAULT_RAW_PATH)
    return generated, raw_path


def run_pipeline(args: argparse.Namespace) -> int:
    """Run loading/generation, analysis, visualizations, and report writing."""

    input_path = args.input if args.input is not None else DEFAULT_RAW_PATH
    source_label = str(input_path)

    try:
        data = load_poll_data(input_path)
        if data.empty:
            raise ValueError("the input contains no usable rows")
        data = clean_poll_data(data)
    except (FileNotFoundError, OSError, UnicodeError, ValueError) as exc:
        print(f"Input unavailable ({exc}); generating synthetic data instead.")
        raw_data, generated_path = _generate_fallback(args.rows, args.seed)
        data = clean_poll_data(raw_data, valid_options=DEFAULT_OPTION_MAP)
        source_label = f"generated fallback ({generated_path})"

    option_analysis = analyze_option_shares(data)
    region_analysis = analyze_region_shares(data)
    demographic_analysis = analyze_demographics(data)
    trend_analysis = analyze_time_trends(data)
    insights = generate_insights(
        data,
        option_analysis=option_analysis,
        region_analysis=region_analysis,
        trend_analysis=trend_analysis,
    )

    output_dir = Path(args.output_dir)
    image_dir = Path(args.image_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    image_dir.mkdir(parents=True, exist_ok=True)

    tables = {
        "option_analysis.csv": option_analysis,
        "region_analysis.csv": region_analysis,
        "demographic_analysis.csv": demographic_analysis,
        "time_trend_analysis.csv": trend_analysis,
    }
    for filename, table in tables.items():
        table.to_csv(output_dir / filename, index=False)

    image_paths = create_all_visualizations(
        option_analysis,
        region_analysis,
        demographic_analysis,
        trend_analysis,
        image_dir=image_dir,
    )
    report_path = _write_report(
        output_dir / "poll_report.md",
        len(data),
        int(data["question"].nunique()) if not data.empty else 0,
        source_label,
        insights,
        list(tables),
        [path.name for path in image_paths.values()],
    )

    print(
        f"Poll pipeline complete: {len(data):,} cleaned responses, "
        f"{data['question'].nunique() if not data.empty else 0} questions."
    )
    print(f"Analysis tables and report: {output_dir}")
    print(f"Charts: {len(image_paths)} PNG files in {image_dir} ({report_path.name})")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """Parse arguments and run the pipeline."""

    parser = build_parser()
    args = parser.parse_args(argv)
    return run_pipeline(args)


if __name__ == "__main__":
    raise SystemExit(main())
