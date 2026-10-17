# Changelog

All notable changes to Poll Results Visualizer are documented here.

## [Unreleased]

- Add repository hygiene files, including the MIT license, contribution guide,
  changelog, and GitHub Actions checks.
- Expand ignore rules for local secrets, generated artifacts, and temporary CI
  output.

## [0.1.0] - 2026-10-18

Initial portfolio release. It includes:

- deterministic synthetic poll-response generation with a repeatable seed;
- loading and cleaning for a documented, alias-aware CSV schema;
- option, regional, demographic, and date-trend summaries with short insights;
- four analysis CSVs, a Markdown report, and five headless PNG charts;
- an interactive Streamlit dashboard with filters, tables, charts, insights, and
  filtered CSV download; and
- behavior-focused tests covering generation, cleaning, percentages, insights,
  and dashboard-facing analysis wrappers.
