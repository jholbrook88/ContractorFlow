"""Delivery boundary. Only a local preview adapter is enabled in this release."""

from typing import Protocol

from config import delivery_mode


class DeliveryService(Protocol):
    def deliver(self, message: dict[str, object]) -> str:
        """Return a local receipt; future providers must honor event_key idempotency."""
        ...


class LocalPreviewService:
    def deliver(self, message: dict[str, object]) -> str:
        # Nothing is sent or written outside the application's SQLite outbox.
        return f"local-preview:{message['event_key']}"


def configured_service() -> DeliveryService:
    mode = delivery_mode()
    if mode != "local":
        raise ValueError("Only local preview delivery is enabled. No email provider is configured.")
    return LocalPreviewService()
