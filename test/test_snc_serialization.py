from unittest import TestCase

from pysnc import ServiceNowClient
from constants import Constants
from pprint import pprint

class TestSerialization(TestCase):
    c = Constants()

    def test_pandas_smart(self):
        client = ServiceNowClient(self.c.server, self.c.credentials)
        gr = client.GlideRecord('problem')
        gr.fields = 'sys_id,short_description,state'

        gr.limit = 4
        gr.query()

        print(gr.serialize_all(display_value='both'))

        data = gr.to_pandas()
        self.assertIsInstance(data, dict)
        self.assertTrue('sys_id' in data)
        self.assertTrue('short_description' in data)
        self.assertTrue('state__value' in data)
        self.assertTrue('state__display' in data)
        self.assertEqual(len(data['sys_id']), 4)
        self.assertEqual(len(data['short_description']), 4)
        self.assertEqual(len(data['state__value']), 4)
        self.assertEqual(len(data['state__display']), 4)

    def test_pandas_both(self):
        client = ServiceNowClient(self.c.server, self.c.credentials)
        gr = client.GlideRecord('problem')
        gr.fields = 'sys_id,short_description,state'

        gr.limit = 4
        gr.query()

        print(gr.serialize_all(display_value='both'))

        data = gr.to_pandas(mode='both')
        print(data)
        self.assertIsInstance(data, dict)
        self.assertTrue('sys_id__value' in data)
        self.assertTrue('short_description__display' in data)
        self.assertTrue('state__value' in data)
        self.assertTrue('state__display' in data)
        self.assertEqual(len(data['sys_id__value']), 4)
        self.assertEqual(len(data['short_description__display']), 4)
        self.assertEqual(len(data['state__value']), 4)
        self.assertEqual(len(data['state__display']), 4)

    def test_pandas_value(self):
        client = ServiceNowClient(self.c.server, self.c.credentials)
        gr = client.GlideRecord('problem')
        gr.fields = 'sys_id,short_description,state'

        gr.limit = 4
        gr.query()

        print(gr.serialize_all(display_value='both'))

        data = gr.to_pandas(mode='value')
        print(data)
        self.assertIsInstance(data, dict)
        self.assertTrue('sys_id' in data)
        self.assertTrue('short_description' in data)
        self.assertTrue('state' in data)
        self.assertFalse('state__value' in data)
        self.assertEqual(len(data['sys_id']), 4)

    def test_pandas_order_cols(self):
        client = ServiceNowClient(self.c.server, self.c.credentials)
        gr = client.GlideRecord('problem')
        gr.fields = 'sys_id,short_description,state'

        gr.limit = 4
        gr.query()

        print(gr.serialize_all(display_value='both'))

        data = gr.to_pandas()
        print(data)
        self.assertEquals(list(data.keys()), ['sys_id', 'short_description', 'state__value', 'state__display'])
        data = gr.to_pandas(mode='display')
        print(data)
        self.assertEquals(list(data.keys()), ['sys_id', 'short_description', 'state'])
        data = gr.to_pandas(columns=['jack', 'jill', 'hill'], mode='display')
        print(data)
        self.assertEquals(list(data.keys()), ['jack', 'jill', 'hill'])


    def test_serialize_all_batch(self):
        client = ServiceNowClient(self.c.server, self.c.credentials)
        gr = client.GlideRecord('problem')
        gr.batch_size = 3
        gr.limit = 9
        gr.query()

        records = gr.serialize_all()
        self.assertEquals(len(records), 9)

    def test_serialize_noncurrent(self):
        client = ServiceNowClient(self.c.server, self.c.credentials)
        gr = client.GlideRecord('problem')
        gr.fields = 'sys_id,short_description,state'
        gr.limit = 4
        gr.query()
        self.assertIsNone(gr.serialize())
        gr.next()
        self.assertIsNotNone(gr.serialize())

    def test_serialize_changes(self):
        client = ServiceNowClient(self.c.server, self.c.credentials)
        gr = client.GlideRecord('problem')
        gr.fields = 'sys_id,short_description,state'
        gr.limit = 4
        gr.query()
        gr.next()
        data = gr.serialize()
        self.assertIsNotNone(data)
        self.assertEquals(list(data.keys()), ['sys_id', 'short_description', 'state'])
        self.assertEquals(list(gr.serialize(changes_only=True).keys()), [])
        gr.short_description = 'new'
        self.assertEquals(list(gr.serialize(changes_only=True).keys()), ['short_description'])

    def test_serialize(self):
        client = ServiceNowClient(self.c.server, self.c.credentials)
        gr = client.GlideRecord('some_table')
        gr.initialize()
        gr.strfield = 'my string'
        gr.set_display_value('strfield', 'my string display value')
        gr.intfield = 5
        data = gr.serialize()
        self.assertIsNotNone(data)
        self.assertEquals(data, {'intfield': 5, 'strfield': 'my string'})

    def test_serialize_display(self):
        client = ServiceNowClient(self.c.server, self.c.credentials)
        gr = client.GlideRecord('some_table')
        gr.initialize()
        gr.strfield = 'my string'
        gr.set_display_value('strfield', 'my string display value')
        gr.intfield = 5
        data = gr.serialize(display_value=True)
        self.assertIsNotNone(data)
        self.assertEquals(gr.get_value('strfield'), 'my string')
        self.assertEquals(gr.get_display_value('strfield'), 'my string display value')
        self.assertEquals(gr.serialize(), {'intfield': 5, 'strfield': 'my string'})
        self.assertEquals(data, {'intfield': 5, 'strfield': 'my string display value'})

    def test_str(self):
        client = ServiceNowClient(self.c.server, self.c.credentials)
        gr = client.GlideRecord('some_table')
        gr.initialize()
        gr.strfield = 'my string'
        gr.set_display_value('strfield', 'my string display value')
        gr.intfield = 5
        data = str(gr)
        self.assertIsNotNone(data)
        self.assertEquals(data, "some_table({'strfield': 'my string', 'intfield': 5})")



