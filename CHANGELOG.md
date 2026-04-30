# Changelog

## [0.0.5] - 2026-04-30
### Fixed
- Resolved `UnboundLocalError` in Gmail header extraction.
- Fixed sandbox escape vulnerability in code execution environment.
- Fixed greedy JSON extraction parsing issues.

## [0.0.4] - 2026-04-30
### Fixed
- Fixed broken type hinting in `telegram_app.py`.
- Resolved circular import risks in `exceptions.py` and `models.py`.
- Tracked side-effects in document creation.

## [0.0.3] - 2026-04-30
### Fixed
- Implemented Singleton pattern for `AppConfig` to maintain consistent state.
- Removed hardcoded test emails from `verification_engine.py`.
- Cleaned up dummy search summarization tool.

## [0.0.2] - 2026-04-30
### Changed
- Default `READ_ONLY_MODE` set to `False` for better out-of-the-box usability.
- Refined `DESTRUCTIVE_ACTIONS` whitelist to exclude benign email sending.

## [0.0.1] - 2026-04-30
### Added
- Initial project release with core Workspace agentic workflows.
- Implemented resolver recursion depth limits.
