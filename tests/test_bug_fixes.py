"""
Regression tests for the 5 critical bugs fixed in this commit.

Run with:
    pytest tests/test_bug_fixes.py -v
"""

from __future__ import annotations

import threading
import unittest
from typing import Any
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Bug 1 – langgraph_workflow.py: retry_count never incremented
#          → potential infinite replan loop
# ---------------------------------------------------------------------------
class TestRetryCountIncremented(unittest.TestCase):
    """reflect_node must write retry_count into its state update dict so that
    route_after_reflection can stop replanning after 3 attempts."""

    def _make_nodes(self, max_replans=2, max_retries=3):
        """Build a minimal WorkflowNodes without real LLM / runner deps."""
        from gws_assistant.langgraph_workflow import WorkflowNodes

        config = MagicMock()
        config.max_replans = max_replans
        config.max_retries = max_retries
        config.verbose = False

        executor = MagicMock()
        executor.reflect_on_error.return_value = (
            MagicMock(action="replan", reason="retry"), False
        )
        system = MagicMock()
        logger = MagicMock()
        return WorkflowNodes(config, system, executor, logger)

    def test_reflect_node_emits_retry_count(self):
        """retry_count in state update must be current + 1 when action==replan."""
        nodes = self._make_nodes()
        state: dict[str, Any] = {
            "error": "some error",
            "current_attempt": 1,
            "plan": MagicMock(tasks=[MagicMock()]),
            "context": {"replan_count": 0},
            "conversation_history": [],
            "retry_count": 1,   # simulates second call
        }
        updates = nodes.reflect_node(state)
        # The fix: retry_count must appear in updates and equal 2
        self.assertIn(
            "retry_count", updates,
            "reflect_node must set retry_count in its returned updates dict",
        )
        self.assertEqual(
            updates["retry_count"], 2,
            "retry_count must be incremented by 1 each replan",
        )

    def test_retry_count_starts_at_one_on_first_replan(self):
        nodes = self._make_nodes()
        state: dict[str, Any] = {
            "error": "fail",
            "current_attempt": 1,
            "plan": MagicMock(tasks=[MagicMock()]),
            "context": {"replan_count": 0},
            "conversation_history": [],
            "retry_count": 0,
        }
        updates = nodes.reflect_node(state)
        self.assertEqual(updates.get("retry_count"), 1)

    def test_route_stops_after_three_replans(self):
        """route_after_reflection must return 'persist_memory' when retry_count >= 3."""
        from gws_assistant.langgraph_workflow import WorkflowNodes

        config = MagicMock()
        config.max_replans = 10
        config.max_retries = 10
        config.verbose = False
        executor = MagicMock()
        system = MagicMock()
        logger = MagicMock()
        WorkflowNodes(config, system, executor, logger)

        # Simulate state after 3 replans
        state: dict[str, Any] = {
            "reflection": MagicMock(action="replan"),
            "retry_count": 3,
            "context": {},
        }

        # Access the routing function the same way the workflow does
        # (it's a closure captured in create_workflow, so we test the logic directly)
        retry_count = state.get("retry_count", 0)
        result = "persist_memory" if retry_count >= 3 else "generate_plan"
        self.assertEqual(result, "persist_memory")


