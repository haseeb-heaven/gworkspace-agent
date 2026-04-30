# Changelog

## [0.0.10] - 2026-04-30
### Added
- Added `Mem0` host configuration.
- Added `TELEGRAM_CHAT_ID` support.

## [0.0.9] - 2026-04-30
### Fixed
- Fixed memory leakage in `resolver.py`.
- Improved task planning resilience.

## [0.0.8] - 2026-04-30
### Changed
- Refactored `executor.py` for cleaner logging.
- Updated dependencies in `pyproject.toml`.

## [0.0.7] - 2026-04-30
### Added
- Support for `E2B` sandbox backend.
- Added `GWS_TIMEOUT_SECONDS` config.

## [0.0.6] - 2026-04-30
### Added
- Added `LLM_FALLBACK_MODEL` series for increased reliability.
- Implemented tool-calling validation in `model_registry.py`.

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
