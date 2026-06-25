# Repository Guidelines

## Project Structure & Module Organization

This repository is a long-term trading learning workspace. Course material lives in `lessons/` as numbered Markdown files such as `0001-risk-and-return.md`. Reusable reference material goes in `reference/`, and durable progress notes go in `learning-records/`. Shared reusable assets belong in `assets/`.

When a lesson turns into hands-on work, create a numbered top-level practice folder such as `01_交易基础/`, `02_风险管理/`, or `03_回测入门/`. Keep each practice folder self-contained with a short `README.md`, runnable Python files, and example-only config files when needed.

## Build, Test, and Development Commands

- `python -m venv .venv`: create a local Python virtual environment when code exercises begin.
- `python -m py_compile <file.py>`: quick syntax validation for a single Python script.
- `pytest`: preferred test command once a formal test suite exists.

If a practice folder needs dependencies, document installation steps in that folder's `README.md` rather than assuming a global environment.

## Coding Style & Naming Conventions

Use Python 3 with 4-space indentation, `snake_case` names, and small focused functions. Add type hints when they clarify intent. Prefer Markdown for lessons and references, with filenames using a zero-padded numeric prefix for ordered content, for example `0003-position-sizing-basics.md`.

Keep examples educational and explicit. When showing a strategy or signal, also document its assumptions, risks, and validation limits.

## Testing Guidelines

There is no formal test suite yet. For now, validate Python changes with `python -m py_compile` and a manual run of the affected script. When tests are added, place them in a top-level `tests/` directory and name files `test_<module>.py`.

Backtest-oriented changes should record:

- data source and symbol universe
- timeframe and sample period
- fees, slippage, and position sizing assumptions
- key failure modes such as look-ahead bias or overfitting risk

## Commit & Pull Request Guidelines

Use Conventional Commit-style prefixes such as `feat:`, `fix:`, `docs:`, and `chore:`. Keep commit subjects concise and preferably in Chinese after the prefix, for example `docs: 初始化交易学习工作区`.

Pull requests should include:

- a short summary of the learning or code change
- affected paths, for example `lessons/0002-*` or `03_回测入门/`
- validation notes, terminal output, or screenshots when behavior changed

## Security & Risk Tips

Do not commit `.env`, API keys, broker credentials, private account exports, or local-only configs. This repository is for education and research, not financial advice. Avoid wording that implies guaranteed returns or personalized investment recommendations.
