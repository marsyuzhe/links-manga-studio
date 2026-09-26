# Contributing

Thanks for helping improve Links Manga Studio. Project contributions are under Apache-2.0 as described in LICENSE and its contribution clause. Contributors retain their copyright. Suggested branch prefixes include feature/, fix/, docs/ and refactor/; they are not mandatory.

1. Fork the repository and make a branch from the default branch (for example, `feature/short-description` or `fix/short-description`).
2. On Windows with Python 3.11 or 3.12, create a virtual environment and install `pip install -e ".[test,imaging]"`.
3. Run `python -m app.main` to inspect behavior and `python -m pytest -q --ignore=tests/test_full_workflow.py` with `QT_QPA_PLATFORM=offscreen` for the core suite. Run the 1,000-page end-to-end test if your change affects import, page loading, rendering or export performance.
4. Keep changes focused. Use readable Python, type hints where helpful, stable Page/Text UIDs, explicit SQLite transactions for core edits, and tests for meaningful behavior. Avoid bundling user files or proprietary fonts/models.
5. Open a pull request with a summary, affected workflow, test results, and synthetic-content screenshots for UI changes. Mention migrations and compatibility risks.

For a bug report, include app version, Windows version and display scaling, steps to reproduce, expected and actual results, and sanitized logs/screenshots. Remove project paths, personal data and copyrighted page content before uploading. Please report security issues privately as described in [SECURITY.md](SECURITY.md).
