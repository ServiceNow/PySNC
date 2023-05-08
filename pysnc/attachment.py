import traceback
import logging
from tempfile import SpooledTemporaryFile
from pathlib import Path
from typing import List, Optional

from .record import GlideElement
from .query import *
from .exceptions import *


class Attachment:
    MAX_MEM_SIZE = 0xFFFF

    # TODO refactor this to use a .get method
    def __init__(self, client, table):
        """
        :param str table: the table we are associated with
        """
        self.__is_iter = False
        self._client = client
        self._log = logging.getLogger(__name__)
        self._table = table
        self.__results = []
        self.__current = -1
        self.__page = -1
        self.__total = None
        self.__limit = None
        self.__encoded_query = None
        self.__query = Query(table)
        # we need to default the table
        self.add_query('table_name', table)

    def _clear_query(self):
        self.__query = Query(self.__table)

    def _parameters(self):
        ret = dict(
            sysparm_query=self.__query.generate_query(encoded_query=self.__encoded_query)
        )
        # Batch size matters! Transaction limits will exceed.
        # This also means we have to be pretty specific with limits
        limit = None
        if self.__limit:
            if self.__limit >= self.batch_size:
                # need to re-calc as our actual queried count will end up greater than our limit
                # this keeps us at our actual limit even when between batch size boundaries
                limit = self.__limit - self.__current - 1
            elif self.__limit <= self.batch_size or self.__limit > 0:
                limit = self.__limit
        if limit:
            ret['sysparm_limit'] = limit
        if self.__current == -1:
            ret['sysparm_offset'] = 0
        else:
            ret['sysparm_offset'] = self.__current + 1
        return ret

    def _current(self):
        if self.__current > -1 and self.__current < len(self.__results):
            return self.__results[self.__current]
        return None

    def __iter__(self):
        self.__is_iter = True
        self.__current = -1
        return self

    def __next__(self):
        return self.next()

    def next(self, _recursive=False):
        """
        Returns the next record in the record set

        :return: ``True`` or ``False`` based on success
        """
        l = len(self.__results)
        if l > 0 and self.__current + 1 < l:
            self.__current = self.__current + 1
            if self.__is_iter:
                return self
            return True
        if self.__total > 0 and \
                (self.__current + 1) < self.__total and \
                self.__total > len(self.__results) and \
                _recursive is False:
            if self.__limit:
                if self.__current + 1 < self.__limit:
                    self.query()
                    return self.next(_recursive=True)
            else:
                self.query()
                return self.next(_recursive=True)
        if self.__is_iter:
            self.__is_iter = False
            raise StopIteration()
        return False

    def as_temp_file(self, chunk_size: int = 512) -> SpooledTemporaryFile:
        """
        Return the attachment as a TempFile

        :param chunk_size: bytes to read in at a time from the HTTP stream
        :return: SpooledTemporaryFile
        """
        assert self._current(), "Cannot read nothing, iterate the attachment"
        tf = SpooledTemporaryFile(max_size=1024 * 1024, mode='w+b')

        with self._client.attachment_api.get_file(self.sys_id) as r:
            for chunk in r.iter_content(chunk_size):
                tf.write(chunk)
        tf.seek(0)
        return tf

    def write_to(self, path, chunk_size=512) -> Path:
        """
        Write the attachment to the given path - if the path is a directory the file_name will be used
        """
        assert self._current(), "Cannot read nothing, iterate the attachment"
        p = Path(path)
        # if we specify a dir, auto set the filename
        if p.is_dir():
            p = p / self.file_name
        with open(p, 'wb') as f:
            with self._client.attachment_api.get_file(self.sys_id) as r:
                for chunk in r.iter_content(chunk_size):
                    f.write(chunk)
        return p

    def read(self) -> bytes:
        """
        Read the entire attachment
        :return: b''
        """
        assert self._current(), "Cannot read nothing, iterate the attachment"
        return self._client.attachment_api.get_file(self.sys_id, stream=False).content

    def readlines(self, encoding='UTF-8', delimiter='\n') -> List[str]:
        """
        Read the attachment, as text, decoding by default as UTF-8, splitting by the delimiter.
        :param encoding: encoding to use, defaults to UTF-8
        :param delimiter: what to split by, defualt \n
        :return: list
        """
        return self.read().decode(encoding).split(delimiter)

    def query(self):
        """
        Query the table

        :return: void
        :raise:
            :AuthenticationException: If we do not have rights
            :RequestException: If the transaction is canceled due to execution time
        """
        response = self._client.attachment_api.list(self)
        try:
            self.__results = self.__results + response.json()['result']
            self.__page = self.__page + 1
            self.__total = int(response.headers['X-Total-Count'])
        except Exception as e:
            if 'Transaction cancelled: maximum execution time exceeded' in response.text:
                raise RequestException(
                    'Maximum execution time exceeded. Lower batch size (< %s).' % self.__batch_size)
            else:
                traceback.print_exc()
                self._log.debug(response.text)
                raise e

    def _transform_result(self, result):
        for key, value in result.items():
            result[key] = GlideElement(key, value, parent_record=self)
        return result

    def get(self, sys_id: str) -> bool:
        """
        Get a single record, accepting two values. If one value is passed, assumed to be sys_id. If two values are
        passed in, the first value is the column name to be used. Can return multiple records.

        :param sys_id: the id of the attachment
        :return: ``True`` or ``False`` based on success
        """
        try:
            response = self._client.attachment_api.get(sys_id)
        except NotFoundException:
            return False
        self.__results = [self._transform_result(response.json()['result'])]
        if len(self.__results) > 0:
            self.__current = 0
            self.__total = len(self.__results)
            return True
        return False

    def delete(self):
        response = self._client.attachment_api.delete(self.sys_id)
        code = response.status_code
        if code != 204:
            raise RequestException(response.text)

    def add_query(self, name, value, second_value=None) -> QueryCondition:
        """
        Add a query to a record. For example::

            add_query('active', 'true')

        Which will create the query ``active=true``. If we specify the second_value::

            add_query('name', 'LIKE', 'test')

        Which will create the query ``nameLIKEtest``


        :param str name: Table field name
        :param str value: Either the value in which ``name`` must be `=` to else an operator if ``second_value`` is specified

            Numbers::

            * =
            * !=
            * >
            * >=
            * <
            * <=

            Strings::

            * =
            * !=
            * IN
            * NOT IN
            * STARTSWITH
            * ENDSWITH
            * CONTAINS
            * DOES NOT CONTAIN
            * INSTANCEOF

        :param str second_value: optional, if specified then ``value`` is expected to be an operator
        """
        return self.__query.add_query(name, value, second_value)

    def add_attachment(self, table_sys_id, file_name, file, content_type=None, encryption_context=None) -> str:
        r = self._client.attachment_api.upload_file(file_name, self._table, table_sys_id, file, content_type,
                                             encryption_context)
        # Location header contains the attachment URL
        return r.headers['Location']

    def get_link(self) -> Optional[str]:
        if self._current():
            return f"{self._client.instance}/api/now/v1/attachment/{self.sys_id}/file"
        return None

    def _get_value(self, item, key='value'):
        obj = self._current()
        if item in obj:
            o = obj[item]
            if isinstance(o, dict):
                return o[key]
            else:
                return o
        return None

    def __getattr__(self, item):
        # TODO: allow override for record fields which may overload our local properties by prepending _
        obj = self._current()
        if obj:
            return self._get_value(item)
        return self.__getattribute__(item)

    def __contains__(self, item):
        obj = self._current()
        if obj:
            return item in obj
        return False

    def __len__(self):
        return self.__total if self.__total else 0
