# tests/asyncio/test_async_api_write.py
from unittest import IsolatedAsyncioTestCase

from pysnc.asyncio import AsyncServiceNowClient
from ..constants import Constants


class TestAsyncWrite(IsolatedAsyncioTestCase):
    c = Constants()

    async def test_crud(self):
        client = AsyncServiceNowClient(self.c.server, self.c.credentials)
        try:
            gr = await client.GlideRecord('problem')
            gr.initialize()
            gr.short_description = "Unit Test - Insert"
            gr.description = "Second Field"
            gr.bunk_field = "Bunk Field"
            res = await gr.insert()
            self.assertIsNotNone(res)
            # should have gotten the response back, ergo populated new fields
            self.assertIsNotNone(gr.opened_by)
            self.assertEqual(len(gr.opened_by), 32, 'expected opened_by to be a sys_id')
            self.assertNotEqual(gr.get_value('opened_by'), gr.get_display_value('opened_by'))
            first_user_display = gr.get_display_value('opened_by')

            # We have validated inserting works, now can we update.
            user = await client.GlideRecord('sys_user')
            self.assertTrue(await user.get('26fbff173b331300ad3cc9bb34efc4bd'))  # problem.admin
            self.assertNotEqual(user.sys_id, gr.get_value('opened_by'))

            # actually update
            gr2 = await client.GlideRecord('problem')
            self.assertTrue(await gr2.get(res))
            self.assertTrue(bool(gr2.active))
            gr2.short_description = "ABCDEFG0123"
            self.assertTrue(gr2.changes())
            self.assertEqual(gr2.get_value('short_description'), "ABCDEFG0123")
            gr2.assigned_to = user.sys_id
            self.assertIsNotNone(await gr2.update())

            # local record updated
            self.assertTrue(bool(gr2.active))
            self.assertEqual(gr2.short_description, 'ABCDEFG0123')
            self.assertEqual(gr2.assigned_to, user.sys_id)
            self.assertNotEqual(gr2.get_display_value('assigned_to'), first_user_display)
            self.assertEqual(gr2.get_display_value('assigned_to'), user.get_display_value('name'))

            # re-query
            gr3 = await client.GlideRecord('problem')
            await gr3.get(res)
            self.assertEqual(gr3.short_description, "ABCDEFG0123")
            self.assertEqual(gr3.get_display_value('assigned_to'), user.get_display_value('name'))

            gr4 = gr3.pop_record()
            gr4.short_description = 'ZZZ123'
            self.assertTrue(await gr4.update())

            gr4 = gr3.pop_record()
            gr4.short_description = 'ZZZ123'
            self.assertTrue(await gr4.update())

            gr4 = gr3.pop_record()
            gr4.short_description = 'ZZZ123'
            self.assertTrue(await gr4.update())

            self.assertTrue(await gr3.delete())

            # make sure it is deleted
            gr4 = await client.GlideRecord('problem')
            self.assertFalse(await gr4.get(res))
        finally:
            await client.session.aclose()

    async def test_insert(self):
        client = AsyncServiceNowClient(self.c.server, self.c.credentials)
        try:
            # I want to ensure the records sys_id is updated
            gr = await client.GlideRecord('problem')
            gr.initialize()
            gr.short_description = "Unit Test - Test insert id update"
            self.assertIsNone(gr.sys_id)
            res = await gr.insert()
            self.assertIsNotNone(res)
            self.assertIsNotNone(gr.sys_id)
            self.assertEqual(res, gr.sys_id)
            self.assertIsNotNone(gr.number)

            # make sure it exists
            gr2 = await client.GlideRecord('problem')
            self.assertTrue(await gr2.get(res))
            self.assertEqual(gr2.number, gr.number)

            await gr.delete()

            # make sure it is deleted
            gr4 = await client.GlideRecord('problem')
            self.assertFalse(await gr4.get(res))
        finally:
            await client.session.aclose()

    async def test_insert_custom_guid(self):
        client = AsyncServiceNowClient(self.c.server, self.c.credentials)
        try:
            customsysid = 'AAAABBBBCCCCDDDDEEEEFFFF00001111'
            # make sure this id doesn't exist, first
            gr = await client.GlideRecord('problem')
            if await gr.get(customsysid):
                await gr.delete()

            gr = await client.GlideRecord('problem')
            gr.initialize()
            gr.set_new_guid_value(customsysid)
            gr.short_description = "Unit Test - Test insert id update"
            res = await gr.insert()
            self.assertIsNotNone(res)
            self.assertIsNotNone(gr.sys_id)
            self.assertEqual(res, customsysid)

            # make sure it exists
            gr2 = await client.GlideRecord('problem')
            self.assertTrue(await gr2.get(customsysid))

            await gr.delete()

            # make sure it is deleted
            gr4 = await client.GlideRecord('problem')
            self.assertFalse(await gr4.get(res))
        finally:
            await client.session.aclose()

    async def test_object_setter(self):
        client = AsyncServiceNowClient(self.c.server, self.c.credentials)
        try:
            gr = await client.GlideRecord('problem')
            gr.initialize()
            gr.name = 'aaaa'
            self.assertEqual(gr.name, 'aaaa')
            gr.roles = [1, 2, 3]
            self.assertEqual(gr.roles, [1, 2, 3])
        finally:
            await client.session.aclose()

    async def test_object_secondary_field(self):
        client = AsyncServiceNowClient(self.c.server, self.c.credentials)
        try:
            gr = await client.GlideRecord('sys_user')
            gr.limit = 1
            await gr.query()
            self.assertTrue(await gr.next())
            gr.boom = 'aaaa'
            self.assertEqual(gr.boom, 'aaaa')
            gr.bye = [1, 2, 3]
            self.assertEqual(gr.bye, [1, 2, 3])
        finally:
            await client.session.aclose()

    async def test_multi_delete(self):
        client = AsyncServiceNowClient(self.c.server, self.c.credentials)
        try:
            gr = await client.GlideRecord('problem')
            gr.add_query('short_description', 'LIKE', 'BUNKZZ')
            await gr.delete_multiple()  # ensure none to start

            # insert five bunk records
            for i in range(5):
                ngr = await client.GlideRecord('problem')
                ngr.initialize()
                ngr.short_description = f"Unit Test - BUNKZZ Multi Delete {i}"
                self.assertTrue(await ngr.insert(), "Failed to insert a record")

            # now make sure they exist...
            gr = await client.GlideRecord('problem')
            gr.add_query('short_description', 'LIKE', 'BUNKZZ')
            await gr.query()
            self.assertEqual(len(gr), 5)

            # now multi delete...
            gr = await client.GlideRecord('problem')
            gr.add_query('short_description', 'LIKE', 'BUNKZZ')
            self.assertTrue(await gr.delete_multiple())

            # check again
            gr = await client.GlideRecord('problem')
            gr.add_query('short_description', 'LIKE', 'BUNKZZ')
            await gr.query()
            self.assertEqual(len(gr), 0)
        finally:
            await client.session.aclose()

    async def test_multi_update(self):
        client = AsyncServiceNowClient(self.c.server, self.c.credentials)
        try:
            gr = await client.GlideRecord('problem')
            gr.add_query('short_description', 'LIKE', 'BUNKZZ')
            await gr.query()
            await gr.delete_multiple()  # clear out
            await gr.query()
            self.assertEqual(len(gr), 0)

            total_count = 10
            # insert records
            for i in range(total_count):
                ngr = await client.GlideRecord('problem')
                ngr.initialize()
                ngr.short_description = f"Unit Test - BUNKZZ Multi Delete {i}"
                self.assertTrue(await ngr.insert(), "Failed to insert a record")

            # verify they exist
            gr = await client.GlideRecord('problem')
            gr.add_query('short_description', 'LIKE', 'BUNKZZ')
            await gr.query()
            self.assertEqual(len(gr), total_count)

            # ensure 'APPENDEDZZ' not present yet
            tgr = await client.GlideRecord('problem')
            tgr.add_query('short_description', 'LIKE', 'APPENDEDZZ')
            await tgr.query()
            self.assertEqual(len(tgr), 0)

            # stage updates
            while await gr.next():
                gr.short_description = gr.short_description + ' -- APPENDEDZZ'
            await gr.update_multiple()

            # verify all appended
            tgr = await client.GlideRecord('problem')
            tgr.add_query('short_description', 'LIKE', 'APPENDEDZZ')
            await tgr.query()
            self.assertEqual(len(tgr), total_count)

            # change only even-indexed
            expected_to_change = []
            i = 0
            while await tgr.next():
                r = tgr
                if i % 2 == 0:
                    r.short_description = r.short_description + ' even'
                    expected_to_change.append(r.get_value('sys_id'))
                    self.assertTrue(r.changes())
                else:
                    self.assertFalse(r.changes())
                i += 1

            saw_change = []

            def custom_handle(response):
                nonlocal saw_change
                self.assertEqual(response.status_code, 200)
                saw_change.append(response.json()['result']['sys_id']['value'])

            await tgr.update_multiple(custom_handle)
            self.assertCountEqual(saw_change, expected_to_change)
            self.assertListEqual(saw_change, expected_to_change)

            await tgr.delete_multiple()
        finally:
            await client.session.aclose()

    async def test_multi_update_with_failures(self):
        client = AsyncServiceNowClient(self.c.server, self.c.credentials)
        try:
            br = await client.GlideRecord('sys_script')

            # create BR once if missing
            br.add_query('name', 'test_multi_update_with_failures')
            await br.query()
            if not await br.next():
                br.initialize()
                br.name = 'test_multi_update_with_failures'
                br.collection = 'problem'
                br.active = True
                br.when = 'before'
                br.order = 100
                br.action_insert = True
                br.action_update = True
                br.abort_action = True
                br.add_message = True
                br.message = 'rejected by test_multi_update_with_failures br'
                br.filter_condition = 'short_descriptionLIKEEICAR^ORdescriptionLIKEEICAR^EQ'
                await br.insert()

            gr = await client.GlideRecord('problem')
            gr.add_query('short_description', 'LIKE', 'BUNKZZ')
            await gr.query()
            self.assertTrue(await gr.delete_multiple())  # clear
            await gr.query()
            self.assertEqual(len(gr), 0, 'should have had none left')

            total_count = 10
            # insert records
            for i in range(total_count):
                ngr = await client.GlideRecord('problem')
                ngr.initialize()
                ngr.short_description = f"Unit Test - BUNKZZ Multi update {i}"
                self.assertTrue(await ngr.insert(), "Failed to insert a record")

            gr = await client.GlideRecord('problem')
            gr.add_query('short_description', 'LIKE', 'BUNKZZ')
            await gr.query()
            self.assertEqual(len(gr), total_count)

            # half append
            i = 0
            while i < (total_count // 2) and await gr.next():
                gr.short_description = gr.short_description + ' -- APPENDEDZZ'
                i += 1
            # half error
            while await gr.next():
                gr.short_description = gr.short_description + ' -- EICAR'

            self.assertFalse(await gr.update_multiple())

            # make sure we cleaned up as expected (name-mangled attrs)
            self.assertEqual(gr._client.batch_api._AsyncBatchAPI__hooks, {})
            self.assertEqual(gr._client.batch_api._AsyncBatchAPI__stored_requests, {})
            self.assertEqual(gr._client.batch_api._AsyncBatchAPI__requests, [])

            tgr = await client.GlideRecord('problem')
            tgr.add_query('short_description', 'LIKE', 'APPENDEDZZ')
            await tgr.query()
            self.assertEqual(len(tgr), total_count // 2)

            tgr = await client.GlideRecord('problem')
            tgr.add_query('short_description', 'LIKE', 'EICAR')
            await tgr.query()
            self.assertEqual(len(tgr), 0)
        finally:
            await client.session.aclose()
