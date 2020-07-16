from warnings import warn

class Query(object):
    def __init__(self, table):
        self._table = table
        self.__sub_query = []
        self.__conditions = []

    def add_active_query(self):
        self.add_query('active', 'true')

    def add_query(self, name, operator, value=None):
        qc = QueryCondition(name, operator, value)
        self._add_query_condition(qc)
        return qc

    def add_join_query(self, join_table, primary_field=None, join_table_field=None):
        join_query = JoinQuery(self._table, join_table, primary_field, join_table_field)
        self.__sub_query.append(join_query)
        return join_query

    def _add_query_condition(self, qc):
        assert isinstance(qc, QueryCondition)
        self.__conditions.append(qc)

    def add_null_query(self, field):
        self.add_query(field, '', 'ISEMPTY')

    def add_not_null_query(self, field):
        self.add_query(field, '', 'ISNOTEMPTY')

    def generate_query(self, encoded_query=None, order_by=None):
        query = '^'.join([c.generate() for c in self.__conditions])
        # Then sub queries
        for sub_query in self.__sub_query:
            if query == '':
                return sub_query.generate_query()
            query = '^'.join((query, sub_query.generate_query()))
        if encoded_query:
            query = '^'.join((query, encoded_query))
        if order_by:
            query = '^'.join((query, order_by))
        return query


class JoinQuery(Query):
    def __init__(self, table, join_table, primary_field=None, join_table_field=None):
        super(self.__class__, self).__init__(table)
        self._join_table = join_table
        self._primary_field = primary_field
        self._join_table_field = join_table_field

    def generate_query(self):
        query = super(self.__class__, self).generate_query()
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


class BaseCondition(object):
    def __init__(self, name, operator, value=None):
        op = operator if value else '='
        true_value = value if value else operator
        self._name = name
        self._operator = op
        self._value = true_value

    def generate(self):
        raise Exception("Condition not implemented")


class OrCondition(BaseCondition):

    def __init__(self, name, operator, value=None):
        super(self.__class__, self).__init__(name, operator, value)

    def generate(self):
        return "OR{}{}{}".format(self._name, self._operator, self._value)


class QueryCondition(BaseCondition):

    def __init__(self, name, operator, value=None):
        super(self.__class__, self).__init__(name, operator, value)
        self.__sub_query = []

    def add_or_condition(self, name, operator, value=None):
        sub_query = OrCondition(name, operator, value)
        self.__sub_query.append(sub_query)
        return sub_query

    def add_or_query(self, name, operator, value=None):
        warn('add_or_query is deprecated, use add_or_condition instead')
        self.add_or_condition(name, operator, value)

    def generate(self):
        query = "{}{}{}".format(self._name, self._operator, self._value)
        for sub_query in self.__sub_query:
            query = '^'.join((query, sub_query.generate()))
        return query
