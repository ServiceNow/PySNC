"""
Asynchronous implementation of GlideRecord for ServiceNow.
"""

from typing import TYPE_CHECKING

from ..query import *
from ..exceptions import *
from ..record import GlideRecord

if TYPE_CHECKING:
    from .client import AsyncServiceNowClient
    from .attachment import AsyncAttachment


class AsyncGlideRecord(GlideRecord):

    def __iter__(self):
        raise TypeError("AsyncGlideRecord is async-iterable. Use `async for`.")

    def __next__(self):
        raise TypeError("AsyncGlideRecord is async-iterable. Use `async for`.")

    def __aiter__(self):
        self.__is_iter = True
        if self._is_rewindable():
            self.rewind()
        return self

    async def __anext__(self):
        ok_or_self = await self.next()
        if ok_or_self is False:
            self.__is_iter = False
            raise StopAsyncIteration()
        return ok_or_self  # return self (iterator style) or True (bool style), matching your original

    async def next(self, _recursive: bool = False):
        l = len(self.__results)
        if l > 0 and self.__current+1 < l:
            self.__current = self.__current + 1
            if self.__is_iter:
                if not self._is_rewindable(): # if we're not rewindable, remove the previous record
                    self.__results[self.__current - 1] = None
                return self  # type: ignore  # this typing is internal only
            return True

        if self.__total and self.__total > 0 and \
                (self.__current+1) < self.__total and \
                self.__total > len(self.__results) and \
                _recursive is False:
            if self.__limit:
                if self.__current+1 < self.__limit:
                    self._do_query()
                    return self.next(_recursive=True)
            else:
                self._do_query()
                return self.next(_recursive=True)
        if self.__is_iter:
            self.__is_iter = False
            raise StopIteration()
        return False

    async def query(self, query=None):
        if not self._is_rewindable() and self.__current > 0:
            raise RuntimeError('Cannot re-query a non-rewindable record that has been iterated upon')
        await self._do_query(query)


    async def _do_query(self, query=None):
        stored = self.__query
        if query:
            assert isinstance(query, Query), 'cannot query with a non query object'
            self.__query = query
        try:
            short_len = len('&'.join([ f"{x}={y}" for (x,y) in self._parameters().items() ]))
            if short_len > 10000:  # just the approx limit, but a few thousand below (i hope/think)

                def on_resp(r):
                    nonlocal response
                    response = r
                self._client.batch_api.list(self, on_resp)
                await self._client.batch_api.execute()
            else:
                response = await self._client.table_api.list(self)
        finally:
            self.__query = stored

        code = response.status_code
        if code == 200:
            try:
                for result in response.json()['result']:
                    self.__results.append(self._transform_result(result))
                self.__page = self.__page + 1
                self.__total = int(response.headers['X-Total-Count'])
                # cannot call query before this...
            except Exception as e:
                if 'Transaction cancelled: maximum execution time exceeded' in response.text:
                    raise RequestException('Maximum execution time exceeded. Lower batch size (< %s).' % self.__batch_size)
                else:
                    traceback.print_exc()
                    self._log.debug(response.text)
                    raise e

        elif code == 401:
            raise AuthenticationException(response.json()['error'])

    async def get(self, name, value=None) -> bool:
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
            self.__results = [self._transform_result(response.json()['result'])]
            if self.__results:
                self.__current = 0
                self.__total = len(self.__results)
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
            self.__results = [self._transform_result(response.json()['result'])]
            if len(self.__results) > 0:
                self.__current = 0
                self.__total = len(self.__results)
                return self.sys_id
            return None
        elif code == 401:
            raise AuthenticationException(response.json()['error'])
        else:
            rjson = response.json()
            raise InsertException(rjson['error'] if 'error' in rjson else f"{code} response on insert -- expected 201", status_code=code)

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
            result = self._transform_result(response.json()['result'])
            if len(self.__results) > 0: # when would this NOT be true...?
                self.__results[self.__current] = result
                return self.sys_id
            return None
        elif code == 401:
            raise AuthenticationException(response.json()['error'])
        else:
            raise UpdateException(response.json(), status_code=code)

    async def delete(self) -> bool:
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
            raise AuthenticationException(response.json()['error'])
        else:
            raise DeleteException(response.json(), status_code=code)


    async def delete_multiple(self) -> bool:
        """
        Deletes the current query, funny enough this is the same as iterating and deleting each record since we're
        using the REST api.

        :return: ``True`` on success
        :raise:
            :AuthenticationException: If we do not have rights
            :DeleteException: For any other failure reason
        """
        if self.__total is None:
            if not self.__field_limits:
                self.fields = 'sys_id'  # type: ignore  ## all we need...
            await self._do_query()

        allRecordsWereDeleted = True
        def handle(response):
            nonlocal  allRecordsWereDeleted
            if response is None or response.status_code != 204:
                allRecordsWereDeleted = False

        for e in self:
            self._client.batch_api.delete(e, handle)
        await self._client.batch_api.execute()
        return allRecordsWereDeleted

    async def update_multiple(self, custom_handler=None) -> bool:
        """
        Updates multiple records at once. A ``custom_handler`` of the form ``def handle(response: requests.Response | None)`` can be passed in,
        which may be useful if you wish to handle errors in a specific way. Note that if a custom_handler is used this
        method will always return ``True``


        :return: ``True`` on success, ``False`` if any records failed. If custom_handler is specified, always returns ``True``
        """
        updated = True
        def handle(response):
            nonlocal updated
            if response is None or response.status_code != 200:
                updated = False

        for e in self:
            if e.changes():
                self._client.batch_api.put(e, custom_handler if custom_handler else handle)

        await self._client.batch_api.execute()
        return updated

    async def get_attachments(self):
        """
        Get the attachments for the current record or the current table

        :return: A list of attachments
        :rtype: :class:`pysnc.Attachment`
        """
        attachment = await self._client.Attachment(self.__table)  # returns AsyncAttachment
        if self.sys_id:
            attachment.add_query('table_sys_id', self.sys_id)
        await attachment.query()
        return attachment

    # Async helpers for callers that used to rely on sync iteration:
    async def serialize_all_async(self, **kw):
        return [rec.serialize(**kw) async for rec in self]