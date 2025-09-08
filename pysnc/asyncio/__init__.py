"""
Asynchronous implementation of the pysnc package using httpx.AsyncClient.
"""

try:
    from .attachment import AsyncAttachment
    from .auth import (
        AsyncServiceNowFlow,
        AsyncServiceNowJWTAuth,
        AsyncServiceNowPasswordGrantFlow,
    )
    from .client import (
        AsyncAttachmentAPI,
        AsyncBatchAPI,
        AsyncServiceNowClient,
        AsyncTableAPI,
    )
    from .record import AsyncGlideRecord
except ImportError:
    raise ImportError("httpx is required for the asyncio module. Please install pysnc with the 'asyncio' extra.")

__all__ = [
    "AsyncServiceNowClient",
    "AsyncTableAPI",
    "AsyncBatchAPI",
    "AsyncAttachmentAPI",
    "AsyncGlideRecord",
    "AsyncAttachment",
    "AsyncServiceNowFlow",
    "AsyncServiceNowPasswordGrantFlow",
    "AsyncServiceNowJWTAuth",
]
