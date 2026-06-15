"""Foundation tests for TASK-001."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from tiewtrade.application.bootstrap import ApplicationBootstrap
from tiewtrade.shared.services.configuration import load_app_config


class FoundationTests(unittest.TestCase):
    def test_load_app_config_uses_environment_overrides(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp) / "data"
            log_dir = Path(tmp) / "logs"
            config = load_app_config(
                environ={
                    "TIEWTRADE_ENV": "test",
                    "TIEWTRADE_LOG_LEVEL": "debug",
                    "TIEWTRADE_DATA_DIR": str(data_dir),
                    "TIEWTRADE_LOG_DIR": str(log_dir),
                }
            )

            self.assertEqual(config.environment, "test")
            self.assertEqual(config.log_level, "DEBUG")
            self.assertEqual(config.data_dir, data_dir)
            self.assertEqual(config.log_dir, log_dir)
            self.assertEqual(config.log_file, log_dir / "tiewtrade.log")

    def test_load_app_config_empty_environment_does_not_use_process_environment(self) -> None:
        original_env = os.environ.get("TIEWTRADE_ENV")
        os.environ["TIEWTRADE_ENV"] = "process-env-should-not-be-used"
        try:
            config = load_app_config(environ={})
        finally:
            if original_env is None:
                os.environ.pop("TIEWTRADE_ENV", None)
            else:
                os.environ["TIEWTRADE_ENV"] = original_env

        self.assertEqual(config.environment, "development")

    def test_bootstrap_creates_directories_and_logger(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp) / "data"
            log_dir = Path(tmp) / "logs"
            context = ApplicationBootstrap(
                environ={
                    "TIEWTRADE_DATA_DIR": str(data_dir),
                    "TIEWTRADE_LOG_DIR": str(log_dir),
                }
            ).initialize()

            self.assertTrue(data_dir.exists())
            self.assertTrue(log_dir.exists())
            self.assertEqual(context.logger.name, "tiewtrade")

    def test_logging_redacts_sensitive_values(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log_dir = Path(tmp) / "logs"
            context = ApplicationBootstrap(
                environ={
                    "TIEWTRADE_DATA_DIR": str(Path(tmp) / "data"),
                    "TIEWTRADE_LOG_DIR": str(log_dir),
                }
            ).initialize()

            context.logger.error("api_secret=my-secret license=abc123 token=xyz")
            context.logger.error('{"api_secret": "json-secret", "token": "json-token"}')
            for handler in context.logger.handlers:
                handler.flush()

            log_text = (log_dir / "tiewtrade.log").read_text(encoding="utf-8")

            self.assertNotIn("my-secret", log_text)
            self.assertNotIn("abc123", log_text)
            self.assertNotIn("xyz", log_text)
            self.assertNotIn("json-secret", log_text)
            self.assertNotIn("json-token", log_text)
            self.assertIn("[REDACTED]", log_text)

    def test_logging_redacts_sensitive_structured_args(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log_dir = Path(tmp) / "logs"
            context = ApplicationBootstrap(
                environ={
                    "TIEWTRADE_DATA_DIR": str(Path(tmp) / "data"),
                    "TIEWTRADE_LOG_DIR": str(log_dir),
                }
            ).initialize()

            context.logger.error(
                "structured credentials %s",
                {
                    "api_secret": "dict-secret",
                    "nested": {"token": "nested-token"},
                    "items": [{"license": "license-secret"}],
                    "signature": 987654321,
                    "safe": "safe-value",
                },
            )
            context.logger.error(
                "tuple credentials %s %s",
                {"api_secret": "tuple-secret"},
                ["token=tuple-token"],
            )
            context.logger.error(
                "mapping credentials %(api_key)s %(safe)s",
                {"api_key": "mapped-secret", "safe": "mapped-safe"},
            )
            for handler in context.logger.handlers:
                handler.flush()

            log_text = (log_dir / "tiewtrade.log").read_text(encoding="utf-8")

            self.assertNotIn("dict-secret", log_text)
            self.assertNotIn("nested-token", log_text)
            self.assertNotIn("license-secret", log_text)
            self.assertNotIn("987654321", log_text)
            self.assertNotIn("tuple-secret", log_text)
            self.assertNotIn("tuple-token", log_text)
            self.assertNotIn("mapped-secret", log_text)
            self.assertIn("safe-value", log_text)
            self.assertIn("mapped-safe", log_text)
            self.assertIn("[REDACTED]", log_text)

    def test_logging_redaction_regression_for_structured_sensitive_keys(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log_dir = Path(tmp) / "logs"
            context = ApplicationBootstrap(
                environ={
                    "TIEWTRADE_DATA_DIR": str(Path(tmp) / "data"),
                    "TIEWTRADE_LOG_DIR": str(log_dir),
                }
            ).initialize()

            context.logger.warning(
                "payload %s",
                {
                    "api-key": "dash-key-secret",
                    "license_token": "compound-license-secret",
                    "account": {"api_secret": "nested-dict-secret"},
                    "orders": [{"signature": "nested-list-signature"}],
                    "visible": "visible-value",
                },
            )
            for handler in context.logger.handlers:
                handler.flush()

            log_text = (log_dir / "tiewtrade.log").read_text(encoding="utf-8")

            self.assertNotIn("dash-key-secret", log_text)
            self.assertNotIn("compound-license-secret", log_text)
            self.assertNotIn("nested-dict-secret", log_text)
            self.assertNotIn("nested-list-signature", log_text)
            self.assertIn("visible-value", log_text)
            self.assertIn("[REDACTED]", log_text)


if __name__ == "__main__":
    unittest.main()
