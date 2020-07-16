from unittest import TestCase

from pysnc import ServiceNowClient
from constants import Constants

class TestRecordFields(TestCase):
    c = Constants()

    def test_field_limit(self):
        client = ServiceNowClient(self.c.server, self.c.credentials)
        gr = client.GlideRecord('sys_user')
        gr.fields = 'sys_id,name'
        r = gr.get('6816f79cc0a8016401c5a33be04be441')

        print(gr.serialize())
        self.assertEquals(r, True)
        sobj = gr.serialize()
        self.assertTrue('sys_id' in sobj)
        self.assertFalse('sys_created_on' in sobj)

    def test_field_limit_query(self):
        client = ServiceNowClient(self.c.server, self.c.credentials)
        gr = client.GlideRecord('sys_user')
        gr.limit = 1
        gr.fields = 'sys_id,name'
        gr.query()
        gr.next()

        print(gr.serialize())
        sobj = gr.serialize()
        self.assertTrue('sys_id' in sobj)
        self.assertFalse('sys_created_on' in sobj)

    def test_field_bool(self):
        client = ServiceNowClient(self.c.server, self.c.credentials)
        gr = client.GlideRecord('sys_user')
        gr.fields = 'sys_id,active'
        gr.get('6816f79cc0a8016401c5a33be04be441')

        print(gr.serialize())

        self.assertEquals(gr.active, 'true')

    def test_field_access(self):
        client = ServiceNowClient(self.c.server, self.c.credentials)
        gr = client.GlideRecord('sys_user')
        gr.fields = 'sys_id,name'
        gr.get('6816f79cc0a8016401c5a33be04be441')

        print(gr.serialize())

        name = 'System Administrator'
        self.assertEquals(gr.name, name)
        self.assertEquals(gr.get_value('name'), name)
        self.assertEquals(gr.get_display_value('name'), name)

    def test_field_contains(self):
        client = ServiceNowClient(self.c.server, self.c.credentials)
        gr = client.GlideRecord('sys_user')
        gr.fields = 'sys_id,name'
        gr.get('6816f79cc0a8016401c5a33be04be441')
        print(gr.serialize())
        self.assertTrue('name' in gr)
        self.assertFalse('whatever' in gr)

    def test_field_set(self):
        client = ServiceNowClient(self.c.server, self.c.credentials)
        gr = client.GlideRecord('sys_user')
        gr.fields = 'sys_id,name'
        gr.get('6816f79cc0a8016401c5a33be04be441')
        print(gr.serialize())
        name = 'System Administrator'
        self.assertEquals(gr.name, name)
        gr.name = 'Whatever'
        self.assertEquals(gr.name, 'Whatever')
        gr.set_value('name', 'Test')
        self.assertEquals(gr.name, 'Test')
        self.assertEquals(gr.get_value('name'), 'Test')

    def test_field_set_init(self):
        client = ServiceNowClient(self.c.server, self.c.credentials)
        gr = client.GlideRecord('sys_user')
        gr.initialize()
        name = 'System Administrator'
        gr.name = name
        self.assertEquals(gr.name, name)
        gr.set_value('name', 'Test')
        self.assertEquals(gr.name, 'Test')
        self.assertEquals(gr.get_value('name'), 'Test')

    def test_fields(self):
        client = ServiceNowClient(self.c.server, self.c.credentials)
        gr = client.GlideRecord('sys_user')
        gr.fields = ['sys_id']
        gr.limit = 4
        gr.query()
        count = 0
        while gr.next():
            count = count + 1
            assert len(gr._current().keys()) == 1
        self.assertEquals(count, 4)

    def test_field_getter(self):
        client = ServiceNowClient(self.c.server, self.c.credentials)
        gr = client.GlideRecord('sys_user')
        gr.fields = ['sys_id']
        self.assertEquals(gr.fields, ['sys_id'])

    def test_field_getter_query(self):
        client = ServiceNowClient(self.c.server, self.c.credentials)
        gr = client.GlideRecord('sys_user')
        self.assertEquals(gr.fields, None)
        gr.limit = 1
        gr.query()
        self.assertEquals(gr.fields, None)
        gr.next()
        print(gr.fields)
        self.assertGreater(len(gr.fields), 10)

    def test_attrs(self):
        client = ServiceNowClient(self.c.server, self.c.credentials)
        gr = client.GlideRecord('sys_user')
        r = gr.get('6816f79cc0a8016401c5a33be04be441')
        self.assertEquals(r, True)
        self.assertEquals(gr.sys_id, '6816f79cc0a8016401c5a33be04be441')
        self.assertEquals(gr.get_value('sys_id'), '6816f79cc0a8016401c5a33be04be441')
        self.assertEquals(gr.get_display_value('user_password'), '********')

    def test_attrs_nil(self):
        client = ServiceNowClient(self.c.server, self.c.credentials)
        gr = client.GlideRecord('sys_user')
        r = gr.get('6816f79cc0a8016401c5a33be04be441')
        self.assertEquals(r, True)
        self.assertIsNotNone(gr.get_element('sys_id'))
        self.assertIsNone(gr.get_element('asdf'))
        self.assertEquals(gr.get_element('sys_id').nil(), False)
        gr.sys_id = ''
        self.assertEquals(gr.get_element('sys_id').nil(), True)

    def test_attrs_changes(self):
        client = ServiceNowClient(self.c.server, self.c.credentials)
        gr = client.GlideRecord('sys_user')
        r = gr.get('6816f79cc0a8016401c5a33be04be441')
        self.assertEquals(r, True)
        self.assertIsNotNone(gr.get_element('sys_id'))
        self.assertIsNone(gr.get_element('asdf'))
        self.assertEquals(gr.get_element('sys_id').changes(), False)
        gr.sys_id = '1234'
        self.assertEquals(gr.get_element('sys_id').changes(), True)

    def test_attrs_changes(self):
        client = ServiceNowClient(self.c.server, self.c.credentials)
        gr = client.GlideRecord('sys_user')
        gr.initialize()
        self.assertTrue(gr.is_new_record())
        self.assertIsNone(gr.get_element('sys_id'))
        gr.sys_id = 'zzzz'
        # i am not considering a state of nothing to something a change, merely the start of existence
        self.assertEquals(gr.get_element('sys_id').changes(), False)
        gr.sys_id = '1234'
        self.assertEquals(gr.get_element('sys_id').changes(), True)
