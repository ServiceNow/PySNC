import traceback
import logging
from tempfile import SpooledTemporaryFile
from .query import *
from .exceptions import *


class Attachment(object):
    MAX_MEM_SIZE = 0xFFFF

    #TODO refactor this to use a .get method
    def __init__(self, client, table, sys_id=None):
        self.__is_iter = False
        self._client = client
        self._log = logging.getLogger(__name__)
        self._table = table
        self._sys_id = sys_id
        self.__results = []
        self.__current = -1
        self.__page = -1
        self.__total = None
        self.__limit = None
        self.__encoded_query = None
        self.__query = Query(table)
        # we need to default the table
        self.add_query('table_name', table)
        if sys_id != None:
            self.add_query('table_sys_id', sys_id)

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
        if self.__current is -1:
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
        if l > 0 and self.__current+1 < l:
            self.__current = self.__current + 1
            if self.__is_iter:
                return self
            return True
        if self.__total > 0 and \
                        (self.__current+1) < self.__total and \
                        self.__total > len(self.__results) and \
                        _recursive is False:
            if self.__limit:
                if self.__current+1 < self.__limit:
                    self.query()
                    return self.next(_recursive=True)
            else:
                self.query()
                return self.next(_recursive=True)
        if self.__is_iter:
            self.__is_iter = False
            raise StopIteration()
        return False

    def getAsFile(self, chunk_size=512):
        """
        Return the attachment as a TempFile

        :param chunk_size:
        :return: SpooledTemporaryFile
        """
        tf = SpooledTemporaryFile(max_size=1024*1024, mode='w+b')
        r = self._client.attachment._get_file(self.sys_id)
        for chunk in r.iter_content(chunk_size=chunk_size):
            tf.write(chunk)
        tf.seek(0)
        return tf

    def query(self):
        """
        Query the table

        :return: void
        :raise:
            :AuthenticationException: If we do not have rights
            :RequestException: If the transaction is canceled due to execution time
        """
        response = self._client.attachment._list(self)
        code = response.status_code
        if code == 200:
            try:
                self.__results = self.__results + response.json()['result']
                self.__page = self.__page + 1
                self.__total = int(response.headers['X-Total-Count'])
            except Exception as e:
                if 'Transaction cancelled: maximum execution time exceeded' in response.text:
                    raise RequestException('Maximum execution time exceeded. Lower batch size (< %s).' % self.__batch_size)
                else:
                    traceback.print_exc()
                    self._log.debug(response.text)
                    raise e

        elif code == 401:
            raise AuthenticationException(response.json()['error'])

    def delete(self):
        response = self._client.attachment._delete(self.sys_id)
        code = response.status_code
        if code != 204:
            raise RequestException(response.text)

    def add_query(self, name, value, second_value=None):
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

    def add_attachment(self, file_name, file, content_type=None, encryption_context=None):
        if self._sys_id is None:
            raise UploadException('We can only attach to a specific record')
        self._client.attachment._upload_file(file_name, self._table, self._sys_id, file, content_type, encryption_context)

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

