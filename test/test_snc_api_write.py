from unittest import TestCase

from pysnc import ServiceNowClient
from constants import Constants

class TestAuditScoped(TestCase):
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
        gr2 = client.GlideRecord('problem')
        self.assertIsNotNone(gr2.get(res))
        # We have validated inserting works, now can we update.
        gr2.short_description = "ABCDEFG0123"
        gr2.update()

        gr3 = client.GlideRecord('problem')
        gr3.get(res)
        self.assertEqual(gr3.short_description, "ABCDEFG0123")

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
        # make sure it exists
        gr2 = client.GlideRecord('problem')
        self.assertTrue(gr2.get(res))

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
        # insert five bunk records
        for i in range(5):
            gr = client.GlideRecord('problem')
            gr.initialize()
            gr.short_description = 'Unit Test - BUNKZZ Multi Delete'
            gr.insert()

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





