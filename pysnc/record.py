import logging
import copy
import traceback
from requests import Request
from collections import OrderedDict
from datetime import datetime, timezone
from typing import Any, Union, List, Optional, TYPE_CHECKING

from .query import *
from .exceptions import *

TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S%z"

if TYPE_CHECKING:  # for mypy
    from .client import ServiceNowClient
    from .attachment import Attachment


class GlideElement(str):
    """
    Object backing the value/display values of a given record entry.
    """

    def __new__(cls, name, value, *args, **kwargs):
        return super(GlideElement, cls).__new__(cls, value)

    def __init__(self, name: str, value=None, display_value=None, parent_record=None, link=None):
        self._name = name
        self._value = None
        self._display_value = None
        self._changed = False
        self._link = None
        if isinstance(value, dict):
            self._value = value['value']
            # only bother to set display value if it's different
            if self._value != value['display_value']:
                self._display_value = value['display_value']
            if 'link' in value:
                self._link = value['link']
        else:
            self._value = value
        if display_value:
            self._display_value = display_value

        self._parent_record = parent_record

    def get_name(self) -> str:
        """
        get the name of the field
        """
        return self._name

    def get_value(self) -> Any:
        """
        get the value of the field
        """
        if self._value is not None:
            return self._value
        return self._display_value  # if we are display only

    def get_display_value(self) -> Any:
        """
        get the display value of the field, if it has one, else just the value
        """
        if self._display_value:
            return self._display_value
        return self._value

    def get_link(self) -> Any:
        """
        get the link of a field, if it has one, else None
        """
        return self._link

    def set_value(self, value):
        """
        set the value for the field. Will also set the display_value to `None`
        """
        if isinstance(value, GlideElement):
            value = value.get_value()

        if self._value != value:
            self._changed = True
            self._value = value
            self._display_value = None

    def set_display_value(self, value: Any):
        """
        set the display value for the field -- generally speaking does not have any affect upstream (to the server)
        """
        if isinstance(value, GlideElement):
            value = value.get_display_value()
        if self._display_value != value:
            self._changed = True
            self._display_value = value

    def set_link(self, link: Any):
        """
        set the reference link for the field -- generally speaking does not have any affect upstream (to the server)
        """
        if isinstance(link, GlideElement):
            link = link.get_link()
        if self._link != link:
            self._changed = True
            self._link = link

    def changes(self) -> bool:
        """
        :return: if we have changed this value
        :rtype: bool
        """
        return self._changed

    def nil(self) -> bool:
        """
        returns True if the value is None or zero length

        :return: if this value is anything
        :rtype: bool
        """
        return not self._value or len(self._value) == 0

    def serialize(self) -> dict:
        """
        Returns a dict with the `value`,`display_value`, `link` keys
        """
        return (
            {
                'value': self.get_value(),
                'display_value': self.get_display_value()
            }
            if self.get_link() is None
            else {
                'value': self.get_value(),
                'display_value': self.get_display_value(),
                'link': self.get_link()
            }
        )

    def date_numeric_value(self) -> int:
        """
        Returns the number of milliseconds since January 1, 1970, 00:00:00 GMT for a duration field
        """
        return int(self.date_value().timestamp() * 1000)

    def date_value(self) -> datetime:
        """
        Returns the current as a UTC datetime or throws if it cannot
        """
        # see also https://stackoverflow.com/a/53291299
        # note: all values are UTC, display values are by user TZ
        value_with_tz = f"{self.get_value()}+0000"
        return datetime.strptime(value_with_tz, TIMESTAMP_FORMAT)

    def set_date_numeric_value(self, ms: int) -> None:
        """
        Sets the value of a date/time element to the specified number of milliseconds since January 1, 1970 00:00:00 GMT.

        When called, setDateNumericValue() automatically creates the necessary GlideDateTime/GlideDate/GlideDuration object, and then sets the element to the specified value.
        """
        dt = datetime.fromtimestamp(ms/1000.0, tz=timezone.utc)
        self.set_value(dt.strftime(TIMESTAMP_FORMAT)[:-5])  # note: strips UTC from the end

    def __str__(self):
        #if self._display_value and self._value != self._display_value:
        #    return dict(value=self._value, display_value=self._display_value)
        return str(self.get_value())

    def __repr__(self):
        return f"GlideElement({self._value!r})"

    def __bool__(self):
        # help with the truthiness of true/false fields
        # theoretically could have a false case if we're a string with the value false since we dont know our types
        if self.get_value() == 'false':
            return False
        return bool(self.get_value())

    def __magic(self, attr, arg=None):
        #print(f"__magic(self, {attr}, {arg}")
        val = arg.get_value() if isinstance(arg, GlideElement) else arg
        f = getattr(self.get_value(), attr)
        return f(val) if val is not None else f()

    def __eq__(self, other):
        return self.__magic('__eq__', other)

    def __ne__(self, other):
        return self.__magic('__ne__', other)

    def __len__(self):
        return self.__magic('__len__')

    def __length_hint__(self):
        return self.__magic('__length_hint__')

    def __iter__(self):
        # unfortunately i don't think we'll ever be smart enough to auto-support List columns
        return self.__magic('__iter__')

    def __next__(self):
        return self.__magic('__next__')


    ## Note: more complicated type operations than this should probably just be done with the get_value() directly
    def __add__(self, other):
        return self.__magic('__add__', other)

    def __sub__(self, other):
        return self.__magic('__sub__', other)

    def __gt__(self, other):
        return self.__magic('__gt__', other)

    def __lt__(self, other):
        return self.__magic('__lt__', other)

    def __le__(self, other):
        return self.__magic('__le__', other)

    def __ge__(self, other):
        return self.__magic('__ge__', other)

    def __contains__(self, other):
        return self.__magic('__contains__', other)

    def __getitem__(self, index):
        return self.__magic('__getitem__', index)

    def __hash__(self):
        return self.__magic('__hash__')

    def __int__(self):
        return int(self.get_value())

    def __float__(self):
        return float(self.get_value())

    def __complex__(self):
        return complex(self.get_value())

    def __getattr__(self, item):
        if item in GlideElement.__class__.__dict__:
            return self.__getattribute__(item)

        if self._parent_record:
            if tv := self._parent_record.get_element(f"{self._name}.{item}"):
                return tv

        if hasattr(self.get_value(), item):
            return getattr(self.get_value(), item)

        raise AttributeError(f"{type(self.get_value())} has no attribute '{item}' nor GlideElement '{self._name}.{item}' -- did you mean to add this to the GlideRecord fields?")

    def __deepcopy__(self, memo):
        """
        ultimately for copy.deepcopy and the use of .pop_record(), avoids recusion doing it this way
        """
        ne = GlideElement(self.get_name(), self.get_value())
        if self._display_value:
            ne.set_display_value(self._display_value)
        return ne


