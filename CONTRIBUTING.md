# Contributing

Thank you for helping improve Poll Results Visualizer. Small, focused changes
are welcome, especially improvements that keep the analysis reproducible and
easy for beginners to understand.

## Set up locally

1. Install Python 3.10 or newer and open a terminal at the repository root.
2. Create and activate a virtual environment:

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

   On Windows PowerShell, use `py -m venv .venv` followed by
   `.\.venv\Scripts\Activate.ps1`.
3. Install the project dependencies:

   ```bash
   python -m pip install --upgrade pip
   python -m pip install -r requirements.txt
   ```
4. Run the test suite before making changes and again before opening a pull
   request:

   ```bash
   pytest -q
   ```

The batch pipeline can be exercised with `python main.py --rows 25 --seed 42`.
Use custom output and image directories when experimenting so generated files
do not replace the portfolio artifacts.

## Branches and commits

- Create a topic branch from `main`; do not work directly on `main`.
- Use a short, descriptive branch name such as `feature/dashboard-filter` or
  `docs/update-contributing`.
- Keep each commit focused on one logical change.
- Use an imperative, conventional-style subject such as `feat: add region
  filter`, `fix: handle empty poll input`, `test: cover duplicate rows`, or
  `docs: clarify setup`.
- Rebase or update your branch from `main` before requesting review when it has
  fallen behind.

## Documentation and screenshots

Update `README.md` when commands, inputs, outputs, or user-facing behavior
change. Keep examples copy-pasteable and explain whether a result is synthetic
or based on sanitized real data. Add only curated, non-sensitive dashboard
captures under `images/screenshots/`, using descriptive filenames and Markdown
alt text. Generated charts belong in the local `images/` output area and should
not be used to hide a missing test or documentation update.

## Data privacy and responsible analysis

- Never commit private survey responses, direct identifiers, credentials,
  tokens, API keys, or local environment files.
- Use synthetic data or a sanitized, approved CSV for examples and screenshots.
- Review generated CSVs, reports, charts, and screenshots before sharing them.
- Document the source and limitations of any real data, and avoid claims that
  descriptive percentages establish causation or generalize to a population.
- Remove or aggregate small groups when publishing comparisons could identify
  respondents.

## Pull-request checklist

Before opening a pull request, confirm that:

- [ ] The change is on a focused topic branch and the commits have clear
      messages.
- [ ] `pytest -q` passes locally.
- [ ] The relevant CLI, dashboard, or documentation path was checked manually.
- [ ] README or other documentation and screenshots were updated when needed.
- [ ] No private data, secrets, generated raw inputs, or accidental local files
      are included.
- [ ] New behavior has an appropriate test, or the pull request explains why a
      test is not needed.
- [ ] The pull request description explains the user-facing change and any
      limitations.
