"""Abstract base class for human gates."""

from abc import ABC, abstractmethod


class HumanGateBase(ABC):
    """Abstract base class defining the human gate interface."""

    @abstractmethod
    async def ask_text(self, question: str, context: str = "", timeout: float = 300) -> str:
        """
        Ask the user a free-text question.

        Args:
            question: The question to ask.
            context: Additional context to provide to the user.
            timeout: Maximum time to wait for a response, in seconds.

        Returns:
            The text response from the user.

        Raises:
            TimeoutError: If the user doesn't respond within the timeout.
        """
        pass

    @abstractmethod
    async def ask_approval(self, action: str, details: str, timeout: float = 60) -> bool:
        """
        Ask the user to approve or reject an action.

        Args:
            action: The action to perform.
            details: Details about the action.
            timeout: Maximum time to wait for a response, in seconds.

        Returns:
            True if approved, False if rejected.

        Raises:
            TimeoutError: If the user doesn't respond within the timeout.
        """
        pass

    @abstractmethod
    async def ask_choice(self, question: str, choices: list[str], timeout: float = 120) -> str:
        """
        Ask the user to select from a list of choices.

        Args:
            question: The question to ask.
            choices: The available choices.
            timeout: Maximum time to wait for a response, in seconds.

        Returns:
            The selected choice string.

        Raises:
            TimeoutError: If the user doesn't respond within the timeout.
        """
        pass

    @abstractmethod
    async def notify(self, message: str) -> None:
        """
        Send a one-way status notification to the user.

        Args:
            message: The message to send.
        """
        pass
