from unittest import TestCase

from pysnc import ServiceNowClient
from constants import Constants

class TestRecordQuery(TestCase):
    """
    TODO: active query
    """
    c = Constants()


    def test_batching(self):
        client = ServiceNowClient(self.c.server, self.c.credentials)
        gr = client.GlideRecord('syslog')
        gr.fields = ['sys_id']  # not testing this, but just limit response size
        gr.query()
        gr.limit = 1100
        count = 0
        while gr.next():
            self.assertFalse(gr.is_new_record())
            count = count + 1
        self.assertGreater(count, 600)
        client.session.close()

    def test_query_obj(self):
        client = ServiceNowClient(self.c.server, self.c.credentials)
        gr = client.GlideRecord('sys_db_object')
        qobj = gr.add_query('name', 'alm_asset')
        self.assertIsNotNone(qobj)
        client.session.close()

    def test_or_query(self):
        client = ServiceNowClient(self.c.server, self.c.credentials)
        gr = client.GlideRecord('sys_db_object')
        o = gr.add_query('name', 'alm_asset')
        o.add_or_condition('name', 'bsm_chart')
        gr.query()
        self.assertEqual(gr.get_row_count(), 2)
        client.session.close()

    def test_get_query(self):
        client = ServiceNowClient(self.c.server, self.c.credentials)
        gr = client.GlideRecord('sys_db_object')
        o = gr.add_query('name', 'alm_asset')
        o.add_or_condition('name', 'bsm_chart')
        enc_query = gr.get_encoded_query()
        self.assertEqual(enc_query, 'name=alm_asset^ORname=bsm_chart')
        client.session.close()

    def test_get_query_two(self):
        client = ServiceNowClient(self.c.server, self.c.credentials)
        gr = client.GlideRecord('sys_user')
        gr.get('6816f79cc0a8016401c5a33be04be441')
        enc_query = gr.get_encoded_query()
        self.assertEqual(enc_query, '')
        client.session.close()

    def test_join_query(self):
        client = ServiceNowClient(self.c.server, self.c.credentials)
        gr = client.GlideRecord('sys_user')
        join_query = gr.add_join_query('sys_user_group', join_table_field='manager')
        join_query.add_query('active','true')
        self.assertEqual(gr.get_encoded_query(), 'JOINsys_user.sys_id=sys_user_group.manager!active=true')
        gr.query()
        self.assertGreater(gr.get_row_count(), 1)
        client.session.close()

    ''' need to validate join query actually works right...
    def test_join_query_2(self):
        client = ServiceNowClient(self.c.server, self.c.credentials)
        gr = client.GlideRecord('sys_user')
        join_query = gr.add_join_query('sys_user_has_role', join_table_field='user')
        join_query.add_query('role.name','admin')
        self.assertEqual(gr.get_encoded_query(), 'JOINsys_user.sys_id=sys_user_has_role.user!role.name=admin')
        gr.query()
        gr.next()
        print(gr.serialize())
        self.assertEqual(gr.get_row_count(), 2)
        '''

    def test_null_query(self):
        client = ServiceNowClient(self.c.server, self.c.credentials)
        gr_first = client.GlideRecord('sys_user')
        gr_first.fields = 'sys_id'
        gr_first.query()

        gr = client.GlideRecord('sys_user')
        gr.add_null_query('name')
        gr.query()
        self.assertNotEqual(gr.get_row_count(), gr_first.get_row_count())
        client.session.close()

    def test_len(self):
        client = ServiceNowClient(self.c.server, self.c.credentials)
        gr_first = client.GlideRecord('sys_user')
        gr_first.fields = 'sys_id'
        gr_first.query()
        gr = client.GlideRecord('sys_user')
        gr.add_null_query('name')
        gr.query()
        self.assertNotEqual(len(gr), len(gr_first))
        client.session.close()

    def test_len_nonzero(self):
        client = ServiceNowClient(self.c.server, self.c.credentials)
        gr = client.GlideRecord('sys_user')
        gr.add_not_null_query('mobile_phone')
        gr.query()
        self.assertLess(len(gr), 20)
        client.session.close()

    def test_not_null_query(self):
        client = ServiceNowClient(self.c.server, self.c.credentials)
        gr = client.GlideRecord('sys_user')
        gr.add_not_null_query('mobile_phone')
        gr.query()
        self.assertLess(gr.get_row_count(), 20)
        client.session.close()

    def test_double_query(self):
        client = ServiceNowClient(self.c.server, self.c.credentials)
        gr = client.GlideRecord('sys_user')
        gr.add_query('active','true')
        gr.add_encoded_query('test=what')

        query = gr.get_encoded_query()
        self.assertEqual(query, "active=true^test=what")

        gr = client.GlideRecord('sys_user')
        gr.add_encoded_query('test=what')
        gr.add_query('active','true')

        query = gr.get_encoded_query()
        self.assertEqual(query, "active=true^test=what")
        client.session.close()

    def test_get_true(self):
        client = ServiceNowClient(self.c.server, self.c.credentials)
        gr = client.GlideRecord('sys_user')
        self.assertTrue(gr.get('6816f79cc0a8016401c5a33be04be441'))
        client.session.close()

    def test_get_field_true(self):
        client = ServiceNowClient(self.c.server, self.c.credentials)
        gr = client.GlideRecord('sys_user')
        self.assertTrue(gr.get('sys_id', '6816f79cc0a8016401c5a33be04be441'))
        client.session.close()

    def test_get_false(self):
        client = ServiceNowClient(self.c.server, self.c.credentials)
        gr = client.GlideRecord('sys_user')
        self.assertFalse(gr.get('bunk'))
        client.session.close()

    def test_get_field_false(self):
        client = ServiceNowClient(self.c.server, self.c.credentials)
        gr = client.GlideRecord('sys_user')
        self.assertFalse(gr.get('sys_id', 'bunk'))
        client.session.close()

    def test_no_result_query(self):
        client = ServiceNowClient(self.c.server, self.c.credentials)
        gr = client.GlideRecord('sys_user')
        gr.add_query('sys_id', 'bunk')
        gr.query()
        self.assertFalse(gr.has_next())
        for e in gr:
            assert "Should not have iterated!"
        client.session.close()

    def test_get_field_access_direct(self):
        client = ServiceNowClient(self.c.server, self.c.credentials)
        gr = client.GlideRecord('sys_user')
        self.assertTrue(gr.get('6816f79cc0a8016401c5a33be04be441'))
        self.assertEqual(gr.user_name, 'admin')
        client.session.close()

    def test_get_field_access(self):
        client = ServiceNowClient(self.c.server, self.c.credentials)
        gr = client.GlideRecord('sys_user')
        self.assertTrue(gr.get('sys_id', '6816f79cc0a8016401c5a33be04be441'))
        self.assertEqual(gr.user_name, 'admin')
        client.session.close()
