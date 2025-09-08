# tests/asyncio/test_async_record_query_advanced.py
from unittest import IsolatedAsyncioTestCase

from pysnc.asyncio import AsyncServiceNowClient
from ..constants import Constants


class TestAsyncRecordQueryAdvanced(IsolatedAsyncioTestCase):
    c = Constants()

    async def test_join_query(self):
        client = AsyncServiceNowClient(self.c.server, self.c.credentials)
        try:
            gr = await client.GlideRecord('sys_user')
            join_query = gr.add_join_query('sys_user_group', join_table_field='manager')
            join_query.add_query('active', 'true')
            self.assertEqual(
                gr.get_encoded_query(),
                'JOINsys_user.sys_id=sys_user_group.manager!active=true'
            )
            await gr.query()
            self.assertGreater(gr.get_row_count(), 1)
        finally:
            await client.session.aclose()

    async def test_join_query_2(self):
        client = AsyncServiceNowClient(self.c.server, self.c.credentials)
        try:
            gr = await client.GlideRecord('sys_user')
            join_query = gr.add_join_query('sys_user_has_role', join_table_field='user')
            join_query.add_query('role', '2831a114c611228501d4ea6c309d626d')
            self.assertEqual(
                gr.get_encoded_query(),
                'JOINsys_user.sys_id=sys_user_has_role.user!role=2831a114c611228501d4ea6c309d626d'
            )
            await gr.query()
            await gr.next()
            # demo data has a lot of admins, but not *that* many
            self.assertGreater(len(gr), 10)
            self.assertLess(len(gr), 25)
        finally:
            await client.session.aclose()

    async def test_rl_query_manual(self):
        # simulate a left outer join by finding groups with admin-like roles
        client = AsyncServiceNowClient(self.c.server, self.c.credentials)
        try:
            gr = await client.GlideRecord('sys_user_group')
            gr.add_encoded_query('RLQUERYsys_group_has_role.group,>0,m2m^role.nameLIKEadmin^ENDRLQUERY')
            await gr.query()
            self.assertGreater(gr.get_row_count(), 2)
            self.assertLess(gr.get_row_count(), 8)
        finally:
            await client.session.aclose()

    async def test_rl_query_advanced(self):
        client = AsyncServiceNowClient(self.c.server, self.c.credentials)
        try:
            gr = await client.GlideRecord('sys_user_group')
            qc = gr.add_rl_query('sys_group_has_role', 'group', '>0', True)
            qc.add_query('role.name', 'LIKE', 'admin')
            self.assertEqual(
                gr.get_encoded_query(),
                'RLQUERYsys_group_has_role.group,>0,m2m^role.nameLIKEadmin^ENDRLQUERY'
            )
            await gr.query()
            self.assertGreater(gr.get_row_count(), 2)
            self.assertLess(gr.get_row_count(), 8)
        finally:
            await client.session.aclose()
