from typing import Any, Dict, List, Optional, TYPE_CHECKING

from .query import Query

if TYPE_CHECKING:
    from .client import ServiceNowClient


__all__ = ['GlideAggregate', 'AggregateType']


class AggregateType:
    """Aggregate function names accepted by :meth:`GlideAggregate.add_aggregate`,
    :meth:`GlideAggregate.get_aggregate`, and :meth:`GlideAggregate.add_having`.

    .. note::
        The server-side ``GlideAggregate`` also supports ``STDDEV``, but the
        REST Stats API (``/api/now/stats``) does not expose it — the only
        aggregate parameters it accepts are ``sysparm_count``,
        ``sysparm_sum_fields``, ``sysparm_avg_fields``, ``sysparm_min_fields``,
        and ``sysparm_max_fields``. ``STDDEV`` is therefore intentionally omitted.
    """

    COUNT = 'COUNT'
    SUM   = 'SUM'
    AVG   = 'AVG'
    MIN   = 'MIN'
    MAX   = 'MAX'


class GlideAggregate(Query):
    """
    Aggregate queries against a ServiceNow table via ``/api/now/stats/{table}``.
    Mirrors the server-side ``GlideAggregate``.

    Inherits :meth:`pysnc.query.Query.add_query`, :meth:`add_null_query`,
    :meth:`add_not_null_query`, and :meth:`add_active_query` for filter
    construction; adds :meth:`add_encoded_query` / :meth:`get_encoded_query`
    for raw encoded-query support.

    Example::

        ga = client.GlideAggregate('incident')
        ga.add_active_query()
        ga.add_aggregate('COUNT')
        ga.add_aggregate('AVG', 'reassignment_count')
        ga.group_by('priority')
        ga.query()
        for row in ga:
            print(row.get_value('priority'), row.get_aggregate('COUNT'))

    For a single ungrouped scalar (e.g. a row count), advance the cursor once::

        ga = client.GlideAggregate('incident')
        ga.add_active_query()
        ga.add_aggregate('COUNT')
        ga.query()
        ga.next()
        count = int(ga.get_aggregate('COUNT'))
    """

    def __init__(self, client: 'ServiceNowClient', table: str) -> None:
        """
        :param ServiceNowClient client: Authenticated PySNC client
        :param str table: Table name to aggregate over (e.g. ``'incident'``)
        """
        super().__init__(table)
        self._client = client
        self._aggregates: List[Dict[str, Optional[str]]] = []
        self._group_by_fields: List[str] = []
        self._order_by: Optional[str] = None
        self._havings: List[str] = []
        self._encoded_query: Optional[str] = None
        self._display_value: bool = False
        self._results: List[Dict[str, Any]] = []
        self._cursor: int = -1

    @property
    def table(self) -> str:
        """The table being aggregated."""
        return self._table

    # ============================================================
    # Query construction
    # ============================================================

    def add_encoded_query(self, encoded_query: str) -> None:
        """
        Append a raw encoded query. Combined with conditions added via
        :meth:`add_query` and friends.

        :param str encoded_query: An encoded ServiceNow query string
            (e.g. ``'active=true^priority=1'``)
        """
        self._encoded_query = encoded_query

    def get_encoded_query(self) -> str:
        """
        Return the encoded query that would be sent as ``sysparm_query``.

        :return: The encoded query, empty string if none defined
        """
        return self.generate_query(encoded_query=self._encoded_query)

    def add_aggregate(self, agg_type: str, field: Optional[str] = None) -> None:
        """
        Add an aggregate function to compute.

        :param str agg_type: One of :class:`AggregateType` values
            (``COUNT``, ``SUM``, ``AVG``, ``MIN``, ``MAX``)
        :param str field: Required for ``SUM``, ``AVG``, ``MIN``, ``MAX``.
            Omit for ``COUNT``.
        """
        self._aggregates.append({'type': agg_type, 'field': field})

    def group_by(self, field: str) -> None:
        """
        Group results by the given field. Call multiple times to group by
        multiple fields.

        :param str field: Field name to group by
        """
        self._group_by_fields.append(field)

    def order_by(self, field: str) -> None:
        """
        Order results by a group-by field, ascending.

        :param str field: Field name to order by
        """
        self._order_by = field

    def order_by_desc(self, field: str) -> None:
        """
        Order results by a group-by field, descending.

        :param str field: Field name to order by
        """
        self._order_by = "{}^DESC".format(field)

    def order_by_aggregate(self, agg_type: str, field: Optional[str] = None) -> None:
        """
        Order results by an aggregate value.

        :param str agg_type: Aggregate function (``COUNT``, ``SUM``, ``AVG``, ``MIN``, ``MAX``)
        :param str field: Required for non-COUNT aggregates
        """
        if field:
            self._order_by = "{}^{}".format(agg_type, field)
        else:
            self._order_by = agg_type

    def add_having(self, agg_type: str, field: str, operator: str, value: Any) -> None:
        """
        Filter grouped results by an aggregate value (HAVING clause).

        :param str agg_type: Aggregate function (``COUNT``, ``SUM``, ``AVG``, ``MIN``, ``MAX``)
        :param str field: Field to aggregate. Always required, even for ``COUNT``
            (use ``sys_id`` when no semantic field applies).
        :param str operator: Comparator (``>``, ``<``, ``=``, ``!=``, ``>=``, ``<=``)
        :param value: Value to compare against
        """
        # Wire syntax: sysparm_having=aggregate^field^operator^value
        # Aggregate name is lowercase; multi-clause separator is ',' (joined in _parameters).
        self._havings.append("{}^{}^{}^{}".format(agg_type.lower(), field, operator, value))

    def set_display_value(self, display_value: bool = True) -> None:
        """
        Toggle display value resolution for group-by fields.

        When ``True``, each result row exposes both raw and display values via
        :meth:`get_value` and :meth:`get_display_value`. When ``False`` (default),
        only raw values are returned.

        :param bool display_value: ``True`` to request both raw + display
            (sends ``sysparm_display_value=all`` internally), ``False`` to omit.
        """
        # NOTE: send 'all' rather than 'true'. 'true' replaces the raw value with
        # the label and drops the raw, breaking get_value(); 'all' returns both.
        self._display_value = bool(display_value)

    # ============================================================
    # Execution
    # ============================================================

    def query(self) -> None:
        """
        Execute the aggregate query. Populates internal results;
        use :meth:`next` or iterate to read rows.

        :raises NotFoundException: 404 from the Stats API
        :raises RoleException: 403 from the Stats API
        :raises AuthenticationException: 401 from the Stats API
        :raises RequestException: other non-2xx responses
        """
        r = self._client.stats_api.list(self)
        data = r.json()
        result = data.get('result', {})
        # Normalize: ungrouped responses are {stats: {...}}; grouped are [{stats, groupby_fields}, ...].
        if isinstance(result, list):
            self._results = result
        elif isinstance(result, dict):
            self._results = [result]
        else:
            self._results = []
        self._cursor = -1

    def _parameters(self) -> Dict[str, str]:
        params: Dict[str, str] = {}

        # Split aggregates into count + per-type field lists.
        type_fields: Dict[str, List[str]] = {}
        wants_count = False
        for agg in self._aggregates:
            t = agg.get('type')
            if t is None:
                continue
            t_upper = t.upper()
            if t_upper == 'COUNT':
                wants_count = True
                continue
            f = agg.get('field') or ''
            type_fields.setdefault(t_upper, []).append(f)

        if wants_count:
            params['sysparm_count'] = 'true'
        for t, fields in type_fields.items():
            # SUM -> sysparm_sum_fields, AVG -> sysparm_avg_fields, etc.
            params['sysparm_{}_fields'.format(t.lower())] = ','.join(fields)

        if self._group_by_fields:
            params['sysparm_group_by'] = ','.join(self._group_by_fields)

        if self._order_by:
            params['sysparm_order_by'] = self._order_by

        if self._havings:
            params['sysparm_having'] = ','.join(self._havings)

        sysparm_query = self.generate_query(encoded_query=self._encoded_query)
        if sysparm_query:
            params['sysparm_query'] = sysparm_query

        if self._display_value:
            params['sysparm_display_value'] = 'all'

        return params

    # ============================================================
    # Result cursor
    # ============================================================

    def next(self) -> bool:
        """
        Advance the cursor to the next result row.

        :return: ``True`` if a new row is available, ``False`` if exhausted
        """
        if self._cursor + 1 < len(self._results):
            self._cursor += 1
            return True
        return False

    def has_next(self) -> bool:
        """
        Whether another row is available without advancing the cursor.

        :return: ``True`` if a subsequent :meth:`next` call would succeed
        """
        return self._cursor + 1 < len(self._results)

    def get_row_count(self) -> int:
        """
        Number of result rows. For ungrouped queries this is 1 after :meth:`query`.

        :return: Number of rows in the result set
        """
        return len(self._results)

    # ============================================================
    # Result access (only valid after next() returns True)
    # ============================================================

    def get_aggregate(self, agg_type: str, field: Optional[str] = None) -> Optional[str]:
        """
        Return the aggregate value for the current row, as a string.

        :param str agg_type: Aggregate function (``COUNT``, ``SUM``, ``AVG``, ``MIN``, ``MAX``)
        :param str field: Required for non-COUNT aggregates
        :return: Aggregate value as string, or ``None`` if not present
        """
        if self._cursor < 0 or self._cursor >= len(self._results):
            return None
        stats = self._results[self._cursor].get('stats', {})
        t_upper = agg_type.upper()
        if t_upper == 'COUNT':
            return stats.get('count')
        # SUM/AVG/MIN/MAX live nested under their lowercase key as {field: value}.
        nested = stats.get(t_upper.lower())
        if not isinstance(nested, dict) or field is None:
            return None
        return nested.get(field)

    def get_value(self, field: str) -> Optional[str]:
        """
        Return the raw value of a group-by field for the current row.

        :param str field: A field name previously passed to :meth:`group_by`
        :return: Raw value as string, or ``None`` if not in the result
        """
        if self._cursor < 0 or self._cursor >= len(self._results):
            return None
        for gf in self._results[self._cursor].get('groupby_fields', []):
            if gf.get('field') == field:
                return gf.get('value')
        return None

    def get_display_value(self, field: str) -> Optional[str]:
        """
        Return the display value of a group-by field for the current row.
        Requires :meth:`set_display_value` to have been called with ``True``
        before :meth:`query`; otherwise falls back to the raw value.

        :param str field: A field name previously passed to :meth:`group_by`
        :return: Display label as string, or ``None`` if not in the result
        """
        if self._cursor < 0 or self._cursor >= len(self._results):
            return None
        for gf in self._results[self._cursor].get('groupby_fields', []):
            if gf.get('field') == field:
                return gf.get('display_value', gf.get('value'))
        return None

    # ============================================================
    # Pythonic affordances
    # ============================================================

    def __iter__(self):
        """Reset the cursor and return self. Iteration mutates the cursor and
        yields ``self`` each row — same pattern as :class:`pysnc.record.GlideRecord`."""
        self._cursor = -1
        return self

    def __next__(self):
        """Advance the cursor; raise ``StopIteration`` when exhausted."""
        if not self.next():
            raise StopIteration
        return self

    def __len__(self) -> int:
        """Number of result rows (alias for :meth:`get_row_count`)."""
        return self.get_row_count()
