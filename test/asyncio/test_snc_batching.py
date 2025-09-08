# tests/asyncio/test_snc_api_batching.py
from unittest import IsolatedAsyncioTestCase

from pysnc.asyncio import AsyncServiceNowClient
from ..constants import Constants


class TestAsyncBatching(IsolatedAsyncioTestCase):
    c = Constants()

    async def test_batch_multi(self):
        client = AsyncServiceNowClient(self.c.server, self.c.credentials)
        try:
            gr = await client.GlideRecord('problem')
            gr.fields = 'sys_id'
            gr.batch_size = 3
            gr.limit = 9
            await gr.query()

            res = [r.sys_id async for r in gr]
            self.assertEqual(len(res), 9)
        finally:
            await client.session.aclose()

    async def test_batch_multi_uneven(self):
        client = AsyncServiceNowClient(self.c.server, self.c.credentials)
        try:
            gr = await client.GlideRecord('problem')
            gr.fields = 'sys_id'
            gr.batch_size = 3
            gr.limit = 7
            await gr.query()

            res = [r.sys_id async for r in gr]
            self.assertEqual(len(res), 7)
        finally:
            await client.session.aclose()

    async def test_batch_actual(self):
        client = AsyncServiceNowClient(self.c.server, self.c.credentials)
        try:
            gr = await client.GlideRecord('problem')
            gr.fields = 'sys_id'
            gr.batch_size = 3
            await gr.query()
            await gr.next()
            # Accessing the same mangled attr as sync (inherited storage)
            self.assertEqual(len(gr._GlideRecord__results), 3)
        finally:
            await client.session.aclose()

    async def test_default_limit(self):
        client = AsyncServiceNowClient(self.c.server, self.c.credentials)
        try:
            gr = await client.GlideRecord('problem')
            gr.add_active_query()

            params = gr._parameters()
            self.assertEqual(params['sysparm_limit'], 100, "default batch size is not 100?")

            gr.limit = 400
            params = gr._parameters()
            self.assertIn('sysparm_limit', params)
            self.assertEqual(
                params['sysparm_limit'], 100,
                "batch size still 100 if we have a limit over batch size"
            )
        finally:
            await client.session.aclose()

    async def test_default_order(self):
        client = AsyncServiceNowClient(self.c.server, self.c.credentials)
        try:
            gr = await client.GlideRecord('problem')

            self.assertEqual(gr._parameters()['sysparm_query'], 'ORDERBYsys_id')
            gr.order_by('number')
            self.assertEqual(gr._parameters()['sysparm_query'], 'ORDERBYnumber')

            gr.order_by(None)
            self.assertEqual(gr._parameters()['sysparm_query'], 'ORDERBYsys_id')
        finally:
            await client.session.aclose()
