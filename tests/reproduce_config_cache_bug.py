
import os
import unittest

from gws_assistant.config import AppConfig
from gws_assistant.models import AppConfigModel
from gws_assistant.verification_engine import VerificationEngine


class TestConfigCacheBug(unittest.TestCase):
    def setUp(self):
        AppConfig.clear_cache()
        VerificationEngine.clear_cache()
        # Clean up env
        self.old_env = os.environ.copy()
        if "DEFAULT_RECIPIENT_EMAIL" in os.environ:
            del os.environ["DEFAULT_RECIPIENT_EMAIL"]
        if "GWS_BINARY_PATH" in os.environ:
            del os.environ["GWS_BINARY_PATH"]

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self.old_env)
        AppConfig.clear_cache()
        VerificationEngine.clear_cache()

    def test_reproduce_cache_bug(self):
        # 1. Trigger failure in AppConfig.from_env()
        # Ensure it fails
        with self.assertRaises(ValueError):
            AppConfig.from_env()

        # 2. Call VerificationEngine._get_config() which should cache VerificationDefaults
        config1 = VerificationEngine._get_config()
        # It should be VerificationDefaults, not AppConfigModel
        self.assertNotIsInstance(config1, AppConfigModel)
        self.assertTrue(hasattr(config1, "verification_exact_placeholders"))

        # 3. Fix environment and clear AppConfig cache
        os.environ["DEFAULT_RECIPIENT_EMAIL"] = "test@example.com"
        os.environ["GWS_BINARY_PATH"] = "dummy_path"
        AppConfig.clear_cache()

        # Mocking Path.exists to avoid real file checks if needed,
        # but AppConfig might still fail if dummy_path doesn't exist.
        # Let's use CI=true to skip some checks.
        os.environ["CI"] = "true"

        # 4. Verify AppConfig.from_env() now succeeds
        config2 = AppConfig.from_env()
        self.assertIsInstance(config2, AppConfigModel)
        self.assertEqual(config2.default_recipient_email, "test@example.com")

        # 5. BUG: VerificationEngine._get_config() still returns the OLD cached VerificationDefaults
        config3 = VerificationEngine._get_config()

        print(f"Config3 type: {type(config3)}")

        # This is expected to FAIL if the bug is present (it will be VerificationDefaults)
        # We WANT it to be the same as config2
        self.assertIsInstance(config3, AppConfigModel, "VerificationEngine should have picked up the new AppConfig")
        self.assertEqual(config3.default_recipient_email, "test@example.com")

if __name__ == "__main__":
    unittest.main()
