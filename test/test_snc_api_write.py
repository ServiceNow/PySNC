from unittest import TestCase

from pysnc import ServiceNowClient
from .constants import Constants


class TestWrite(TestCase):
    c = Constants()

    def test_crud(self):
        client = ServiceNowClient(self.c.server, self.c.credentials)
        gr = client.GlideRecord('problem')
        gr.initialize()
        gr.short_description = "Unit Test - Insert"
        gr.description = "Second Field"
        gr.bunk_field = "Bunk Field"
        res = gr.insert()
        self.assertIsNotNone(res)
        # should have gotten the response back, ergo populated new fields
        self.assertIsNotNone(gr.opened_by)
        self.assertEqual(len(gr.opened_by), 32, 'expected opened_by to be a sys_id')
        self.assertNotEqual(gr.get_value('opened_by'), gr.get_display_value('opened_by')) # our name isnt a sys_id
        first_user_display = gr.get_display_value('opened_by')

        # We have validated inserting works, now can we update.
        # find us a user to change the opened_by field that isn't us
        user = client.GlideRecord('sys_user')
        self.assertTrue(user.get('26fbff173b331300ad3cc9bb34efc4bd')) # problem.admin
        self.assertNotEqual(user.sys_id, gr.get_value('opened_by'), 'what this shouldnt happen')
        #print(f"new user id is {user.sys_id}")

        # actually update
        gr2 = client.GlideRecord('problem')
        self.assertTrue(gr2.get(res))
        #print(f"pre-update {gr2.serialize(display_value='both')}")
        self.assertTrue(bool(gr2.active))
        gr2.short_description = "ABCDEFG0123"
        self.assertTrue(gr2.changes())
        self.assertEqual(gr2.get_value('short_description'), "ABCDEFG0123")
        gr2.assigned_to = user.sys_id

        #print(f"mid-update {gr2.serialize(display_value='both')}")
        self.assertIsNotNone(gr2.update())
        #print(f"post-update {gr2.serialize(display_value='both')}")

        # now we expect our record to be different, locally
        self.assertTrue(bool(gr2.active)) # server-side forces it to stay true
        self.assertEqual(gr2.short_description, 'ABCDEFG0123')
        self.assertEqual(gr2.assigned_to, user.sys_id)
        self.assertNotEqual(gr2.get_display_value('assigned_to'), first_user_display)
        self.assertEqual(gr2.get_display_value('assigned_to'), user.get_display_value('name'))


        # and if we re-query
        gr3 = client.GlideRecord('problem')
        gr3.get(res)
        self.assertEqual(gr3.short_description, "ABCDEFG0123")
        self.assertEqual(gr3.get_display_value('assigned_to'), user.get_display_value('name'))

        gr4 = gr3.pop_record()
        gr4.short_description = 'ZZZ123'
        self.assertTrue(gr4.update())

        gr4 = gr3.pop_record()
        gr4.short_description = 'ZZZ123'
        self.assertTrue(gr4.update())



        gr4 = gr3.pop_record()
        gr4.short_description = 'ZZZ123'
        self.assertTrue(gr4.update())



        self.assertTrue(gr3.delete())

        # make sure it is deleted
        gr4 = client.GlideRecord('problem')
        self.assertFalse(gr4.get(res))
        client.session.close()

    def test_insert(self):
        # I want to ensure the records sys_id is updated
        client = ServiceNowClient(self.c.server, self.c.credentials)
        gr = client.GlideRecord('problem')
        gr.initialize()
        gr.short_description = "Unit Test - Test insert id update"
        self.assertIsNone(gr.sys_id)
        res = gr.insert()
        self.assertIsNotNone(res)
        self.assertIsNotNone(gr.sys_id)
        self.assertEqual(res, gr.sys_id)
        self.assertIsNotNone(gr.number)
        # make sure it exists
        gr2 = client.GlideRecord('problem')
        self.assertTrue(gr2.get(res))
        self.assertEqual(gr2.number, gr.number)

        gr.delete()

        # make sure it is deleted
        gr4 = client.GlideRecord('problem')
        self.assertFalse(gr4.get(res))
        client.session.close()

    def test_insert_custom_guid(self):
        client = ServiceNowClient(self.c.server, self.c.credentials)
        customsysid = 'AAAABBBBCCCCDDDDEEEEFFFF00001111'
        # make sure this id doesn't exist, first
        gr = client.GlideRecord('problem')
        if gr.get(customsysid):
            gr.delete()
        # I want to ensure the records sys_id is updated
        gr = client.GlideRecord('problem')
        gr.initialize()
        gr.set_new_guid_value(customsysid)
        gr.short_description = "Unit Test - Test insert id update"
        res = gr.insert()
        self.assertIsNotNone(res)
        self.assertIsNotNone(gr.sys_id)
        self.assertEqual(res, customsysid)
        # make sure it exists
        gr2 = client.GlideRecord('problem')
        self.assertTrue(gr2.get(customsysid))

        gr.delete()

        # make sure it is deleted
        gr4 = client.GlideRecord('problem')
        self.assertFalse(gr4.get(res))
        client.session.close()

    def test_object_setter(self):
        client = ServiceNowClient(self.c.server, self.c.credentials)
        gr = client.GlideRecord('problem')
        gr.initialize()
        gr.name = 'aaaa'
        self.assertEqual(gr.name, 'aaaa')
        gr.roles = [1,2,3]
        self.assertEqual(gr.roles, [1,2,3])
        client.session.close()

    def test_object_secondary_field(self):
        client = ServiceNowClient(self.c.server, self.c.credentials)
        gr = client.GlideRecord('sys_user')
        gr.limit = 1
        gr.query()
        self.assertTrue(gr.next())
        gr.boom = 'aaaa'
        self.assertEqual(gr.boom, 'aaaa')
        gr.bye = [1,2,3]
        self.assertEqual(gr.bye, [1,2,3])
        client.session.close()

    def test_multi_delete(self):
        client = ServiceNowClient(self.c.server, self.c.credentials)
        gr = client.GlideRecord('problem')
        gr.add_query('short_description', 'LIKE', 'BUNKZZ')
        gr.delete_multiple() # try to make sure weh ave none first

        # insert five bunk records
        for i in range(5):
            gr = client.GlideRecord('problem')
            gr.initialize()
            gr.short_description = f"Unit Test - BUNKZZ Multi Delete {i}"
            assert gr.insert(), "Failed to insert a record"

        # now make sure they exist...
        gr = client.GlideRecord('problem')
        gr.add_query('short_description', 'LIKE', 'BUNKZZ')
        gr.query()

        self.assertEqual(len(gr), 5)

        # now multi delete...
        gr = client.GlideRecord('problem')
        gr.add_query('short_description', 'LIKE', 'BUNKZZ')
        self.assertTrue(gr.delete_multiple())

        # check again
        gr = client.GlideRecord('problem')
        gr.add_query('short_description', 'LIKE', 'BUNKZZ')
        gr.query()

        self.assertEqual(len(gr), 0)
        client.session.close()

    def test_multi_update(self):
        client = ServiceNowClient(self.c.server, self.c.credentials)

        gr = client.GlideRecord('problem')
        gr.add_query('short_description', 'LIKE', 'BUNKZZ')
        gr.query()
        gr.delete_multiple() # try to make sure weh ave none first
        gr.query()
        self.assertEqual(len(gr), 0)


        total_count = 10
        # insert five bunk records
        for i in range(total_count):
            gr = client.GlideRecord('problem')
            gr.initialize()
            gr.short_description = f"Unit Test - BUNKZZ Multi Delete {i}"
            assert gr.insert(), "Failed to insert a record"

        # now make sure they exist...
        gr = client.GlideRecord('problem')
        gr.add_query('short_description', 'LIKE', 'BUNKZZ')
        gr.query()
        self.assertEqual(len(gr), total_count)

        # make sure our 'new' ones arent here to throw it off
        tgr = client.GlideRecord('problem')
        tgr.add_query('short_description', 'LIKE', 'APPENDEDZZ')
        tgr.query()
        self.assertEqual(len(tgr), 0)

        while gr.next():
            gr.short_description = gr.short_description + ' -- APPENDEDZZ'

        gr.update_multiple()

        tgr = client.GlideRecord('problem')
        tgr.add_query('short_description', 'LIKE', 'APPENDEDZZ')
        tgr.query()
        self.assertEqual(len(tgr), total_count)

        # make sure we only send changed ones...
        expected_to_change = []
        for i, r in enumerate(tgr):
            if i % 2 == 0:
                r.short_description = r.short_description + ' even'
                expected_to_change.append(r.get_value('sys_id'))
                self.assertTrue(r.changes())
            else:
                self.assertFalse(r.changes())

        saw_change = []
        def custom_handle(response):
            nonlocal saw_change
            self.assertEqual(response.status_code, 200)
            saw_change.append(response.json()['result']['sys_id']['value'])

        tgr.update_multiple(custom_handle)
        print(saw_change)
        self.assertCountEqual(saw_change, expected_to_change)
        self.assertListEqual(saw_change, expected_to_change)

        tgr.delete_multiple()
        client.session.close()

    def test_multi_update_with_failures(self):
        client = ServiceNowClient(self.c.server, self.c.credentials)
        br = client.GlideRecord('sys_script')

        # in order to test the failure case, let's insert a BR that will reject specific values
        br.add_query('name', 'test_multi_update_with_failures')
        br.query()
        if not br.next():
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
            br.insert()


        gr = client.GlideRecord('problem')
        gr.add_query('short_description', 'LIKE', 'BUNKZZ')
        gr.query()
        self.assertTrue(gr.delete_multiple()) # try to make sure weh ave none first
        gr.query()
        self.assertEqual(len(gr), 0, 'should have had none left')


        total_count = 10
        # insert five bunk records
        # TODO: insert multiple
        for i in range(total_count):
            gr = client.GlideRecord('problem')
            gr.initialize()
            gr.short_description = f"Unit Test - BUNKZZ Multi update {i}"
            assert gr.insert(), "Failed to insert a record"

        gr = client.GlideRecord('problem')
        gr.add_query('short_description', 'LIKE', 'BUNKZZ')
        gr.query()
        self.assertEqual(len(gr), total_count)

        i = 0
        # half append
        print(f"for i < {total_count//2}")
        while i < (total_count//2) and gr.next():
            gr.short_description = gr.short_description + ' -- APPENDEDZZ'
            i += 1
        # half error
        while gr.next():
            gr.short_description = gr.short_description + ' -- EICAR'

        self.assertFalse(gr.update_multiple())
        # make sure we cleaned up as expected
        self.assertEqual(gr._client.batch_api._BatchAPI__hooks, {})
        self.assertEqual(gr._client.batch_api._BatchAPI__stored_requests, {})
        self.assertEqual(gr._client.batch_api._BatchAPI__requests, [])

        tgr = client.GlideRecord('problem')
        tgr.add_query('short_description', 'LIKE', 'APPENDEDZZ')
        tgr.query()
        self.assertEqual(len(tgr), total_count//2)

        tgr = client.GlideRecord('problem')
        tgr.add_query('short_description', 'LIKE', 'EICAR')
        tgr.query()
        self.assertEqual(len(tgr), 0)

