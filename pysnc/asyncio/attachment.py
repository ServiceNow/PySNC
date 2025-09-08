import logging
import traceback
from pathlib import Path
from tempfile import SpooledTemporaryFile
from typing import TYPE_CHECKING, Any, BinaryIO, Dict, List, Optional, Union

from ..attachment import Attachment
from ..exceptions import NotFoundException, RequestException
from ..query import Query

if TYPE_CHECKING:
    from .client import AsyncServiceNowClient


class AsyncAttachment(Attachment):
    """
    Asynchronous implementation of Attachment for ServiceNow.

    This class provides an async interface for working with ServiceNow attachments.
    """

    # TODO refactor this to use a .get method
    def __init__(self, client, table):
        """
        :param str table: the table we are associated with
        """
        super().__init__(client, table)
        self._log = logging.getLogger(__name__)

    def __iter__(self):
        # Block sync iteration to avoid calling async query() from a sync context
        raise TypeError("AsyncAttachment is async-iterable. Use `async for` instead of `for`.")

    def __next__(self):
        raise TypeError("AsyncAttachment is async-iterable. Use `async for` and `__anext__`.")

    def __aiter__(self):
        # mirror the sync class behavior, but for async iteration
        # reset iteration state
        self._Attachment__is_iter = True
        self._Attachment__current = -1
        return self

    async def __anext__(self):
        return await self.next()

    async def next(self, _recursive: bool = False):
        """
        Async variant of .next()

        Returns:
            self on success, or raises StopAsyncIteration when done (if used via `async for`)
            If not iterating, returns True/False like the sync API.
        """
        l = len(self._Attachment__results)
        if l > 0 and self._Attachment__current + 1 < l:
            self._Attachment__current = self._Attachment__current + 1
            if self._Attachment__is_iter:
                return self
            return True
        if (
            (self._Attachment__total or 0) > 0
            and (self._Attachment__current + 1) < (self._Attachment__total or 0)
            and (self._Attachment__total or 0) > len(self._Attachment__results)
            and _recursive is False
        ):
            if self._Attachment__limit:
                if self._Attachment__current + 1 < self._Attachment__limit:
                    await self.query()
                    return await self.next(_recursive=True)
            else:
                await self.query()
                return await self.next(_recursive=True)

        if self._Attachment__is_iter:
            self._Attachment__is_iter = False
            raise StopAsyncIteration()
        return False

    async def as_temp_file(self, chunk_size: int = 512) -> SpooledTemporaryFile:  # type: ignore[override]
        """
        Return the attachment as a TempFile (async streaming).
        """
        assert self._current(), "Cannot read nothing, iterate the attachment"
        tf = SpooledTemporaryFile(max_size=1024 * 1024, mode="w+b")

        resp = await self._client.attachment_api.get_file(self.sys_id, stream=True)
        try:
            async for chunk in resp.aiter_bytes(chunk_size):
                tf.write(chunk)
        finally:
            await resp.aclose()
        tf.seek(0)
        return tf

    async def write_to(self, path, chunk_size: int = 512) -> Path:  # type: ignore[override]
        """
        Write the attachment to the given path (async streaming).
        """
        assert self._current(), "Cannot read nothing, iterate the attachment"
        p = Path(path)
        # if we specify a dir, auto set the filename
        if p.is_dir():
            p = p / self.file_name

        resp = await self._client.attachment_api.get_file(self.sys_id, stream=True)
        try:
            with open(p, "wb") as f:
                async for chunk in resp.aiter_bytes(chunk_size):
                    f.write(chunk)
        finally:
            await resp.aclose()
        return p

    async def read(self) -> bytes:  # type: ignore[override]
        """
        Read the entire attachment into memory.
        """
        assert self._current(), "Cannot read nothing, iterate the attachment"
        resp = await self._client.attachment_api.get_file(self.sys_id, stream=False)
        try:
            # Ensure content is loaded; for AsyncClient this is safe
            data = await resp.aread()
        finally:
            await resp.aclose()
        return data

    async def readlines(self, encoding: str = "UTF-8", delimiter: str = "\n") -> List[str]:  # type: ignore[override]
        """
        Read the attachment as text, splitting by delimiter.
        """
        data = await self.read()
        return data.decode(encoding).split(delimiter)

    async def query(self):
        """
        Query the attachment list (async).
        """
        response = await self._client.attachment_api.list(self)
        try:
            result = response.json()["result"]
            # append results and update counters
            self._Attachment__results = self._Attachment__results + result
            self._Attachment__page = self._Attachment__page + 1
            self._Attachment__total = int(response.headers.get("X-Total-Count", "0"))
        except Exception as e:
            if "Transaction cancelled: maximum execution time exceeded" in response.text:
                raise RequestException("Maximum execution time exceeded. Lower batch size.")
            else:
                traceback.print_exc()
                self._log.debug(response.text)
                raise e

    async def get(self, sys_id: str) -> bool:  # type: ignore[override]
        """
        Get a single attachment by sys_id (async).
        """
        try:
            response = await self._client.attachment_api.get(sys_id)
        except NotFoundException:
            return False
        self._Attachment__results = [self._transform_result(response.json()["result"])]
        if len(self._Attachment__results) > 0:
            self._Attachment__current = 0
            self._Attachment__total = len(self._Attachment__results)
            return True
        return False

    async def delete(self):
        """
        Delete current attachment (async).
        """
        response = await self._client.attachment_api.delete(self.sys_id)
        code = response.status_code
        if code != 204:
            raise RequestException(response.text)

    async def add_attachment( # type: ignore[override]
        self,
        table_sys_id,
        file_name,
        file,
        content_type: Optional[str] = None,
        encryption_context: Optional[str] = None,
    ) -> str:
        """
        Upload an attachment to this table (async). Returns Location header.
        """
        r = await self._client.attachment_api.upload_file(file_name, self._table, table_sys_id, file, content_type, encryption_context)
        return r.headers["Location"]
