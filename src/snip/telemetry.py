"""
Anonymous install telemetry for snip.

Sends a single fire-and-forget POST to a Supabase Edge Function when
`snip init` completes successfully. The only data sent is Python version
and OS platform. No personally identifiable information is collected.

To activate: replace the TODO constants below with your Supabase project
values from Settings → API in the Supabase dashboard.
"""

from __future__ import annotations

import json
import sys
import urllib.request

# ---------------------------------------------------------------------------
# Constants — replace with your Supabase project values
# ---------------------------------------------------------------------------

SUPABASE_URL: str = "https://jvuolopjgaogffbrxlld.supabase.co"

SUPABASE_ANON_KEY: str = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imp2dW9sb3BqZ2FvZ2ZmYnJ4bGxkIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzM5MjQ4MjIsImV4cCI6MjA4OTUwMDgyMn0.7rGDI-N5NGdH4AsMEnefanNnGIFgHFYJan47AMV8iNY"

_ENDPOINT = f"{SUPABASE_URL}/functions/v1/log-install"
_TIMEOUT_SECONDS = 5


def report_install() -> None:
    """POST an anonymous install event to the Supabase Edge Function.

    Always returns None. All exceptions are silently swallowed — telemetry
    must never block or error the user.
    """
    try:
        payload = json.dumps(
            {
                "python_version": sys.version,
                "platform": sys.platform,
            }
        ).encode()

        req = urllib.request.Request(
            _ENDPOINT,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {SUPABASE_ANON_KEY}",
            },
            method="POST",
        )
        urllib.request.urlopen(req, timeout=_TIMEOUT_SECONDS)  # noqa: S310
    except Exception:  # noqa: BLE001
        pass
