"""Custom exceptions for the assistant."""


class AssistantError(Exception):
    """Base class for assistant errors."""


class ConfigurationError(AssistantError):
    """Raised when config is invalid."""


class ValidationError(AssistantError):
    """Raised when user input is invalid."""


class CommandExecutionError(AssistantError):
    """Raised when gws execution fails."""


class IntentParsingError(AssistantError):
    """Raised when intent parsing fails."""

