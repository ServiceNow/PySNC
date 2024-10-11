from unittest import TestCase

from pysnc import ServiceNowClient, exceptions
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
        self.assertEqual(enc_query, 'name=alm_asset^ORname=bsm_chart^ORDERBYsys_id')
        client.session.close()

    def test_get_query_two(self):
        client = ServiceNowClient(self.c.server, self.c.credentials)
        gr = client.GlideRecord('sys_user')
        gr.get('6816f79cc0a8016401c5a33be04be441')
        enc_query = gr.get_encoded_query()
        self.assertEqual(enc_query, 'ORDERBYsys_id') # always have default orderby
        client.session.close()

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
        self.assertEqual(query, "active=true^test=what^ORDERBYsys_id")

        gr = client.GlideRecord('sys_user')
        gr.add_encoded_query('test=what')
        gr.add_query('active','true')

        query = gr.get_encoded_query()
        self.assertEqual(query, "active=true^test=what^ORDERBYsys_id")
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

    def test_import(self):
        from pysnc.query import Query
        from pysnc.query import QueryCondition
        from pysnc.query import BaseCondition
        class Junk(BaseCondition):
            pass
        j = Junk('name', 'operator')

    def test_code_query_one(self):
        from pysnc.query import Query
        client = ServiceNowClient(self.c.server, self.c.credentials)
        gr = client.GlideRecord('sys_user')
        q = Query()
        q.add_query('sys_id', '6816f79cc0a8016401c5a33be04be441')
        q.add_query('second', 'asdf')
        self.assertEqual(q.generate_query(), 'sys_id=6816f79cc0a8016401c5a33be04be441^second=asdf')
        self.assertEqual(gr.get_encoded_query(), 'ORDERBYsys_id')
        gr.query(q)
        self.assertEqual(len(gr), 1)
        self.assertEqual(gr.get_encoded_query(), 'ORDERBYsys_id')
        gr.add_encoded_query(q.generate_query())
        self.assertEqual(gr.get_encoded_query(), 'sys_id=6816f79cc0a8016401c5a33be04be441^second=asdf^ORDERBYsys_id')
        gr.query()
        self.assertEqual(len(gr), 1)

    def test_extra_long_query(self):
        client = ServiceNowClient(self.c.server, self.c.credentials)

        true_id = '6816f79cc0a8016401c5a33be04be441'
        gr = client.GlideRecord('sys_user')
        self.assertTrue(gr.get(true_id), 'failed to get true_id')

        # make an extra long query...
        gr = client.GlideRecord('sys_user')
        for _ in range(2300):
            # designed to be 10 chars long including ^
            gr.add_query('AAAA', 'BBBB')  # 'AAAA=BBBB^'
        gr.add_query('sys_id', true_id) # i want this at the end of the query just to be sure
        self.assertGreater(len(gr.get_encoded_query()), 23000)
        gr.query()  # would throw normally
        self.assertEqual(len(gr), 1)
        self.assertTrue(gr.next())
        self.assertEqual(gr.sys_id, true_id)

    def test_disable_display_values(self):
        client = ServiceNowClient(self.c.server, self.c.credentials)
        gr = client.GlideRecord('sys_user')
        gr.display_value = False
        gr.limit = 1
        gr.query()
        self.assertTrue(gr.next())
        #print(gr.serialize(display_value='all'))
        self.assertFalse(gr.sys_updated_on.nil())
        ele = gr.sys_updated_on
        print(repr(ele))
        self.assertEqual(ele.get_value(), ele.get_display_value(), 'expected timestamps to equal')

        gr = client.GlideRecord('sys_user')
        gr.display_value = True
        gr.limit = 1
        gr.query()
        gr.next()
        self.assertNotEqual(ele.get_value(), gr.get_value('sys_updated_on'))
        
    def test_nonjson_error(self):
        client = ServiceNowClient(self.c.server, self.c.credentials)

        super_long_non_existant_name = "A" * 23000
        gr = client.GlideRecord(super_long_non_existant_name)
        self.assertRaisesRegex(exceptions.RequestException, r'^<!DOCTYPE html>.*', lambda: gr.get('doesntmatter'))

    def test_changes(self):
        client = ServiceNowClient(self.c.server, self.c.credentials)
        gr = client.GlideRecord('sys_user')
        gr.limit = 2
        gr.query()
        self.assertTrue(gr.next())
        self.assertFalse(gr.changes())
        gr.set_value('user_name', gr.user_name)
        self.assertFalse(gr.changes())
        gr.user_name = gr.user_name
        self.assertFalse(gr.changes())
        gr.user_name = 'some new name'
        self.assertTrue(gr.changes())
        # issue #114, multiple changes
        gr.set_value('state', gr.state) # same state
        self.assertTrue(gr.changes())
        gr.set_value('state', 300)
        gr.set_value('work_notes', 'unittesting')
        self.assertTrue(gr.changes())

        gr.next()
        self.assertFalse(gr.changes())
        gr.state = 311
        gr.work_notes = 'unittest'
        self.assertTrue(gr.changes())