class GlideRecord(object):
    """
    The GlideRecord object. Normally instantiated via convenience method :func:`pysnc.ServiceNowClient.GlideRecord`.
    This object allows us to interact with a specific table via the table rest api.

    :param ServiceNowClient client: We need to know which instance we're connecting to
    :param str table: The table are we going to access
    :param int batch_size: Batch size (items returned per HTTP request). Default is ``500``.
    :param bool rewindable: If we can rewind the record. Default is ``True``. If ``False`` then we cannot rewind 
                            the record, which means as an Iterable this object will be 'spent' after iteration.
                            This is normally the default behavior expected for a python Iterable, but not a GlideRecord.
                            When ``False`` less memory will be consumed, as each previous record will be collected.
    """
    def __init__(self, client: 'ServiceNowClient', table: str, batch_size: int=500, rewindable: bool=True):
        self._log = logging.getLogger(__name__)
        self._client = client
        self.__table: str = table
        self.__is_iter: bool = False
        self.__batch_size: int = batch_size
        self.__query: Query = Query(table)
        self.__encoded_query: Optional[str] = None
        self.__results: list = []
        self.__current: int = -1
        self.__field_limits: Optional[List[str]] = None
        self.__view: Optional[str] = None
        self.__total: Optional[int] = None
        self.__limit: Optional[int] = None
        self.__page: int = -1
        self.__order: str = "ORDERBYsys_id" # we *need* a default order in the event we page, see issue#96
        self.__is_new_record: bool = False
        self.__display_value: Union[bool, str] = 'all'
        self.__exclude_reference_link: bool = True
        self.__rewindable = rewindable

    def _clear_query(self):
        self.__query = Query(self.__table)

    def _parameters(self):
        ret = dict(
            sysparm_query=self.__query.generate_query(encoded_query=self.__encoded_query, order_by=self.__order)
        )
        if self.__field_limits and len(self.__field_limits) > 0:
            c = self.__field_limits
            if 'sys_id' not in self.__field_limits:
                c.insert(0, 'sys_id')

            ret['sysparm_fields'] = ','.join(c)
        if self.__view:
            ret['sysparm_view'] = self.__view

        ret['sysparm_display_value'] = str(self.display_value).lower()
        ret['sysparm_exclude_reference_link'] = str(self.exclude_reference_link).lower()
        # Batch size matters! Transaction limits will exceed.
        # This also means we have to be pretty specific with limits
        limit = None
        if self.__limit:
            if self.__limit >= self.batch_size:
                # need to re-calc as our actual queried count will end up greater than our limit
                # this keeps us at our actual limit even when between batch size boundaries
                if (self.__current + self.batch_size) > self.__limit:
                    limit = self.__limit - self.__current - 1
            elif self.__limit <= self.batch_size or self.__limit > 0:
                # limit is less than batch, nothing special to do
                limit = self.__limit
        if limit is None and self.batch_size:
            limit = self.batch_size
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

    @property
    def table(self) -> str:
        """
        :return: The table we are operating on
        """
        return self.__table

    def __len__(self):
        return self.get_row_count()

    def get_row_count(self) -> int:
        """
        Glide compatable method.

        :return: the total
        """
        return self.__total if self.__total is not None else 0

    @property
    def fields(self) -> Union[List[str], None]:
        """
        :return: Fields in which this record will query OR has queried
        """
        if self.__field_limits:
            return self.__field_limits
        c = self._current()
        if c:
            return list(c.keys())
        else:
            if len(self.__results) > 0:
                return list(self.__results[0].keys())
        return None

    @fields.setter
    def fields(self, fields: Union[str, List[str]]):
        """
        Set the fields to query, in CSV string format or as a list
        """
        if isinstance(fields, str):
            fields = fields.split(',')
        self.__field_limits = fields

    @property
    def view(self):
        """
        :return: The current view
        """
        return self.__view

    @view.setter
    def view(self, view):
        self.__view = view

    @property
    def limit(self) -> Optional[int]:
        """
        :return: Query number limit
        """
        return self.__limit

    @limit.setter
    def limit(self, count: int):
        self.__limit = count

    @property
    def batch_size(self) -> int:
        """
        :return: The number of records to query in a single HTTP GET
        """
        return self.__batch_size

    @batch_size.setter
    def batch_size(self, size: int):
        if self.limit:
            assert size < self.limit
        self.__batch_size = size

    @property
    def location(self) -> int:
        """
        Current location within the iteration
        :return: location is -1 if iteration has not started
        :rtype: int
        """
        return self.__current

    @location.setter
    def location(self, location: int):
        """
        Set the current location

        :param location: the location to be at
        """
        assert self.__total is not None, 'no location to be had when we have no query'
        assert -1 <= location < self.__total
        self.__current = location

    @property
    def display_value(self):
        return self.__display_value

    @display_value.setter
    def display_value(self, display_value):
        """
        True: Returns the display values for all fields.
        False: Returns the actual values from the database.
        all: Returns both actual and display values.
        """
        assert display_value in [True, False, 'all']
        self.__display_value = display_value

    @property
    def exclude_reference_link(self):
        return self.__exclude_reference_link

    @exclude_reference_link.setter
    def exclude_reference_link(self, exclude_reference_link):
        """
        True: Exclude Table API links for reference fields.
        False: Include Table API links for reference fields.
        """
        assert exclude_reference_link in [True, False]
        self.__exclude_reference_link = exclude_reference_link

    def order_by(self, column: str):
        """
        Set the order in ascending

        :param column: Column to sort by
        """
        if column:
            self.__order = "ORDERBY%s" % column
        else:
            self.__order = "ORDERBYsys_id"

    def order_by_desc(self, column: str):
        """
        Set the order in decending

        :param column: Column to sort by
        """
        if column:
            self.__order = "ORDERBYDESC%s" % column
        else:
            self.__order = 'ORDERBYDESCsys_id'

    def pop_record(self) -> 'GlideRecord':
        """
        Pop the current record into a new :class:`GlideRecord` object - equivalent to a clone of a singular record
        FIXME: this, by the name, should be a destructive operation, but it is not.

        :return: Give us a new :class:`GlideRecord` containing only the current record
        """
        gr = GlideRecord(self._client, self.__table)
        c = self.__results[self.__current]
        gr.__results = [copy.deepcopy(c)]
        gr.__current = 0
        gr.__total = 1
        return gr

    def initialize(self):
        """
        Must be called for records to initialize data frame. Will not be able to set values otherwise.
        """
        self.__results = [{}]
        self.__current = 0
        self.__total = 1
        self.__is_new_record = True

    def is_new_record(self) -> bool:
        """
        Is this a new record?
        :return: ``True`` or ``False``
        """
        return len(self.__results) == 1 and self.__is_new_record

    def set_new_guid_value(self, value):
        """
        This does make an assumption the guid is a sys_id, if it is not, set the value directly.

        :param value: A 32 byte string that is the value
        """
        value = str(value)
        assert len(value) == 32, "GUID must be a 32 byte string"
        self.set_value('sys_id', value)

    def rewind(self):
        """
        Rewinds the record (iterable) so it may be iterated upon again. Only possible when the record is rewindable.
        """
        if not self._is_rewindable():
            raise Exception('Cannot rewind a non-rewindable record')
        self.__current = -1

    def changes(self) -> bool:
        """
        Determines weather any of the fields in the record have changed
        """
        obj = self._current()
        if obj:
            has_changed = False
            for key, value in obj.items():
                has_changed |= value.changes()
            return has_changed
        return False


    def query(self, query=None):
        """
        Query the table - executes a GET

        :raise:
            :AuthenticationException: If we do not have rights
            :RequestException: If the transaction is canceled due to execution time
        """
        if not self._is_rewindable() and self.__current > 0:
            raise RuntimeError(f"huh {self._is_rewindable} and {self.__current}")
        #    raise RuntimeError('Cannot re-query a non-rewindable record that has been iterated upon')
        self._do_query(query)

    def _do_query(self, query=None):
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
                self._client.batch_api.execute()
            else:
                response = self._client.table_api.list(self)
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

    def get(self, name, value=None) -> bool:
        """
        Get a single record, accepting two values. If one value is passed, assumed to be sys_id. If two values are
        passed in, the first value is the column name to be used. Can return multiple records.

        :param value: the ``sys_id`` or the field to query
        :param value2: the field value
        :return: ``True`` or ``False`` based on success
        """
        if value is None:
            try:
                response = self._client.table_api.get(self, name)
            except NotFoundException:
                return False
            self.__results = [self._transform_result(response.json()['result'])]
            if len(self.__results) > 0:
                self.__current = 0
                self.__total = len(self.__results)
                return True
            return False
        else:
            self.add_query(name, value)
            self._do_query()
            return self.next()

    def insert(self) -> Optional[GlideElement]:
        """
        Insert a new record.

        :return: The ``sys_id`` of the record created or ``None``
        :raise:
            :AuthenticationException: If we do not have rights
            :InsertException: For any other failure reason
        """
        response = self._client.table_api.post(self)
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

    def update(self) -> Optional[GlideElement]:
        """
        Update the current record.

        :return: The ``sys_id`` on success or ``None``
        :raise:
            :AuthenticationException: If we do not have rights
            :UpdateException: For any other failure reason
        """
        response = self._client.table_api.put(self)
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

    def delete(self) -> bool:
        """
        Delete the current record

        :return: ``True`` on success
        :raise:
            :AuthenticationException: If we do not have rights
            :DeleteException: For any other failure reason
        """
        response = self._client.table_api.delete(self)
        code = response.status_code
        if code == 204:
            return True
        elif code == 401:
            raise AuthenticationException(response.json()['error'])
        else:
            raise DeleteException(response.json(), status_code=code)

    def delete_multiple(self) -> bool:
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
            self._do_query()

        allRecordsWereDeleted = True
        def handle(response):
            nonlocal  allRecordsWereDeleted
            if response is None or response.status_code != 204:
                allRecordsWereDeleted = False

        for e in self:
            self._client.batch_api.delete(e, handle)
        self._client.batch_api.execute()
        return allRecordsWereDeleted

    def update_multiple(self, custom_handler=None) -> bool:
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

        self._client.batch_api.execute()
        return updated

    def _get_value(self, item, key='value'):
        obj = self._current()
        if obj is None:
            raise NoRecordException('cannot get a value from nothing, did you forget to call next() or initialize()?')
        if item in obj:
            o = obj[item]
            if key == 'display_value':
                return o.get_display_value()
            if key == 'link':
                return o.get_link()
            return o.get_value()
        return None

    def get_value(self, field) -> Any:
        """
        Return the value field for the given field

        :param str field: The field
        :return: The field value or ``None``
        """
        return self._get_value(field, 'value')

    def get_display_value(self, field) -> Any:
        """
        Return the display value for the given field

        :param str field: The field, required
        :return: The field value or ``None``
        """
        assert field, 'cannot get the display value for the entire record, as the API does not tell us what that is'
        return self._get_value(field, 'display_value')

    def get_element(self, field) -> GlideElement:
        """
        Return the backing GlideElement for the given field. This is the only method to directly access this element.gr2.serialize()

        :param str field: The Field
        :return: The GlideElement class or ``None``
        """
        c = self._current()
        if c is None:
            raise NoRecordException('cannot get a value from nothing, did you forget to call next() or initialize()?')
        return self._current()[field] if field in c else None

    def set_value(self, field, value):
        """
        Set the value for a field.

        :param str field: The field
        :param value: The Value
        """
        c = self._current()
        if c is None:
            raise NoRecordException('cannot get a value from nothing, did you forget to call next() or initialize()?')
        if field not in c:
            if isinstance(value, GlideElement):
                c[field] = GlideElement(field, value.get_value(), value.get_display_value(), parent_record=self)
            else:
                c[field] = GlideElement(field, value, parent_record=self)
        else:
            c[field].set_value(value)

    def set_display_value(self, field, value):
        """
        Set the display value for a field.

        :param str field: The field
        :param value: The Value
        """
        c = self._current()
        if c is None:
            raise NoRecordException('cannot get a value from nothing, did you forget to call next() or initialize()?')
        if field not in c:
            c[field] = GlideElement(field, display_value=value, parent_record=self)
        else:
            c[field].set_display_value(value)

    def set_link(self, field, value):
        """
        Set the link for a field, it is however preferable to to `gr.field.set_link(value)`.

        :param str field: The field
        :param value: The Value
        """
        c = self._current()
        if c is None:
            raise NoRecordException('cannot get a value from nothing, did you forget to call next() or initialize()?')
        if field not in c:
            c[field] = GlideElement(field, link=value, parent_record=self)
        else:
            c[field].set_link(value)

    def get_link(self, no_stack: bool=False) -> str:
        """
        Generate a full URL to the current record. sys_id will be -1 if there is no current record.

        :param bool no_stack: Default ``False``, adds ``&sysparm_stack=<table>_list.do?sysparm_query=active=true`` to the URL
        :param bool list: Default ``False``, if ``True`` then provide a link to the record set, not the current record
        :return: The full URL to the current record
        :rtype: str
        """
        ins = self._client.instance
        obj = self._current()
        stack = '&sysparm_stack=%s_list.do?sysparm_query=active=true' % self.__table
        if no_stack:
            stack = ''
        id = self.sys_id if obj else None
        id = id or '-1'
        return "{}/{}.do?sys_id={}{}".format(ins, self.__table, id, stack)

    def get_link_list(self) -> Optional[str]:
        """
        Generate a full URL to for the current query.

        :return: The full URL to the record query
        """
        ins = self._client.instance
        sysparm_query = self.get_encoded_query()
        url = "{}/{}_list.do".format(ins, self.__table)
        # Using `requests` as to be py2/3 agnostic and to encode the URL properly.
        return Request('GET', url, params=dict(sysparm_query=sysparm_query)).prepare().url

    def get_encoded_query(self) -> str:
        """
        Generate the encoded query. Does not respect limits.

        :return: The encoded query, empty string if none exists
        """
        return self.__query.generate_query(encoded_query=self.__encoded_query, order_by=self.__order)

    def get_unique_name(self) -> str:
        """
        always give us the sys_id
        """
        return self.get_value('sys_id')

    def get_attachments(self) -> 'Attachment':
        """
        Get the attachments for the current record or the current table

        :return: A list of attachments
        :rtype: :class:`pysnc.Attachment`
        """
        attachment = self._client.Attachment(self.__table)
        if self.sys_id:
            attachment.add_query('table_sys_id', self.sys_id)
        attachment.query()
        return attachment

    def add_attachment(self, file_name, file, content_type=None, encryption_context=None):
        if self._current() is None:
            raise NoRecordException('cannot add attachment to nothing, did you forget to call next() or initialize()?')

        attachment = self._client.Attachment(self.__table)
        return attachment.add_attachment(self.sys_id, file_name, file, content_type, encryption_context)

    def add_active_query(self) -> QueryCondition:
        """
        Equivilant to the following::

           add_query('active', 'true')

        """
        return self.__query.add_active_query()

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

    def add_join_query(self, join_table, primary_field=None, join_table_field=None) -> JoinQuery:
        """
        Do a join query::

            gr = client.GlideRecord('sys_user')
            join_query = gr.add_join_query('sys_user_group', join_table_field='manager')
            join_query.add_query('active','true')
            gr.query()

        :param str join_table: The table to join against
        :param str primary_field: The current table field to use for the join. Default is ``sys_id``
        :param str join_table_field: The ``join_Table`` field to use for the join
        :return: :class:`query.JoinQuery`
        """
        return self.__query.add_join_query(join_table, primary_field, join_table_field)

    def add_rl_query(self, related_table, related_field, operator_condition, stop_at_relationship=False):
        """
        Generates a 'Related List Query' which is defined as:

        RLQUERY<other_table_name>.<field>,<operator><value>[,m2m][^subquery]^ENDRLQUERY

        For example, when querying sys_user to simulate a LEFT OUTER JOIN to find active users with no manager:

        RLQUERYsys_user.manager,=0^active=true^ENDRLQUERY

        If we find users with a specific role:

        RLQUERYsys_user_has_role.user,>0^role=ROLESYSID^ENDRLQUERY

        But if we want to dotwalk the role (aka set stop_at_relationship=True):

        RLQUERYsys_user_has_role.user,>0,m2m^role.name=admin^ENDRLQUERY

        :param str related_table: The table with the relationship -- the other table
        :param str related_field: The field to use to relate from the other table to the table we are querying on
        :param str operator_condition: The operator to use to relate the two tables, as in `=0` or `>=1` -- this is not validated by pysnc
        :param bool stop_at_relationship: if we have a subquery (a query condition ON the RLQUERY) AND it dot walks, this must be True. Default is False.
        """
        return self.__query.add_rl_query(related_table, related_field, operator_condition, stop_at_relationship)

    def add_encoded_query(self, encoded_query):
        """
        Adds a raw query. Appends (comes after) all other defined queries e.g. :func:`add_query`

        :param str encoded_query: The same as ``sysparm_query``
        """

        self.__encoded_query = encoded_query

    def add_null_query(self, field) -> QueryCondition:
        """
        If the specified field is empty
        Equivilant to the following::

           add_query(field, '', 'ISEMPTY')

        :param str field: The field to validate
        """
        return self.__query.add_null_query(field)

    def add_not_null_query(self, field) -> QueryCondition:
        """
        If the specified field is `not` empty
        Equivilant to the following::

           add_query(field, '', 'ISNOTEMPTY')

        :param str field: The field to validate
        """
        return self.__query.add_not_null_query(field)

    def _serialize(self, record, display_value, fields=None, changes_only=False, exclude_reference_link=True):
        if isinstance(display_value, str):
            v_type = 'both'
        else:
            v_type = 'display_value' if display_value else 'value'

        def compress(obj):
            ret = dict()
            if not obj:
                return None
            for key, value in obj.items():
                if fields and key not in fields:
                    continue
                if isinstance(value, GlideElement):
                    if changes_only and not value.changes():
                        continue
                    if exclude_reference_link or value.get_link() is None:
                        if v_type == 'display_value':
                            ret[key] = value.get_display_value()
                        elif v_type == 'both':
                            ret[key] = value.serialize()
                        else:
                            ret[key] = value.get_value()
                    else:
                        serialized = value.serialize()
                        if v_type == 'display_value':
                            serialized.pop('value', None)
                        elif v_type == 'value':
                            serialized.pop('display_value', None)
                        ret[key] = serialized
                else:
                    ret[key] = value.get_value()
            return ret

        return compress(record)

    def serialize(self, display_value=False, fields=None, fmt=None, changes_only=False, exclude_reference_link=True) -> Any:
        """
        Turn current record into a dictGlideRecord(None, 'incident')

        :param display_value: ``True``, ``False``, or ``'both'``
        :param list fields: Fields to serialize. Defaults to all fields.
        :param str fmt: None or ``pandas``. Defaults to None
        :param changes_only: Do we want to serialize only the fields we've modified?
        :param exclude_reference_link: Do we want to exclude the reference link? default is True
        :return: dict representation
        """
        if fmt == 'pandas':
            self._log.warning('Pandas serialize format is depricated')
            # Pandas format
            def transform(obj):
                # obj == GlideRecord
                ret = dict(sys_class_name=self.table)
                for f in obj.fields:
                    if f == 'sys_id':
                        ret['sys_id'] = obj.get_value(f)
                    else:
                        # value
                        ret['%s__value' % f] = obj.get_value(f)
                        # display value
                        ret['%s__display' % f] = obj.get_display_value(f)
                return ret
            return transform(self) # i know this is inconsistent, self vs current
        else:
            c = self._current()
            return self._serialize(c, display_value, fields, changes_only, exclude_reference_link)

    def serialize_all(self, display_value=False, fields=None, fmt=None, exclude_reference_link=True) -> list:
        """
        Serialize the entire query. See serialize() docs for details on parameters

        :param display_value:
        :param fields:
        :param fmt:
        :return: list
        """
        return [record.serialize(display_value, fields, fmt, exclude_reference_link) for record in self]

    def to_pandas(self, columns=None, mode='smart'):
        """
        This is similar to serialize_all, but we by default include a table column and split into `__value`/`__display` if
        the values are different (mode == `smart`). Other modes include `both`, `value`, and `display` in which behavior
        follows their name.

        ```
        df = pd.DataFrame(gr.to_pandas())
        ```

        Note: it is highly recommended you first restrict the number of columns generated by settings :func:`fields` first.

        :param mode: How do we want to serialize the data, options are `smart`, `both`, `value`, `display`
        :rtype: tuple
        :return: ``(list, list)`` inwhich ``(data, fields)``
        """
        fres = []
        if mode == 'smart':
            for f in self.fields:
                column_equals = True
                self.rewind()
                while (self.next() and column_equals):
                    v = self.get_value(f)
                    d = self.get_display_value(f)
                    #print(f'{v} == {d} ? {v == d}')
                    column_equals &= (v == d)
                if column_equals:
                    fres.append(f)
                else:
                    fres.append('%s__value' % f)
                    fres.append('%s__display' % f)
        elif mode == 'both':
            for f in self.fields:
                fres.append('%s__value' % f)
                fres.append('%s__display' % f)
        else:
            fres = self.fields

        if columns:
            assert len(fres) == len(columns)

        data = OrderedDict({k:[] for k in fres})

        if len(self.fields) > 20:
            self._log.warning("Generating data for a large number of columns (>20) - consider limiting fields")

        for gr in self:
            if mode == 'value':
                for f in fres:
                    data[f].append(gr.get_value(f))
            elif mode == 'display':
                for f in fres:
                    data[f].append(gr.get_display_value(f))
            else:
                for f in fres:
                    field = f.split('__')
                    if len(field) == 2:
                        if field[1] == 'value':
                            data[f].append(gr.get_value(field[0]))
                        elif field[1] == 'display':
                            data[f].append(gr.get_display_value(field[0]))
                    else:
                        data[f].append(gr.get_display_value(field[0]))

        if columns:
            # update keys
            return OrderedDict((c, v) for (c, (k, v)) in zip(columns, data.items()))

        return data

    def _is_rewindable(self) -> bool:
        return self.__rewindable

    def __iter__(self):
        self.__is_iter = True
        if self._is_rewindable():
            self.rewind()
        return self

    def __next__(self):
        return self.next()

    def next(self, _recursive=False) -> bool:
        """
        Returns the next record in the record set

        :return: ``True`` or ``False`` based on success
        """
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

    def has_next(self) -> bool:
        """
        Do we have a next record in the iteration?

        :return: ``True`` or ``False``
        """
        l = len(self.__results)
        if l > 0 and self.__current + 1 < l:
            return True
        return False

    def _transform_result(self, result):
        for key, value in result.items():
            result[key] = GlideElement(key, value, parent_record=self)
        return result

    def __str__(self):
        return """{}({})""".format(
            self.__table,
            self._serialize(self._current(), False)
        )

    def __setattr__(self, key, value):
        if key.startswith('_'):
            # Obviously internal
            super(GlideRecord, self).__setattr__(key, value)
        else:
            propobj = getattr(self.__class__, key, None)
            if isinstance(propobj, property):
                if propobj.fset is None:
                    raise AttributeError("can't set attribute")
                propobj.fset(self, value)
            else:
                self.set_value(key, value)

    def __getattr__(self, item):
        # TODO: allow override for record fields which may overload our local properties by prepending _
        obj = self._current()
        if obj:
            return self.get_element(item)
            #return self.get_value(item)
        return self.__getattribute__(item)

    def __contains__(self, item):
        obj = self._current()
        if obj:
            return item in obj
        return False



