"""Logging and tracing setup for Glider."""

from __future__ import annotations

import logfire

from glider.config import settings


def configure_logfire() -> None:
    logfire.configure(
        service_name=settings.logfire_service_name,
        environment=settings.logfire_environment,
        token=settings.logfire_token,
        console=logfire.ConsoleOptions(
            colors="auto",
            verbose=True,
        )
        if settings.logfire_console_enabled
        else False,
        send_to_logfire="if-token-present",
    )
    logfire.instrument_httpx()