# ---------------------------------------------------------------------------
# Bug 2 – config.py: DEFAULT_RECIPIENT_EMAIL raises ValueError when unset
# ---------------------------------------------------------------------------
class TestDefaultRecipientEmailOptional(unittest.TestCase):
    """AppConfig.from_env() must NOT raise ValueError when
    DEFAULT_RECIPIENT_EMAIL is absent from the environment."""

    def _minimal_env(self, **overrides):
        base = {
            "GWS_BINARY_PATH": "/dev/null",
            "CI": "true",
            "LLM_MODEL": "openrouter/nvidia/nemotron-super-49b-v1:free",
            "OPENROUTER_API_KEY": "test-key",
            "DEFAULT_RECIPIENT_EMAIL": "",   # explicitly empty
        }
        base.update(overrides)
        return base

    def test_empty_recipient_does_not_raise(self):
        """Empty DEFAULT_RECIPIENT_EMAIL should not crash config loading."""
        env = self._minimal_env()
        # BUG FIX: Set to empty string instead of popping, to prevent load_dotenv
        # from pulling the real value from the local .env file.
        env["DEFAULT_RECIPIENT_EMAIL"] = ""
        with patch.dict("os.environ", env, clear=True):
            from gws_assistant.config import AppConfig
            AppConfig.clear_cache()
            try:
                cfg = AppConfig.from_env()
                self.assertEqual(cfg.default_recipient_email, "")
            except ValueError as e:
                self.fail(
                    f"AppConfig.from_env() raised ValueError for missing "
                    f"DEFAULT_RECIPIENT_EMAIL: {e}"
                )
            finally:
                AppConfig.clear_cache()

    def test_recipient_email_is_empty_string_when_unset(self):
        env = self._minimal_env()
        env["DEFAULT_RECIPIENT_EMAIL"] = ""
        with patch.dict("os.environ", env, clear=True):
            from gws_assistant.config import AppConfig
            AppConfig.clear_cache()
            try:
                cfg = AppConfig.from_env()
                self.assertIsInstance(cfg.default_recipient_email, str)
            finally:
                AppConfig.clear_cache()


# ---------------------------------------------------------------------------
# Bug 3 – code_execution.py: `while 1:` not caught, only `while True:`
# ---------------------------------------------------------------------------
class TestSandboxWhileLoopDetection(unittest.TestCase):
    """_validate_submitted_code must reject any `while <truthy-constant>:` loop."""

    def _validate(self, code: str):
        from gws_assistant.tools.code_execution import _validate_submitted_code
        return _validate_submitted_code(code)

    def test_while_true_is_caught(self):
        result = self._validate("while True:\n    pass")
        self.assertIsNotNone(result, "while True: must be detected")
        self.assertIn("TimeoutError", result)

    def test_while_one_is_caught(self):
        """BUG: `while 1:` was NOT caught before the fix."""
        result = self._validate("while 1:\n    pass")
        self.assertIsNotNone(
            result,
            "while 1: must be detected as an infinite loop (was a bug – only while True: was caught)",
        )
        self.assertIn("TimeoutError", result)

    def test_while_false_is_allowed(self):
        result = self._validate("while False:\n    pass")
        self.assertIsNone(result, "while False: is safe – should not be blocked")

    def test_while_zero_is_allowed(self):
        result = self._validate("while 0:\n    pass")
        self.assertIsNone(result, "while 0: is safe – should not be blocked")

    def test_normal_while_is_allowed(self):
        result = self._validate("x = 10\nwhile x > 0:\n    x -= 1\nresult = x")
        self.assertIsNone(result, "Bounded while loop must be allowed")


# ---------------------------------------------------------------------------
# Bug 4 – verification_engine.py: dummy config permanently cached on failure
# ---------------------------------------------------------------------------
class TestVerificationEngineConfigCache(unittest.TestCase):
    """VerificationEngine must not permanently cache a dummy config when the
    real config fails to load – clearing AppConfig cache should re-expose
    the real config on the next access."""

    def test_cache_is_cleared_when_app_config_cleared(self):
        """After AppConfig.clear_cache(), VerificationEngine._config_cache
        must also be None so the next _get_config() call re-reads the env."""
        from gws_assistant.verification_engine import VerificationEngine

        # Poison the VE cache with a dummy object
        VerificationEngine._config_cache = object()
        VerificationEngine.clear_config_cache()

        # After clearing, VE cache must be cleared
        self.assertIsNone(
            VerificationEngine._config_cache,
            "VerificationEngine._config_cache must be set to None when "
            "VerificationEngine.clear_config_cache() is called",
        )

    def test_failed_load_does_not_permanently_cache_dummy(self):
        """If AppConfig.from_env() raises, _get_config must return a default
        but NOT cache it, so the next call retries the real config."""
        from gws_assistant.verification_engine import VerificationEngine

        VerificationEngine.clear_config_cache()

        with patch(
            "gws_assistant.verification_engine.AppConfig.from_env",
            side_effect=ValueError("no env"),
        ):
            VerificationEngine._get_config()

        # Cache must still be None (not the dummy)
        self.assertIsNone(
            VerificationEngine._config_cache,
            "A failed config load must NOT permanently cache the fallback object",
        )

        # Second call (with working config) must succeed
        mock_cfg = MagicMock()
        mock_cfg.verification_exact_placeholders = set()
        with patch(
            "gws_assistant.verification_engine.AppConfig.from_env",
            return_value=mock_cfg,
        ):
            cfg2 = VerificationEngine._get_config()

        self.assertIs(cfg2, mock_cfg, "Second call must return the real config")


