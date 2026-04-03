import os
import pytest
from nicode_claw.config import Settings


def test_settings_from_env(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token-123")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")
    monkeypatch.setenv("MODE", "polling")

    settings = Settings.from_env()

    assert settings.telegram_bot_token == "test-token-123"
    assert settings.openai_api_key == "sk-test-key"
    assert settings.mode == "polling"
    assert settings.webhook_url is None


def test_settings_webhook_mode(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("MODE", "webhook")
    monkeypatch.setenv("WEBHOOK_URL", "https://example.com/webhook")

    settings = Settings.from_env()

    assert settings.mode == "webhook"
    assert settings.webhook_url == "https://example.com/webhook"


def test_settings_missing_token(monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with pytest.raises(ValueError):
        Settings.from_env()
