from unittest import TestCase

from pysnc import ServiceNowClient
from .constants import Constants
from pysnc.record import GlideElement

class TestRecordFields(TestCase):
    c = Constants()

    def setUp(self):
        self.client = ServiceNowClient(self.c.server, self.c.credentials)

    def tearDown(self):
        self.client.session.close()
        self.client = None

    def test_field_limit(self):
        gr = self.client.GlideRecord('sys_user')
        gr.fields = 'sys_id,name'
        r = gr.get('6816f79cc0a8016401c5a33be04be441')

        print(gr.serialize())
        self.assertEqual(r, True)
        sobj = gr.serialize()
        self.assertTrue('sys_id' in sobj)
        self.assertFalse('sys_created_on' in sobj)

    def test_field_limit_query(self):
        gr = self.client.GlideRecord('sys_user')
        gr.limit = 1
        gr.fields = 'sys_id,name'
        gr.query()
        gr.next()

        print(gr.serialize())
        sobj = gr.serialize()
        self.assertTrue('sys_id' in sobj)
        self.assertFalse('sys_created_on' in sobj)

    def test_field_bool(self):
        gr = self.client.GlideRecord('sys_user')
        gr.fields = 'sys_id,active'
        gr.get('6816f79cc0a8016401c5a33be04be441')

        print(gr.serialize())

        self.assertEqual(gr.active, 'true')

    def test_field_access(self):
        gr = self.client.GlideRecord('sys_user')
        gr.fields = 'sys_id,name'
        gr.get('6816f79cc0a8016401c5a33be04be441')

        print(gr.serialize())

        name = 'System Administrator'
        self.assertEqual(gr.name, name)
        self.assertEqual(gr.get_value('name'), name)
        self.assertEqual(gr.get_display_value('name'), name)

    def test_field_contains(self):
        gr = self.client.GlideRecord('sys_user')
        gr.fields = 'sys_id,name'
        gr.get('6816f79cc0a8016401c5a33be04be441')
        print(gr.serialize())
        self.assertTrue('name' in gr)
        self.assertFalse('whatever' in gr)

    def test_field_set(self):
        gr = self.client.GlideRecord('sys_user')
        gr.fields = 'sys_id,name'
        gr.get('6816f79cc0a8016401c5a33be04be441')
        print(gr.serialize())
        name = 'System Administrator'
        self.assertEqual(gr.name, name)
        gr.name = 'Whatever'
        self.assertEqual(gr.name, 'Whatever')
        gr.set_value('name', 'Test')
        self.assertEqual(gr.name, 'Test')
        self.assertEqual(gr.get_value('name'), 'Test')

    def test_field_set_init(self):
        gr = self.client.GlideRecord('sys_user')
        gr.initialize()
        name = 'System Administrator'
        gr.name = name
        self.assertEqual(gr.name, name)
        gr.set_value('name', 'Test')
        self.assertEqual(gr.name, 'Test')
        self.assertEqual(gr.get_value('name'), 'Test')

    def test_fields(self):
        gr = self.client.GlideRecord('sys_user')
        gr.fields = ['sys_id']
        gr.limit = 4
        gr.query()
        count = 0
        while gr.next():
            count = count + 1
            assert len(gr._current().keys()) == 1
        self.assertEqual(count, 4)

    def test_field_getter(self):
        gr = self.client.GlideRecord('sys_user')
        gr.fields = ['sys_id']
        self.assertEqual(gr.fields, ['sys_id'])

    def test_field_all(self):
        gr = self.client.GlideRecord('sys_user')
        self.assertIsNone(gr.fields)
        gr.query()
        self.assertIsNotNone(gr.fields)

    def test_field_getter_query(self):
        gr = self.client.GlideRecord('sys_user')
        self.assertEqual(gr.fields, None)
        gr.limit = 1
        gr.query()
        self.assertIsNotNone(gr.fields)
        self.assertGreater(len(gr.fields), 10)
        gr.next()
        print(gr.fields)
        self.assertGreater(len(gr.fields), 10)

    def test_boolean(self):
        gr = self.client.GlideRecord('sys_user')
        gr.fields = ['sys_id', 'active']
        gr.query()
        self.assertTrue(gr.next())
        # as a string, because that's the actual JSON response value
        self.assertEqual(gr.active, 'true')
        self.assertEqual(gr.get_value('active'), 'true')
        self.assertEqual(gr.get_display_value('active'), 'true')
        self.assertEqual(gr.get_element('active'), 'true')
        self.assertTrue(bool(gr.active))
        if not gr.active:
            assert 'should have been true'
        gr.active = 'false'
        print(repr(gr.active))
        self.assertFalse(bool(gr.active))
        if gr.active:
            assert 'should have been false'


    def test_attrs(self):
        gr = self.client.GlideRecord('sys_user')
        r = gr.get('6816f79cc0a8016401c5a33be04be441')
        self.assertEqual(r, True)
        self.assertEqual(gr.sys_id, '6816f79cc0a8016401c5a33be04be441')
        self.assertEqual(gr.get_value('sys_id'), '6816f79cc0a8016401c5a33be04be441')
        self.assertEqual(gr.get_display_value('user_password'), '********')

    def test_attrs_nil(self):
        gr = self.client.GlideRecord('sys_user')
        r = gr.get('6816f79cc0a8016401c5a33be04be441')
        self.assertEqual(r, True)
        self.assertIsNotNone(gr.get_element('sys_id'))
        self.assertIsNone(gr.get_element('asdf'))
        self.assertFalse(gr.get_element('sys_id').nil())
        self.assertFalse(gr.sys_id.nil())
        gr.sys_id = ''
        self.assertTrue(gr.get_element('sys_id').nil())
        self.assertTrue(gr.sys_id.nil())

    def test_attrs_changes(self):
        gr = self.client.GlideRecord('sys_user')
        r = gr.get('6816f79cc0a8016401c5a33be04be441')
        self.assertEqual(r, True)
        self.assertIsNotNone(gr.get_element('sys_id'))
        self.assertIsNone(gr.get_element('asdf'))
        self.assertEqual(gr.get_element('sys_id').changes(), False)
        gr.sys_id = '1234'
        self.assertEqual(gr.get_element('sys_id').changes(), True)

    def test_attrs_changes(self):
        gr = self.client.GlideRecord('sys_user')
        gr.initialize()
        self.assertTrue(gr.is_new_record())
        self.assertIsNone(gr.get_element('sys_id'))
        gr.sys_id = 'zzzz'
        # i am not considering a state of nothing to something a change, merely the start of existence
        self.assertEqual(gr.get_element('sys_id').changes(), False)
        gr.sys_id = '1234'
        self.assertEqual(gr.get_element('sys_id').changes(), True)

    def test_dotwalk_with_element(self):
        gr = self.client.GlideRecord('sys_user')
        gr.fields = 'sys_id,active,email,department,department.name,department.dept_head,department.dept_head.email'
        gr.get('6816f79cc0a8016401c5a33be04be441')
        print(gr.serialize(display_value='both'))

        self.assertEqual(gr.email, 'admin@example.com')

        self.assertEqual(gr.department, 'a581ab703710200044e0bfc8bcbe5de8')

        self.assertEqual(gr.department.name, 'Finance')

        self.assertEqual(gr.department.dept_head, '46c5bf6ca9fe1981010713e3ac7d3384')
        self.assertEqual(type(gr.department.dept_head), GlideElement)
        self.assertEqual(gr.department.dept_head.get_value(), '46c5bf6ca9fe1981010713e3ac7d3384')
        self.assertFalse(gr.department.dept_head.nil())

        self.assertEqual(gr.department.dept_head.email, 'natasha.ingram@example.com')
        self.assertEqual(type(gr.department.dept_head.email), GlideElement)

        self.assertRaisesRegex(AttributeError, r'.+has no attribute.+nor GlideElement.+', lambda: gr.department.description)