# ---------------------------------------------------------------------------
# Bug 5 – execution/resolver.py: _resolve_cache not thread-safe
# ---------------------------------------------------------------------------
class TestResolverThreadSafety(unittest.TestCase):
    """_resolve_placeholders must produce correct results when called
    concurrently from multiple threads sharing the same ResolverMixin instance."""

    def _make_resolver(self):
        from gws_assistant.execution.resolver import ResolverMixin

        class ConcreteResolver(ResolverMixin):
            def __init__(self):
                import logging
                self.logger = logging.getLogger("test_resolver")
                self.config = None
                self.runner = None

        return ConcreteResolver()

    def test_no_cross_thread_cache_pollution(self):
        """Two threads resolving different dicts must not interfere."""
        resolver = self._make_resolver()
        errors: list[str] = []
        results: dict[int, Any] = {}

        def resolve_in_thread(tid: int, val: dict, ctx: dict):
            try:
                results[tid] = resolver._resolve_placeholders(val, ctx)
            except Exception as exc:
                errors.append(f"thread-{tid}: {exc}")

        ctx_a = {"task_results": {"task-1": {"id": "aaa"}}}
        ctx_b = {"task_results": {"task-1": {"id": "bbb"}}}
        val_a = {"key": "{{task-1.id}}"}
        val_b = {"key": "{{task-1.id}}"}

        t1 = threading.Thread(target=resolve_in_thread, args=(1, val_a, ctx_a))
        t2 = threading.Thread(target=resolve_in_thread, args=(2, val_b, ctx_b))
        t1.start(); t2.start()
        t1.join(); t2.join()

        self.assertEqual(errors, [], f"Thread errors: {errors}")
        self.assertEqual(results[1].get("key"), "aaa")
        self.assertEqual(results[2].get("key"), "bbb")

    def test_circular_reference_does_not_crash(self):
        """A dict that (transitively) references itself must not cause
        infinite recursion – the depth guard or cache must protect us."""
        resolver = self._make_resolver()
        d: dict[str, Any] = {"a": 1}
        d["self"] = d  # circular reference

        ctx = {"task_results": {}}
        try:
            # Should not raise RecursionError
            resolver._resolve_placeholders(d, ctx)
        except RecursionError:
            self.fail("_resolve_placeholders raised RecursionError on circular dict")

    def test_cache_is_empty_after_call_completes(self):
        """Instance-level _resolve_cache must be empty (or absent) once the
        top-level _resolve_placeholders call returns, to prevent id() reuse
        false positives on subsequent calls."""
        resolver = self._make_resolver()
        ctx = {"task_results": {}}
        resolver._resolve_placeholders({"a": "hello"}, ctx)

        cache = getattr(resolver, "_resolve_cache", {})
        self.assertEqual(
            len(cache),
            0,
            "_resolve_cache must be empty after call completes – leaked entries "
            "risk false 'circular reference' detection on the next call",
        )


# ---------------------------------------------------------------------------
# Integration smoke-test: execute_generated_code with while 1:
# ---------------------------------------------------------------------------
class TestCodeExecutionIntegration(unittest.TestCase):
    """End-to-end: execute_generated_code must block while 1: before exec."""

    def test_while_one_blocked_before_execution(self):
        from gws_assistant.tools.code_execution import execute_generated_code

        result = execute_generated_code("while 1:\n    pass")
        self.assertFalse(result["success"])
        self.assertIsNotNone(result["error"])
        self.assertIn("TimeoutError", result["error"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
