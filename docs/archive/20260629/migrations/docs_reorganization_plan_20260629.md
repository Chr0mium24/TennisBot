# Documentation Reorganization Plan

Date: 2026-06-29

## Objective

Move the crowded `docs/` root into a stable structure without deleting history.

## Planned Structure

- `docs/README.md`: entry point and navigation.
- `docs/current/`: current architecture, status, runbook, and operator-facing
  docs.
- `docs/reports/`: formal reports and their assets.
- `docs/archive/YYYYMMDD/`: dated plans, results, probes, audits, reviews, and
  migration records.

## Scope

- Move existing Markdown and report assets only.
- Preserve historical files instead of rewriting them.
- Update the current docs that still describe obsolete tool boundaries.
- Do not run application tests unless code changes are introduced.

## Validation

- Check `git status --short` for intended moves only.
- Check `git diff --check`.
- Confirm `docs/` root contains only `README.md` and directory entries.
