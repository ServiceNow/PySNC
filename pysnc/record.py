import logging
import copy
import traceback
from requests import Request
from six import string_types
from collections import OrderedDict
from .query import *
from .exceptions import *
from .attachment import Attachment


class GlideRecord(object):
    """
    The GlideRecord object. Normally instantiated via convenience method :func:`pysnc.ServiceNowClient.GlideRecord`.
    This object allows us to interact with a specific table via the table rest api.

    :param ServiceNowClient client: We need to know which instance we're connecting to
    :param str table: The table are we going to access
    :param int batch_size: Batch size (items returned per HTTP request). Default is ``10``.
    """
    def __init__(self, client, table, batch_size=10):
        self._client = client
        self.__table = table
        self.__is_iter = False
        self._log = logging.getLogger(__name__)
        self._client = client
        self.__table = table
        self.__batch_size = batch_size
        self.__query = Query(table)
        self.__encoded_query = None
        self.__results = []
        self.__current = -1
        self.__field_limits = None
        self.__view = None
        self.__total = None
        self.__limit = None
        self.__page = -1
        self.__order = None
        self.__is_new_record = False

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

    @property
    def table(self):
        """
        :return: The table we are operating on
        """
        return self.__table

    def __len__(self):
        return self.get_row_count()

    def get_row_count(self):
        """
        Glide compatable method.

        :return: the total
        """
        return self.__total if self.__total is not None else 0

    @property
    def fields(self):
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
    def fields(self, fields):
        if isinstance(fields, string_types):
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
    def limit(self):
        """
        :return: Query number limit
        """
        return self.__limit

    @limit.setter
    def limit(self, count):
        self.__limit = count

    @property
    def batch_size(self):
        """
        :return: The number of records to query in a single HTTP GET
        """
        return self.__batch_size

    @batch_size.setter
    def batch_size(self, size):
        if self.limit:
            assert size < self.limit
        self.__batch_size = size

    @property
    def location(self):
        """
        Current location within the iteration
        :return: location is -1 if iteration has not started
        :rtype: int
        """
        return self.__current

    @location.setter
    def location(self, location):
        """
        Set the current location

        :param location: the location to be at
        """
        assert -1 <= location < self.__total
        self.__current = location

    def order_by(self, column):
        """
        Set the order in ascending

        :param column: Column to sort by
        """
        if column:
            self.__order = "ORDERBY%s" % column
        else:
            self.__order = None

    def order_by_desc(self, column):
        """
        Set the order in decending

        :param column: Column to sort by
        """
        if column:
            self.__order = "ORDERBYDESC%s" % column
        else:
            self.__order = None

    def pop_record(self):
        """
        Pop the current record into a new :class:`GlideRecord` object - equivalent to a clone of a singular record

        :return: Give us a new :class:`GlideRecord` containing only the current record
        """
        gr = GlideRecord(None, self.__table)
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

    def is_new_record(self):
        """
        Is this a new record?
        :return: ``True`` or ``False``
        :rtype: bool
        """
        return len(self.__results) == 1 and self.__is_new_record

    def rewind(self):
        """
        Rewinds the record so it may be iterated upon again. Not required to be called if iterating in the pythonic method.
        """
        self.__current = -1

    def query(self):
        """
        Query the table - executes a GET

        :return: void
        :raise:
            :AuthenticationException: If we do not have rights
            :RequestException: If the transaction is canceled due to execution time
        """
        response = self._client._list(self)
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

    def get(self, name, value=None):
        """
        Get a single record, accepting two values. If one value is passed, assumed to be sys_id. If two values are
        passed in, the first value is the column name to be used. Can return multiple records.

        :param value: the ``sys_id`` or the field to query
        :param value2: the field value
        :return: ``True`` or ``False`` based on success
        :raise:
            :AuthenticationException: If we do not have rights
        """
        if value == None:
            response = self._client._get(self, name)
            code = response.status_code
            if code == 200:
                self.__results = [self._transform_result(response.json()['result'])]
                if len(self.__results) > 0:
                    self.__current = 0
                    self.__total = len(self.__results)
                    return True
                return False
            elif code == 401:
                raise AuthenticationException(response.json()['error'])
        else:
            self.add_query(name, value)
            self.query()
            if self.next():
                return True
            return False

    def insert(self):
        """
        Insert a new record.

        :return: The ``sys_id`` of the record created or ``None``
        :raise:
            :AuthenticationException: If we do not have rights
            :InsertException: For any other failure reason
        """
        response = self._client._post(self)
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
            raise InsertException(response.json(), status_code=code)

    def update(self):
        """
        Update the current record.

        :return: The ``sys_id`` on success or ``None``
        :raise:
            :AuthenticationException: If we do not have rights
            :UpdateException: For any other failure reason
        """
        response = self._client._put(self)
        code = response.status_code
        if code == 200:
            #self.__results = [response.json()['result']]
            # TODO: figure out if i should splice in the result...
            # pro: can avoid data mis-match scenarios
            # con: unexpected local data-updates without re-query?
            if len(self.__results) > 0:
                return self.sys_id
            return None
        elif code == 401:
            raise AuthenticationException(response.json()['error'])
        else:
            raise UpdateException(response.json(), status_code=code)

    def delete(self):
        """
        Delete the current record

        :return: ``True`` on success
        :raise:
            :AuthenticationException: If we do not have rights
            :DeleteException: For any other failure reason
        """
        response = self._client._delete(self)
        code = response.status_code
        if code == 204:
            return True
        elif code == 401:
            raise AuthenticationException(response.json()['error'])
        else:
            raise DeleteException(response.json(), status_code=code)

    def delete_multiple(self):
        """
        Deletes the current query, funny enough this is the same as iterating and deleting each record since we're
        using the REST api.
        :return: ``True`` on success
        :raise:
            :AuthenticationException: If we do not have rights
            :DeleteException: For any other failure reason
        """
        # cannot call query before this...
        if self.__total != None:
            raise DeleteException('Cannot deleteMultiple after a query is performed')

        self.fields = 'sys_id'  # all we need...
        self.query()
        for e in self:
            e.delete()
        return True

    def _get_value(self, item, key='value'):
        obj = self._current()
        if item in obj:
            o = obj[item]
            if key == 'display_value':
                return o.get_display_value()
            return o.get_value()
        return None

    def get_value(self, field):
        """
        Return the value field for the given field

        :param str field: The field
        :return: The field value or ``None``
        """
        return self._get_value(field, 'value')

    def get_display_value(self, field):
        """
        Return the display value for the given field

        :param str field: The field
        :return: The field value or ``None``
        """
        return self._get_value(field, 'display_value')

    def get_element(self, field):
        """
        Return the backing GlideElement for the given field. This is the only method to directly access this element.

        :param str field: The Field
        :return: The GlideElement class or ``None``
        """
        c = self._current()
        return self._current()[field] if field in c else None

    def set_value(self, field, value):
        """
        Set the value for a field.

        :param str field: The field
        :param value: The Value
        """
        c = self._current()
        if field not in c:
            c[field] = GlideElement(field, value)
        else:
            c[field].set_value(value)

    def set_display_value(self, field, value):
        """
        Set the display value for a field.

        :param str field: The field
        :param value: The Value
        """
        c = self._current()
        if field not in c:
            c[field] = GlideElement(field, display_value=value)
        else:
            c[field].set_display_value(value)

    def get_link(self, no_stack=False):
        """
        Generate a full URL to the current record. sys_id will be null if there is no current record.

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
        id = self.sys_id if obj else 'null'
        return "{}/{}.do?sys_id={}{}".format(ins, self.__table, id, stack)

    def get_link_list(self):
        """
        Generate a full URL to for the current query.

        :return: The full URL to the record query
        :rtype: str
        """
        ins = self._client.instance
        sysparm_query = self.get_encoded_query()
        url = "{}/{}_list.do".format(ins, self.__table)
        # Using `requests` as to be py2/3 agnostic and to encode the URL properly.
        return Request('GET', url, params=dict(sysparm_query=sysparm_query)).prepare().url

    def get_encoded_query(self):
        """
        Generate the encoded query. Does not respect limits.

        :return: The encoded query, empty string if none exists
        """
        return self.__query.generate_query(encoded_query=self.__encoded_query, order_by=self.__order)

    def get_attachments(self):
        """
        Get the attachments for the current record or the current table

        :return: A list of attachments
        :rtype: :class:`pysnc.Attachment`
        """
        id = self.sys_id if self._current() else None
        attachment = self._client.Attachment(self.__table, id)
        attachment.query()
        return attachment

    def add_attachment(self, file_name, file, content_type=None, encryption_context=None):
        if self._current() == None:
            raise UpdateException('Cannot attach to non existant record')

        id = self.sys_id if self._current() else None
        attachment = self._client.Attachment(self.__table, id)
        attachment.query()

        attachment.add_attachment(file_name, file, content_type, encryption_context)


    def add_active_query(self):
        """
        Equivilant to the following::

           add_query('active', 'true')

        """
        self.__query.add_active_query()

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

    def add_join_query(self, join_table, primary_field=None, join_table_field=None):
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

    def add_encoded_query(self, encoded_query):
        """
        Adds a raw query. Appends (comes after) all other defined queries e.g. :func:`add_query`

        :param str encoded_query: The same as ``sysparm_query``
        """

        self.__encoded_query = encoded_query

    def add_null_query(self, field):
        """
        If the specified field is empty
        Equivilant to the following::

           add_query(field, '', 'ISEMPTY')

        :param str field: The field to validate
        """
        self.__query.add_null_query(field)

    def add_not_null_query(self, field):
        """
        If the specified field is `not` empty
        Equivilant to the following::

           add_query(field, '', 'ISNOTEMPTY')

        :param str field: The field to validate
        """
        self.__query.add_not_null_query(field)

    def _serialize(self, record, display_value, fields=None, changes_only=False):
        if isinstance(display_value, string_types):
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
                    if display_value:
                        ret[key] = value.get_display_value()
                    else:
                        ret[key] = value.get_value()
                else:
                    ret[key] = value.get_value()
            return ret

        return compress(record)

    def serialize(self, display_value=False, fields=None, fmt=None, changes_only=False):
        """
        Turn current record into a dict

        :param display_value: ``True``, ``False``, or ``'both'``
        :param list fields: Fields to serialize. Defaults to all fields.
        :param str fmt: None or ``pandas``. Defaults to None
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
            return self._serialize(c, display_value, fields, changes_only)

    def serialize_all(self, display_value=False, fields=None, fmt=None):
        """
        Serialize the entire query. See serialize() docs for details on parameters

        :param display_value:
        :param fields:
        :param fmt:
        :return: list
        """
        return [record.serialize(display_value, fields, fmt) for record in self]

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

    def __iter__(self):
        self.__is_iter = True
        self.rewind()
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
        if self.__total and self.__total > 0 and \
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

    def has_next(self):
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
            result[key] = GlideElement(key, value)
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
            return self.get_value(item)
        return self.__getattribute__(item)

    def __contains__(self, item):
        obj = self._current()
        if obj:
            return item in obj
        return False


