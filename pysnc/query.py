from warnings import warn


class BaseCondition(object):
    def __init__(self, name, operator, value=None):
        op = operator if value else '='
        true_value = value if value else operator
        self._name = name
        self._operator = op
        self._value = true_value

    def generate(self) -> str:
        raise Exception("Condition not implemented")


class OrCondition(BaseCondition):

    def __init__(self, name, operator, value=None):
        super(self.__class__, self).__init__(name, operator, value)

    def generate(self) -> str:
        return "OR{}{}{}".format(self._name, self._operator, self._value)


class QueryCondition(BaseCondition):

    def __init__(self, name, operator, value=None):
        super(self.__class__, self).__init__(name, operator, value)
        self.__sub_query = []

    def add_or_condition(self, name, operator, value=None) -> OrCondition:
        sub_query = OrCondition(name, operator, value)
        self.__sub_query.append(sub_query)
        return sub_query

    def generate(self) -> str:
        query = "{}{}{}".format(self._name, self._operator, self._value)
        for sub_query in self.__sub_query:
            query = '^'.join((query, sub_query.generate()))
        return query


class Query(object):
    def __init__(self, table=None):
        self._table = table
        self.__sub_query = []
        self.__conditions = []

    def add_active_query(self) -> QueryCondition:
        return self.add_query('active', 'true')

    def add_query(self, name, operator, value=None) -> QueryCondition:
        qc = QueryCondition(name, operator, value)
        self._add_query_condition(qc)
        return qc

    def add_join_query(self, join_table, primary_field=None, join_table_field=None) -> 'JoinQuery':
        assert self._table != None, "Cannot execute join query as Query object was not instantiated with a table name"
        join_query = JoinQuery(self._table, join_table, primary_field, join_table_field)
        self.__sub_query.append(join_query)
        return join_query

    def add_rl_query(self, related_table, related_field, operator_condition, stop_at_relationship):
        rl_query = RLQuery(self._table, related_table, related_field, operator_condition, stop_at_relationship)
        self.__sub_query.append(rl_query)
        return rl_query

    def _add_query_condition(self, qc):
        assert isinstance(qc, QueryCondition)
        self.__conditions.append(qc)

    def add_null_query(self, field) -> QueryCondition:
        return self.add_query(field, '', 'ISEMPTY')

    def add_not_null_query(self, field) -> QueryCondition:
        return self.add_query(field, '', 'ISNOTEMPTY')

    def generate_query(self, encoded_query=None, order_by=None) -> str:
        query = '^'.join([c.generate() for c in self.__conditions])
        # Then sub queries
        for sub_query in self.__sub_query:
            if query == '':
                return sub_query.generate_query()
            query = '^'.join((query, sub_query.generate_query()))
        if encoded_query:
            query = '^'.join(filter(None, (query, encoded_query)))
        if order_by:
            query = '^'.join((query, order_by))
        # dont start with ^
        if query.startswith('^'):
            query = query[1:]
        return query


class JoinQuery(Query):
    def __init__(self, table, join_table, primary_field=None, join_table_field=None):
        super(self.__class__, self).__init__(table)
        self._join_table = join_table
        self._primary_field = primary_field
        self._join_table_field = join_table_field

    def generate_query(self, encoded_query=None, order_by=None) -> str:
        query = super(self.__class__, self).generate_query(encoded_query, order_by)
        primary = self._primary_field if self._primary_field else "sys_id"
        secondary = self._join_table_field if self._join_table_field else "sys_id"
        res = "JOIN{table}.{primary}={j_table}.{secondary}".format(
            table=self._table,
            primary=primary,
            j_table=self._join_table,
            secondary=secondary
        )
        # The `!` is required even if empty
        res = "{}!{}".format(res, query)
        return res


class RLQuery(Query):

    def __init__(self, table, related_table, related_field, operator_condition, stop_at_relationship):
        super(self.__class__, self).__init__(table)
        self._related_table = related_table
        self._related_field = related_field
        self.operator_condition = operator_condition
        self.stop_at_relationship = stop_at_relationship

    def generate_query(self, encoded_query=None, order_by=None) -> str:
        query = super(self.__class__, self).generate_query(encoded_query, order_by)
        identifier = "{}.{}".format(self._related_table, self._related_field)
        stop_condition = ",m2m" if self.stop_at_relationship else ""
        query = "^{}".format(query) if query else ""
        return "RLQUERY{},{}{}{}^ENDRLQUERY".format(identifier, self.operator_condition, stop_condition, query)
