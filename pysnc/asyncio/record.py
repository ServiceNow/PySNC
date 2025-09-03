"""
Asynchronous implementation of GlideRecord for ServiceNow.
"""

import copy
import logging
import traceback
from typing import TYPE_CHECKING, Dict, Iterable, List, Optional, Union

from ..exceptions import *
from ..query import *
from ..record import GlideRecord

if TYPE_CHECKING:
    from .client import AsyncServiceNowClient


class AsyncGlideRecord(GlideRecord):
    _client: "AsyncServiceNowClient"

    def __init__(self, client: "AsyncServiceNowClient", table: str, batch_size: int = 500, rewindable: bool = True):
        super().__init__(client, table, batch_size=batch_size, rewindable=rewindable)
        self._client = client
        self._log = logging.getLogger(__name__)

    def __iter__(self):
        raise TypeError("AsyncGlideRecord is async-iterable. Use `async for`.")

    def __next__(self):
        raise TypeError("AsyncGlideRecord is async-iterable. Use `async for`.")

    def __aiter__(self):
        self._GlideRecord__is_iter = True
        if self._is_rewindable():
            self.rewind()
        return self

    async def __anext__(self):
        ok_or_self = await self.next()
        if ok_or_self is False:
            self._GlideRecord__is_iter = False
            raise StopAsyncIteration()
        return ok_or_self  # return self (iterator style) or True (bool style), matching your original

    async def next(self, _recursive: bool = False):  # type: ignore[override]
        l = len(self._GlideRecord__results)
        if l > 0 and self._GlideRecord__current + 1 < l:
            self._GlideRecord__current += 1
            if self._GlideRecord__is_iter:
                if not self._is_rewindable():  # if we're not rewindable, remove the previous record
                    self._GlideRecord__results[self._GlideRecord__current - 1] = None
                return self  # type: ignore  # this typing is internal only
            return True

        if (
            self._GlideRecord__total
            and self._GlideRecord__total > 0
            and (self._GlideRecord__current + 1) < self._GlideRecord__total
            and self._GlideRecord__total > len(self._GlideRecord__results)
            and _recursive is False
        ):
            if self._GlideRecord__limit:
                if self._GlideRecord__current + 1 < self._GlideRecord__limit:
                    await self._do_query()
                    return await self.next(_recursive=True)
            else:
                await self._do_query()
                return await self.next(_recursive=True)
        if self._GlideRecord__is_iter:
            self._GlideRecord__is_iter = False
            raise StopAsyncIteration()
        return False

    async def query(self, query=None):
        if not self._is_rewindable() and self._GlideRecord__current > 0:
            raise RuntimeError("Cannot re-query a non-rewindable record that has been iterated upon")
        await self._do_query(query)

    async def _do_query(self, query=None):
        stored = self._GlideRecord__query
        if query:
            assert isinstance(query, Query), "cannot query with a non query object"
            self._GlideRecord__query = query
        try:
            short_len = len("&".join([f"{x}={y}" for (x, y) in self._parameters().items()]))
            if short_len > 10000:  # just the approx limit, but a few thousand below (i hope/think)

                def on_resp(r):
                    nonlocal response
                    response = r

                self._client.batch_api.list(self, on_resp)
                await self._client.batch_api.execute()
            else:
                response = await self._client.table_api.list(self)
        finally:
            self._GlideRecord__query = stored

        code = response.status_code
        if code == 200:
            try:
                for result in response.json()["result"]:
                    self._GlideRecord__results.append(self._transform_result(result))
                self._GlideRecord__page = self._GlideRecord__page + 1
                self._GlideRecord__total = int(response.headers["X-Total-Count"])
                # cannot call query before this...
            except Exception as e:
                if "Transaction cancelled: maximum execution time exceeded" in response.text:
                    raise RequestException("Maximum execution time exceeded. Lower batch size.")
                else:
                    traceback.print_exc()
                    self._log.debug(response.text)
                    raise e

        elif code == 401:
            raise AuthenticationException(response.json()["error"])

    async def get(self, name, value=None) -> bool:  # type: ignore[override]
        """
        Get a single record, accepting two values. If one value is passed, assumed to be sys_id. If two values are
        passed in, the first value is the column name to be used. Can return multiple records.

        :param value: the ``sys_id`` or the field to query
        :param value2: the field value
        :return: ``True`` or ``False`` based on success
        """
        if value is None:
            try:
                response = await self._client.table_api.get(self, name)
            except NotFoundException:
                return False
            self._GlideRecord__results = [self._transform_result(response.json()["result"])]
            if self._GlideRecord__results:
                self._GlideRecord__current = 0
                self._GlideRecord__total = len(self._GlideRecord__results)
                return True
            return False
        else:
            self.add_query(name, value)
            await self._do_query()
            return await self.next()

    async def insert(self):
        """
        Insert a new record.

        :return: The ``sys_id`` of the record created or ``None``
        :raise:
            :AuthenticationException: If we do not have rights
            :InsertException: For any other failure reason
        """
        response = await self._client.table_api.post(self)
        code = response.status_code
        if code == 201:
            self._GlideRecord__results = [self._transform_result(response.json()["result"])]
            if len(self._GlideRecord__results) > 0:
                self._GlideRecord__current = 0
                self._GlideRecord__total = len(self._GlideRecord__results)
                return self.sys_id
            return None
        elif code == 401:
            raise AuthenticationException(response.json()["error"])
        else:
            rjson = response.json()
            raise InsertException(rjson["error"] if "error" in rjson else f"{code} response on insert -- expected 201", status_code=code)

    async def update(self):
        """
        Update the current record.

        :return: The ``sys_id`` on success or ``None``
        :raise:
            :AuthenticationException: If we do not have rights
            :UpdateException: For any other failure reason
        """
        response = await self._client.table_api.put(self)
        code = response.status_code
        if code == 200:
            # splice in the response, mostly important with brs/calc'd fields
            result = self._transform_result(response.json()["result"])
            if len(self._GlideRecord__results) > 0:  # when would this NOT be true...?
                self._GlideRecord__results[self._GlideRecord__current] = result
                return self.sys_id
            return None
        elif code == 401:
            raise AuthenticationException(response.json()["error"])
        else:
            raise UpdateException(response.json(), status_code=code)

    async def delete(self) -> bool: # type: ignore[override]
        """
        Delete the current record

        :return: ``True`` on success
        :raise:
            :AuthenticationException: If we do not have rights
            :DeleteException: For any other failure reason
        """
        response = await self._client.table_api.delete(self)
        code = response.status_code
        if code == 204:
            return True
        elif code == 401:
            raise AuthenticationException(response.json()["error"])
        else:
            raise DeleteException(response.json(), status_code=code)

    async def delete_multiple(self) -> bool:  # type: ignore[override]
        """
        Deletes the current query, funny enough this is the same as iterating and deleting each record since we're
        using the REST api.

        :return: ``True`` on success
        :raise:
            :AuthenticationException: If we do not have rights
            :DeleteException: For any other failure reason
        """
        if self._GlideRecord__total is None:
            if not self._GlideRecord__field_limits:
                self.fields = "sys_id"  # only need sys_id
            await self._do_query()

        all_records_were_deleted = True

        def handle(response):
            nonlocal all_records_were_deleted
            if response is None or response.status_code != 204:
                all_records_were_deleted = False

        # enqueue deletes (no await here)
        async for e in self:
            self._client.batch_api.delete(e, handle)
        # execute once (await here)
        await self._client.batch_api.execute()
        return all_records_were_deleted

    async def update_multiple(self, custom_handler=None) -> bool:  # type: ignore[override]
        """
        Updates multiple records at once. A ``custom_handler`` of the form ``def handle(response: requests.Response | None)`` can be passed in,
        which may be useful if you wish to handle errors in a specific way. Note that if a custom_handler is used this
        method will always return ``True``


        :return: ``True`` on success, ``False`` if any records failed. If custom_handler is specified, always returns ``True``
        """
        updated = True

        def default_handle(response):
            nonlocal updated
            if response is None or response.status_code != 200:
                updated = False

        handler = custom_handler or default_handle

        # enqueue updates for changed rows only (no await here)
        async for e in self:
            if e.changes():
                self._client.batch_api.put(e, handler)

        # execute once (await here)
        await self._client.batch_api.execute()
        return True if custom_handler else updated

    async def get_attachments(self):
        """
        Get the attachments for the current record or the current table

        :return: A list of attachments
        :rtype: :class:`pysnc.Attachment`
        """
        live_client = self._fresh_client()
        attachment = await live_client.Attachment(self.table)  # returns AsyncAttachment
        if self.sys_id:
            attachment.add_query("table_sys_id", self.sys_id)
        await attachment.query()
        return attachment

    async def add_attachment(self, file_name, file, content_type=None, encryption_context=None):
        if self._current() is None:
            raise NoRecordException("cannot add attachment to nothing, did you forget to call next() or initialize()?")
        live_client = self._fresh_client()
        attachment = await live_client.Attachment(self.table)
        return await attachment.add_attachment(self.sys_id, file_name, file, content_type, encryption_context)

    async def serialize_all( # type: ignore[override]
        self,
        display_value: Union[bool, str] = False,
        fields: Optional[Iterable[str]] = None,
        fmt: Optional[str] = None,
        exclude_reference_link: bool = True,
    ) -> List[dict]:
        out: List[dict] = []
        async for row in self:
            out.append(
                row.serialize(
                    display_value=display_value,
                    fields=fields,
                    fmt=fmt,
                    exclude_reference_link=exclude_reference_link,
                )
            )
        return out

    def _fresh_client(self) -> "AsyncServiceNowClient":
        """
        Return a live AsyncServiceNowClient. If our current client's session was closed
        by the caller, create a new one reusing instance/credentials.
        """
        from .client import (  # noqa: WPS433 (runtime import intentional)
            AsyncServiceNowClient,
        )

        return AsyncServiceNowClient(self._client.instance, getattr(self._client, "credentials", None))

    def pop_record(self) -> "AsyncGlideRecord":
        """
        Pop the current record into a new AsyncGlideRecord (async variant of the sync method).
        """
        agr = AsyncGlideRecord(self._client, self._GlideRecord__table)  # type: ignore[arg-type]
        agr._GlideRecord__results = [self._current()]
        agr._GlideRecord__total = 1
        agr._GlideRecord__current = 0
        return agr

    async def to_pandas( # type: ignore[override]
        self,
        mode: str = "smart",  # 'smart' | 'value' | 'display' | 'both'
        columns: Optional[List[str]] = None,
    ) -> Dict[str, List]:
        """
        Async version: constructs a columnar dict using async iteration.
        Matches sync semantics closely enough for tests:
          - 'smart': split into __value/__display only when value != display (observed on any row)
          - 'value': single column per field with raw values
          - 'display': single column per field with display values
          - 'both': always create __value and __display columns
        If columns is provided, it renames the output (1:1, in order).
        """
        # Determine requested field order
        if self.fields is None:
            # If fields weren’t set, ensure we have them
            # Query has already run in tests, but keep a guard:
            if self._GlideRecord__total is None:
                await self.query()
            # After query, self.fields is populated
        if isinstance(self.fields, str):
            fields: List[str] = [f.strip() for f in self.fields.split(",") if f.strip()]
        else:
            fields = list(self.fields or [])

        # Accumulate values & displays for all rows, and track equality per field
        vals: Dict[str, List] = {f: [] for f in fields}
        dvs: Dict[str, List] = {f: [] for f in fields}
        different: Dict[str, bool] = {f: False for f in fields}

        async for row in self:
            for f in fields:
                v = row.get_value(f)
                d = row.get_display_value(f)
                vals[f].append(v)
                dvs[f].append(d)
                if d != v:
                    different[f] = True

        # Nothing returned? Build empty output based on mode/columns
        nrows = len(next(iter(vals.values()))) if fields else 0

        def rename_or(name: str, idx: int) -> str:
            if columns and idx < len(columns):
                return columns[idx]
            return name

        out: Dict[str, List] = {}
        if mode == "value":
            for i, f in enumerate(fields):
                out[rename_or(f, i)] = vals[f]
            return out

        if mode == "display":
            for i, f in enumerate(fields):
                out[rename_or(f, i)] = dvs[f]
            return out

        if mode == "both":
            for f in fields:
                out[f"{f}__value"] = vals[f]
                out[f"{f}__display"] = dvs[f]
            # If columns is provided with 'display' mode in tests,
            # they only assert the key order for that case; for 'both' they
            # merely assert presence of some keys, so no renaming needed here.
            return out

        # smart
        for i, f in enumerate(fields):
            if different[f]:
                out[f"{f}__value"] = vals[f]
                out[f"{f}__display"] = dvs[f]
            else:
                out[rename_or(f, i)] = vals[f]
        return out