class GlideElement(object):
    """
    Object backing the value/display values of a given record entry.
    """
    def __init__(self, name, value=None, display_value=None):
        """
        Create a new GlideElement

        :param name:
        :param value:
        :param display_value:
        """
        self._name = name
        self._value = None
        self._display_value = None
        self._changed = False
        if isinstance(value, dict):
            self._value = value['value']
            self._display_value = value['display_value']
        else:
            self._value = value
        if display_value:
            self._display_value = display_value

    def get_name(self):
        return self._name

    def get_value(self):
        return self._value

    def get_display_value(self):
        if self._display_value:
            return self._display_value
        return self.get_value()

    def set_value(self, value):
        if isinstance(value, GlideElement):
            nv = value.get_value()

            if nv != self._value:
                self._changed = True

            self._value = nv
        else:
            if self._value != value:
                self._changed = True
                self._value = value

    def set_display_value(self, value):
        if isinstance(value, GlideElement):
            nv = value.get_display_value()
            if nv != self._display_value:
                self._changed = True
            self._display_value = nv
        else:
            if self._display_value != value:
                self._changed = True
                self._display_value = value

    def __str__(self):
        if self._display_value and self._value != self._display_value:
            return dict(value=self._value, display_value=self._display_value)
        return self._value

    def changes(self):
        """
        :return: if we have changed this value
        :rtype: bool
        """
        return self._changed

    def nil(self):
        """
        returns True if the value is None or zero length

        :return: if this value is anything
        :rtype: bool
        """
        return not self._value or len(self._value) == 0

