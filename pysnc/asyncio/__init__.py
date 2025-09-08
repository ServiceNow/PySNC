"""
Asynchronous implementation of the pysnc package using httpx.AsyncClient.
"""

try:
    from .client import AsyncTableAPI, AsyncBatchAPI, AsyncAttachmentAPI, AsyncServiceNowClient
    from .record import AsyncGlideRecord
    from .attachment import AsyncAttachment
    from .auth import AsyncServiceNowFlow, AsyncServiceNowPasswordGrantFlow, AsyncServiceNowJWTAuth
except ImportError:
    raise ImportError("httpx is required for the asyncio module. Please install pysnc with the 'asyncio' extra.")


__all__ = [
    'AsyncServiceNowClient',
    'AsyncTableAPI',
    'AsyncBatchAPI',
    'AsyncAttachmentAPI',
    'AsyncGlideRecord',
    'AsyncAttachment',
    'AsyncServiceNowFlow',
    'AsyncServiceNowPasswordGrantFlow',
    'AsyncServiceNowJWTAuth'
]
