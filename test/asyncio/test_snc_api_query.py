# tests/asyncio/test_async_record_query.py
from unittest import IsolatedAsyncioTestCase

from pysnc.asyncio import AsyncServiceNowClient
from pysnc import exceptions
from ..constants import Constants


class TestAsyncRecordQuery(IsolatedAsyncioTestCase):
    """
    TODO: active query
    """
    c = Constants()

    async def test_batching(self):
        client = AsyncServiceNowClient(self.c.server, self.c.credentials)
        try:
            gr = await client.GlideRecord('syslog')
            gr.fields = ['sys_id']  # limit response size
            await gr.query()
            gr.limit = 1100  # set after first page to mimic original behavior
            count = 0
            while await gr.next():
                self.assertFalse(gr.is_new_record())
                count += 1
            self.assertGreater(count, 600)
        finally:
            await client.session.aclose()

    async def test_query_obj(self):
        client = AsyncServiceNowClient(self.c.server, self.c.credentials)
        try:
            gr = await client.GlideRecord('sys_db_object')
            qobj = gr.add_query('name', 'alm_asset')
            self.assertIsNotNone(qobj)
        finally:
            await client.session.aclose()

    async def test_or_query(self):
        client = AsyncServiceNowClient(self.c.server, self.c.credentials)
        try:
            gr = await client.GlideRecord('sys_db_object')
            o = gr.add_query('name', 'alm_asset')
            o.add_or_condition('name', 'bsm_chart')
            await gr.query()
            self.assertEqual(gr.get_row_count(), 2)
        finally:
            await client.session.aclose()

    async def test_get_query(self):
        client = AsyncServiceNowClient(self.c.server, self.c.credentials)
        try:
            gr = await client.GlideRecord('sys_db_object')
            o = gr.add_query('name', 'alm_asset')
            o.add_or_condition('name', 'bsm_chart')
            enc_query = gr.get_encoded_query()
            self.assertEqual(enc_query, 'name=alm_asset^ORname=bsm_chart^ORDERBYsys_id')
        finally:
            await client.session.aclose()

    async def test_get_query_two(self):
        client = AsyncServiceNowClient(self.c.server, self.c.credentials)
        try:
            gr = await client.GlideRecord('sys_user')
            await gr.get('6816f79cc0a8016401c5a33be04be441')
            enc_query = gr.get_encoded_query()
            self.assertEqual(enc_query, 'ORDERBYsys_id')  # always have default orderby
        finally:
            await client.session.aclose()

    async def test_null_query(self):
        client = AsyncServiceNowClient(self.c.server, self.c.credentials)
        try:
            gr_first = await client.GlideRecord('sys_user')
            gr_first.fields = 'sys_id'
            await gr_first.query()

            gr = await client.GlideRecord('sys_user')
            gr.add_null_query('name')
            await gr.query()
            self.assertNotEqual(gr.get_row_count(), gr_first.get_row_count())
        finally:
            await client.session.aclose()

    async def test_len(self):
        client = AsyncServiceNowClient(self.c.server, self.c.credentials)
        try:
            gr_first = await client.GlideRecord('sys_user')
            gr_first.fields = 'sys_id'
            await gr_first.query()

            gr = await client.GlideRecord('sys_user')
            gr.add_null_query('name')
            await gr.query()
            self.assertNotEqual(len(gr), len(gr_first))
        finally:
            await client.session.aclose()

    async def test_len_nonzero(self):
        client = AsyncServiceNowClient(self.c.server, self.c.credentials)
        try:
            gr = await client.GlideRecord('sys_user')
            gr.add_not_null_query('mobile_phone')
            await gr.query()
            self.assertLess(len(gr), 20)
        finally:
            await client.session.aclose()

    async def test_not_null_query(self):
        client = AsyncServiceNowClient(self.c.server, self.c.credentials)
        try:
            gr = await client.GlideRecord('sys_user')
            gr.add_not_null_query('mobile_phone')
            await gr.query()
            self.assertLess(gr.get_row_count(), 20)
        finally:
            await client.session.aclose()

    async def test_double_query(self):
        client = AsyncServiceNowClient(self.c.server, self.c.credentials)
        try:
            gr = await client.GlideRecord('sys_user')
            gr.add_query('active', 'true')
            gr.add_encoded_query('test=what')
            query = gr.get_encoded_query()
            self.assertEqual(query, "active=true^test=what^ORDERBYsys_id")

            gr = await client.GlideRecord('sys_user')
            gr.add_encoded_query('test=what')
            gr.add_query('active', 'true')
            query = gr.get_encoded_query()
            self.assertEqual(query, "active=true^test=what^ORDERBYsys_id")
        finally:
            await client.session.aclose()

    async def test_get_true(self):
        client = AsyncServiceNowClient(self.c.server, self.c.credentials)
        try:
            gr = await client.GlideRecord('sys_user')
            self.assertTrue(await gr.get('6816f79cc0a8016401c5a33be04be441'))
        finally:
            await client.session.aclose()

    async def test_get_field_true(self):
        client = AsyncServiceNowClient(self.c.server, self.c.credentials)
        try:
            gr = await client.GlideRecord('sys_user')
            self.assertTrue(await gr.get('sys_id', '6816f79cc0a8016401c5a33be04be441'))
        finally:
            await client.session.aclose()

    async def test_get_false(self):
        client = AsyncServiceNowClient(self.c.server, self.c.credentials)
        try:
            gr = await client.GlideRecord('sys_user')
            self.assertFalse(await gr.get('bunk'))
        finally:
            await client.session.aclose()

    async def test_get_field_false(self):
        client = AsyncServiceNowClient(self.c.server, self.c.credentials)
        try:
            gr = await client.GlideRecord('sys_user')
            self.assertFalse(await gr.get('sys_id', 'bunk'))
        finally:
            await client.session.aclose()

    async def test_no_result_query(self):
        client = AsyncServiceNowClient(self.c.server, self.c.credentials)
        try:
            gr = await client.GlideRecord('sys_user')
            gr.add_query('sys_id', 'bunk')
            await gr.query()
            self.assertFalse(gr.has_next())

            # Ensure we don't iterate any items
            iterated = False
            while await gr.next():
                iterated = True
            self.assertFalse(iterated)
        finally:
            await client.session.aclose()

    async def test_get_field_access_direct(self):
        client = AsyncServiceNowClient(self.c.server, self.c.credentials)
        try:
            gr = await client.GlideRecord('sys_user')
            self.assertTrue(await gr.get('6816f79cc0a8016401c5a33be04be441'))
            self.assertEqual(gr.user_name, 'admin')
        finally:
            await client.session.aclose()

    async def test_get_field_access(self):
        client = AsyncServiceNowClient(self.c.server, self.c.credentials)
        try:
            gr = await client.GlideRecord('sys_user')
            self.assertTrue(await gr.get('sys_id', '6816f79cc0a8016401c5a33be04be441'))
            self.assertEqual(gr.user_name, 'admin')
        finally:
            await client.session.aclose()

    async def test_import(self):
        from pysnc.query import Query
        from pysnc.query import QueryCondition
        from pysnc.query import BaseCondition

        class Junk(BaseCondition):
            pass

        _ = Junk('name', 'operator')  # exercise basic subclassing

    async def test_code_query_one(self):
        from pysnc.query import Query
        client = AsyncServiceNowClient(self.c.server, self.c.credentials)
        try:
            gr = await client.GlideRecord('sys_user')
            q = Query()
            q.add_query('sys_id', '6816f79cc0a8016401c5a33be04be441')
            q.add_query('second', 'asdf')
            self.assertEqual(q.generate_query(), 'sys_id=6816f79cc0a8016401c5a33be04be441^second=asdf')
            self.assertEqual(gr.get_encoded_query(), 'ORDERBYsys_id')
            await gr.query(q)
            self.assertEqual(len(gr), 1)
            self.assertEqual(gr.get_encoded_query(), 'ORDERBYsys_id')
            gr.add_encoded_query(q.generate_query())
            self.assertEqual(
                gr.get_encoded_query(),
                'sys_id=6816f79cc0a8016401c5a33be04be441^second=asdf^ORDERBYsys_id'
            )
            await gr.query()
            self.assertEqual(len(gr), 1)
        finally:
            await client.session.aclose()

    async def test_extra_long_query(self):
        client = AsyncServiceNowClient(self.c.server, self.c.credentials)
        try:
            true_id = '6816f79cc0a8016401c5a33be04be441'
            gr = await client.GlideRecord('sys_user')
            self.assertTrue(await gr.get(true_id), 'failed to get true_id')

            # make an extra long query...
            gr = await client.GlideRecord('sys_user')
            for _ in range(2300):
                # designed to be ~10 chars long including ^
                gr.add_query('AAAA', 'BBBB')  # 'AAAA=BBBB^'
            gr.add_query('sys_id', true_id)  # want this at the end
            self.assertGreater(len(gr.get_encoded_query()), 23000)
            await gr.query()  # would throw normally; should batch under the hood
            self.assertEqual(len(gr), 1)
            self.assertTrue(await gr.next())
            self.assertEqual(gr.sys_id, true_id)
        finally:
            await client.session.aclose()

    async def test_disable_display_values(self):
        client = AsyncServiceNowClient(self.c.server, self.c.credentials)
        try:
            gr = await client.GlideRecord('sys_user')
            gr.display_value = False
            gr.limit = 1
            await gr.query()
            self.assertTrue(await gr.next())
            # print(gr.serialize(display_value='all'))
            self.assertFalse(gr.sys_updated_on.nil())
            ele = gr.sys_updated_on
            print(repr(ele))
            self.assertEqual(ele.get_value(), ele.get_display_value(), 'expected timestamps to equal')

            gr = await client.GlideRecord('sys_user')
            gr.display_value = True
            gr.limit = 1
            await gr.query()
            await gr.next()
            self.assertNotEqual(ele.get_value(), gr.get_value('sys_updated_on'))
        finally:
            await client.session.aclose()

    async def test_nonjson_error(self):
        client = AsyncServiceNowClient(self.c.server, self.c.credentials)
        try:
            super_long_non_existant_name = "A" * 23000
            gr = await client.GlideRecord(super_long_non_existant_name)
            with self.assertRaisesRegex(exceptions.RequestException, r'^<.*html>.*'):
                await gr.get('doesntmatter')
        finally:
            await client.session.aclose()

    async def test_changes(self):
        client = AsyncServiceNowClient(self.c.server, self.c.credentials)
        try:
            gr = await client.GlideRecord('sys_user')
            gr.limit = 1
            await gr.query()
            self.assertTrue(await gr.next())
            self.assertFalse(gr.changes())
            gr.user_name = 'new name'
            self.assertTrue(gr.changes())
        finally:
            await client.session.aclose()
