# Optional notebooks

Use this folder for exploratory work that you do not want to put into the
production-style command-line pipeline. A useful notebook sequence is:

1. `01_data_preview.ipynb` — inspect raw rows, types, missing values, and duplicates.
2. `02_exploratory_analysis.ipynb` — reproduce the summary tables and explore additional questions.
3. `03_storytelling.ipynb` — select the three strongest findings and export portfolio screenshots.

The executable source of truth remains in `src/`, `main.py`, and `dashboard.py`.
Keep notebooks reproducible: set a random seed, record the input path, and avoid
committing private survey responses.
