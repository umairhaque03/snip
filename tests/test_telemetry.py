"""Unit tests for snip.telemetry.report_install."""

from __future__ import annotations

import json
import sys
from unittest.mock import MagicMock, patch
from urllib.error import URLError

import pytest

import snip.telemetry as telemetry


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _capture_call() -> tuple[MagicMock, MagicMock]:
    """Return (mock_urlopen, mock_request_class) with a successful response."""
    mock_response = MagicMock()
    mock_response.__enter__ = lambda s: s
    mock_response.__exit__ = MagicMock(return_value=False)
    mock_urlopen = MagicMock(return_value=mock_response)
    return mock_urlopen, mock_response


# ---------------------------------------------------------------------------
# Happy-path tests
# ---------------------------------------------------------------------------

class TestReportInstallSuccess:
    def test_calls_urlopen(self):
        mock_urlopen, _ = _capture_call()
        with patch("snip.telemetry.urllib.request.urlopen", mock_urlopen):
            telemetry.report_install()
        mock_urlopen.assert_called_once()

    def test_posts_to_correct_endpoint(self):
        mock_urlopen, _ = _capture_call()
        with patch("snip.telemetry.urllib.request.urlopen", mock_urlopen):
            telemetry.report_install()
        req = mock_urlopen.call_args[0][0]
        assert req.full_url == telemetry._ENDPOINT
        assert req.method == "POST"

    def test_payload_contains_python_version(self):
        mock_urlopen, _ = _capture_call()
        with patch("snip.telemetry.urllib.request.urlopen", mock_urlopen):
            telemetry.report_install()
        req = mock_urlopen.call_args[0][0]
        body = json.loads(req.data)
        assert body["python_version"] == sys.version

    def test_payload_contains_platform(self):
        mock_urlopen, _ = _capture_call()
        with patch("snip.telemetry.urllib.request.urlopen", mock_urlopen):
            telemetry.report_install()
        req = mock_urlopen.call_args[0][0]
        body = json.loads(req.data)
        assert body["platform"] == sys.platform

    def test_authorization_header_contains_anon_key(self):
        mock_urlopen, _ = _capture_call()
        with patch("snip.telemetry.urllib.request.urlopen", mock_urlopen):
            telemetry.report_install()
        req = mock_urlopen.call_args[0][0]
        assert req.get_header("Authorization") == f"Bearer {telemetry.SUPABASE_ANON_KEY}"

    def test_content_type_header(self):
        mock_urlopen, _ = _capture_call()
        with patch("snip.telemetry.urllib.request.urlopen", mock_urlopen):
            telemetry.report_install()
        req = mock_urlopen.call_args[0][0]
        assert req.get_header("Content-type") == "application/json"

    def test_returns_none_on_success(self):
        mock_urlopen, _ = _capture_call()
        with patch("snip.telemetry.urllib.request.urlopen", mock_urlopen):
            result = telemetry.report_install()
        assert result is None

    def test_timeout_is_passed(self):
        mock_urlopen, _ = _capture_call()
        with patch("snip.telemetry.urllib.request.urlopen", mock_urlopen):
            telemetry.report_install()
        _, kwargs = mock_urlopen.call_args
        assert kwargs.get("timeout") == telemetry._TIMEOUT_SECONDS


# ---------------------------------------------------------------------------
# Silent-failure tests — telemetry MUST NEVER raise
# ---------------------------------------------------------------------------

class TestReportInstallSilentFailure:
    def test_silent_on_url_error(self):
        with patch(
            "snip.telemetry.urllib.request.urlopen",
            side_effect=URLError("network unreachable"),
        ):
            # Should not raise
            result = telemetry.report_install()
        assert result is None

    def test_silent_on_timeout_error(self):
        with patch(
            "snip.telemetry.urllib.request.urlopen",
            side_effect=TimeoutError("timed out"),
        ):
            result = telemetry.report_install()
        assert result is None

    def test_silent_on_os_error(self):
        with patch(
            "snip.telemetry.urllib.request.urlopen",
            side_effect=OSError("connection refused"),
        ):
            result = telemetry.report_install()
        assert result is None

    def test_silent_on_value_error(self):
        with patch(
            "snip.telemetry.urllib.request.urlopen",
            side_effect=ValueError("bad URL"),
        ):
            result = telemetry.report_install()
        assert result is None

    def test_silent_on_generic_exception(self):
        with patch(
            "snip.telemetry.urllib.request.urlopen",
            side_effect=Exception("unexpected"),
        ):
            result = telemetry.report_install()
        assert result is None
