from unittest import TestCase

from pysnc import ServiceNowClient, exceptions
from pysnc.aggregate import GlideAggregate, AggregateType
from .constants import Constants


class TestAggregate(TestCase):
    c = Constants()

    def setUp(self):
        self.client = ServiceNowClient(self.c.server, self.c.credentials)

    def tearDown(self):
        self.client.session.close()
        self.client = None

    def test_factory_returns_aggregate(self):
        ga = self.client.GlideAggregate('sys_user')
        self.assertIsInstance(ga, GlideAggregate)
        self.assertEqual(ga.table, 'sys_user')

    def test_ungrouped_count(self):
        ga = self.client.GlideAggregate('sys_user')
        ga.add_aggregate(AggregateType.COUNT)
        ga.query()
        self.assertEqual(ga.get_row_count(), 1)
        self.assertTrue(ga.has_next())
        self.assertTrue(ga.next())
        self.assertFalse(ga.has_next())
        count = ga.get_aggregate('COUNT')
        self.assertIsNotNone(count)
        self.assertGreater(int(count), 0)
        self.assertFalse(ga.next())

    def test_grouped_count(self):
        # active is an out-of-box field present on every instance.
        ga = self.client.GlideAggregate('sys_user')
        ga.add_aggregate(AggregateType.COUNT)
        ga.group_by('active')
        ga.query()
        self.assertGreaterEqual(ga.get_row_count(), 1)
        total = 0
        for row in ga:
            self.assertIs(row, ga)
            self.assertIsNotNone(row.get_value('active'))
            total += int(row.get_aggregate('COUNT'))
        self.assertGreater(total, 0)

    def test_nested_aggregates(self):
        # alm_asset.cost exercises the nested SUM/AVG/MIN/MAX response shape.
        # Skip cleanly if the instance has no asset cost data.
        ga = self.client.GlideAggregate('alm_asset')
        ga.add_aggregate(AggregateType.AVG, 'cost')
        ga.add_aggregate(AggregateType.MAX, 'cost')
        ga.add_aggregate(AggregateType.MIN, 'cost')
        ga.add_aggregate(AggregateType.SUM, 'cost')
        ga.query()
        self.assertTrue(ga.next())
        avg = ga.get_aggregate('AVG', 'cost')
        if avg is None:
            self.skipTest('instance has no alm_asset cost data')
        mx = ga.get_aggregate('MAX', 'cost')
        mn = ga.get_aggregate('MIN', 'cost')
        sm = ga.get_aggregate('SUM', 'cost')
        for v in (mx, mn, sm):
            self.assertIsNotNone(v)
        self.assertGreaterEqual(float(mx), float(mn))
        self.assertGreaterEqual(float(sm), float(mx))

    def test_display_value(self):
        # notification is an out-of-box choice field whose display label
        # ("Enable"/"Disable") differs from its raw value ("2"/"1").
        ga = self.client.GlideAggregate('sys_user')
        ga.add_aggregate(AggregateType.COUNT)
        ga.group_by('notification')
        ga.set_display_value(True)
        ga.query()
        saw_diff = False
        rows = 0
        for row in ga:
            rows += 1
            raw = row.get_value('notification')
            disp = row.get_display_value('notification')
            self.assertIsNotNone(raw)
            self.assertIsNotNone(disp)
            if raw != disp:
                saw_diff = True
        self.assertGreater(rows, 0)
        if not saw_diff:
            self.skipTest('instance data has no differing display values for notification')

    def test_having(self):
        ga = self.client.GlideAggregate('alm_asset')
        ga.add_aggregate(AggregateType.COUNT)
        ga.group_by('install_status')
        ga.add_having('COUNT', 'sys_id', '>', 50)
        ga.query()
        if ga.get_row_count() == 0:
            self.skipTest('instance has no alm_asset groups exceeding the HAVING threshold')
        for row in ga:
            self.assertGreater(int(row.get_aggregate('COUNT')), 50)

    def test_order_by_aggregate(self):
        ga = self.client.GlideAggregate('sys_user')
        ga.add_aggregate(AggregateType.COUNT)
        ga.group_by('active')
        ga.order_by_aggregate('COUNT')
        ga.query()
        counts = [int(row.get_aggregate('COUNT')) for row in ga]
        self.assertEqual(counts, sorted(counts))

    def test_order_by_and_desc(self):
        ga = self.client.GlideAggregate('sys_user')
        ga.add_aggregate(AggregateType.COUNT)
        ga.group_by('active')
        ga.order_by('active')
        ga.query()
        asc = [row.get_value('active') for row in ga]
        self.assertEqual(asc, sorted(asc))

        ga = self.client.GlideAggregate('sys_user')
        ga.add_aggregate(AggregateType.COUNT)
        ga.group_by('active')
        ga.order_by_desc('active')
        ga.query()
        desc = [row.get_value('active') for row in ga]
        self.assertEqual(desc, sorted(desc, reverse=True))

    def test_encoded_query(self):
        ga = self.client.GlideAggregate('sys_user')
        ga.add_encoded_query('active=true')
        self.assertEqual(ga.get_encoded_query(), 'active=true')
        ga.add_aggregate(AggregateType.COUNT)
        ga.query()
        ga.next()
        self.assertGreater(int(ga.get_aggregate('COUNT')), 0)

    def test_encoded_query_filter(self):
        ga = self.client.GlideAggregate('sys_user')
        ga.add_aggregate(AggregateType.COUNT)
        ga.add_active_query()
        ga.query()
        self.assertTrue(ga.next())
        active_count = int(ga.get_aggregate('COUNT'))

        ga2 = self.client.GlideAggregate('sys_user')
        ga2.add_aggregate(AggregateType.COUNT)
        ga2.query()
        ga2.next()
        total_count = int(ga2.get_aggregate('COUNT'))

        self.assertLessEqual(active_count, total_count)

    def test_bad_table_raises(self):
        ga = self.client.GlideAggregate('this_table_does_not_exist_zzz')
        ga.add_aggregate(AggregateType.COUNT)
        with self.assertRaises(exceptions.RequestException):
            ga.query()
