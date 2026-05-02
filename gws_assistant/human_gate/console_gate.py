"""Console fallback implementation for the human gate."""

import asyncio
import logging

from gws_assistant.human_gate.base import HumanGateBase

logger = logging.getLogger(__name__)


class ConsoleFallbackGate(HumanGateBase):
    """Fallback implementation that uses the console (CLI) to prompt the user."""

    def _sync_ask_text(self, question: str, context: str) -> str:
        if context:
            print(f"\nContext: {context}")
        return input(f"\n❓ {question}\n> ")

    async def ask_text(self, question: str, context: str = "", timeout: float = 300) -> str:
        """Ask a free-text question using the console."""
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(self._sync_ask_text, question, context),
                timeout=timeout
            )
        except asyncio.TimeoutError:
            print("\n⏰ Timeout — action cancelled")
            raise TimeoutError("Timed out waiting for input")

    def _sync_ask_approval(self, action: str, details: str) -> bool:
        print(f"\n⚠️ Approval Required")
        print(f"Action: {action}")
        print(f"Details: {details}")
        while True:
            resp = input("Do you approve? [y/N]: ").strip().lower()
            if resp in ("y", "yes"):
                return True
            if resp in ("n", "no", ""):
                return False

    async def ask_approval(self, action: str, details: str, timeout: float = 60) -> bool:
        """Ask for approval using the console."""
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(self._sync_ask_approval, action, details),
                timeout=timeout
            )
        except asyncio.TimeoutError:
            print("\n⏰ Timeout — action cancelled")
            raise TimeoutError("Timed out waiting for approval")

    def _sync_ask_choice(self, question: str, choices: list[str]) -> str:
        if not choices:
            raise ValueError("choices cannot be empty")
        print(f"\n❓ {question}")
        for i, choice in enumerate(choices, 1):
            print(f"  {i}. {choice}")
        while True:
            resp = input(f"Select an option (1-{len(choices)}): ").strip()
            if resp.isdigit():
                idx = int(resp) - 1
                if 0 <= idx < len(choices):
                    return choices[idx]

    async def ask_choice(self, question: str, choices: list[str], timeout: float = 120) -> str:
        """Ask for a choice using the console."""
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(self._sync_ask_choice, question, choices),
                timeout=timeout
            )
        except asyncio.TimeoutError:
            print("\n⏰ Timeout — action cancelled")
            raise TimeoutError("Timed out waiting for choice")

    def _sync_notify(self, message: str) -> None:
        print(f"\nℹ️ {message}")

    async def notify(self, message: str) -> None:
        """Send a notification using the console."""
        await asyncio.to_thread(self._sync_notify, message)

    async def start(self):
        """Start the console gate (no-op)."""
        pass

    async def stop(self):
        """Stop the console gate (no-op)."""
        pass

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.stop()
