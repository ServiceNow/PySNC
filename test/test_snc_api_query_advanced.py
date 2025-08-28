from unittest import TestCase

from pysnc import ServiceNowClient, exceptions
from constants import Constants

class TestRecordQueryAdvanced(TestCase):
    c = Constants()


    def test_join_query(self):
        client = ServiceNowClient(self.c.server, self.c.credentials)
        gr = client.GlideRecord('sys_user')
        join_query = gr.add_join_query('sys_user_group', join_table_field='manager')
        join_query.add_query('active','true')
        self.assertEqual(gr.get_encoded_query(), 'JOINsys_user.sys_id=sys_user_group.manager!active=true')
        gr.query()
        self.assertGreater(gr.get_row_count(), 1)
        client.session.close()

    def test_join_query_2(self):
        client = ServiceNowClient(self.c.server, self.c.credentials)
        gr = client.GlideRecord('sys_user')
        join_query = gr.add_join_query('sys_user_has_role', join_table_field='user')
        join_query.add_query('role', '2831a114c611228501d4ea6c309d626d')
        self.assertEqual(gr.get_encoded_query(), 'JOINsys_user.sys_id=sys_user_has_role.user!role=2831a114c611228501d4ea6c309d626d')
        gr.query()
        gr.next()
        self.assertGreater(len(gr), 10) # demo data has a lot of admins
        self.assertLess(len(gr), 25) # but not THAT many

    def test_rl_query_manual(self):
        # simulate a left outter join by finding users with no roles
        client = ServiceNowClient(self.c.server, self.c.credentials)
        gr = client.GlideRecord('sys_user_group')
        gr.add_encoded_query('RLQUERYsys_group_has_role.group,>0,m2m^role.nameLIKEadmin^ENDRLQUERY')
        gr.query()
        self.assertGreater(gr.get_row_count(), 2)
        self.assertLess(gr.get_row_count(), 8)

    def test_rl_query_advanced(self):
        client = ServiceNowClient(self.c.server, self.c.credentials)
        gr = client.GlideRecord('sys_user_group')
        qc = gr.add_rl_query('sys_group_has_role', 'group', '>0', True)
        qc.add_query('role.name', 'LIKE', 'admin')
        self.assertEqual(gr.get_encoded_query(), 'RLQUERYsys_group_has_role.group,>0,m2m^role.nameLIKEadmin^ENDRLQUERY')
        gr.query()
        self.assertGreater(gr.get_row_count(), 2)
        self.assertLess(gr.get_row_count(), 8)

