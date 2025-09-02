# tests/asyncio/test_snc_api_audit_scoped.py
from unittest import IsolatedAsyncioTestCase

from pysnc.asyncio import AsyncServiceNowClient
from pysnc import exceptions
from ..constants import Constants


class TestAsyncAuditScoped(IsolatedAsyncioTestCase):
    c = Constants()

    async def test_connect(self):
        client = AsyncServiceNowClient(self.c.server, self.c.credentials)
        try:
            gr = await client.GlideRecord('sys_user')
            r = await gr.get('6816f79cc0a8016401c5a33be04be441')
            self.assertEqual(r, True)
        finally:
            await client.session.aclose()

    async def test_link(self):
        client = AsyncServiceNowClient(self.c.server, self.c.credentials)
        try:
            gr = await client.GlideRecord('sys_user')
            await gr.get('6816f79cc0a8016401c5a33be04be441')
            link = gr.get_link(no_stack=True)
            self.assertTrue(link.endswith('sys_user.do?sys_id=6816f79cc0a8016401c5a33be04be441'))
            link = gr.get_link()
            self.assertTrue(
                link.endswith(
                    'sys_user.do?sys_id=6816f79cc0a8016401c5a33be04be441'
                    '&sysparm_stack=sys_user_list.do?sysparm_query=active=true'
                )
            )
        finally:
            await client.session.aclose()

    async def test_link_query(self):
        client = AsyncServiceNowClient(self.c.server, self.c.credentials)
        try:
            gr = await client.GlideRecord('sys_user')
            gr.limit = 5
            await gr.query()
            link = gr.get_link(no_stack=True)
            self.assertTrue(link.endswith('sys_user.do?sys_id=-1'))
            self.assertTrue(await gr.next())
            link = gr.get_link(no_stack=True)
            self.assertFalse(link.endswith('sys_user.do?sys_id=-1'))
        finally:
            await client.session.aclose()

    async def test_link_list(self):
        client = AsyncServiceNowClient(self.c.server, self.c.credentials)
        try:
            gr = await client.GlideRecord('sys_user')
            gr.add_active_query()
            gr.add_query("name", "CONTAINS", "a")
            link = gr.get_link_list()
            self.assertTrue(
                link.endswith('sys_user_list.do?sysparm_query=active%3Dtrue%5EnameCONTAINSa%5EORDERBYsys_id')
            )
        finally:
            await client.session.aclose()

    async def test_next(self):
        client = AsyncServiceNowClient(self.c.server, self.c.credentials)
        try:
            gr = await client.GlideRecord('sys_user')
            gr.add_active_query()
            gr.limit = 2
            await gr.query()
            self.assertTrue(await gr.next())
            self.assertTrue(gr.has_next())
            self.assertTrue(await gr.next())
            self.assertFalse(gr.has_next())
        finally:
            await client.session.aclose()

    async def test_proxy(self):
        proxy = 'http://localhost:4444'
        obj = {'http': 'http://localhost:4444', 'https': 'http://localhost:4444'}

        client = AsyncServiceNowClient(self.c.server, self.c.credentials, proxy=proxy)
        try:
            # Async client doesn’t expose .proxies like requests.Session,
            # so validate what AsyncServiceNowClient stored.
            self.assertEqual(client._AsyncServiceNowClient__proxy_url, proxy)
        finally:
            await client.session.aclose()

        client = AsyncServiceNowClient(self.c.server, self.c.credentials, proxy=obj)
        try:
            self.assertEqual(client._AsyncServiceNowClient__proxy_url, proxy)
        finally:
            await client.session.aclose()

    async def test_len(self):
        client = AsyncServiceNowClient(self.c.server, self.c.credentials)
        try:
            gr = await client.GlideRecord('sys_user')
            self.assertEqual(len(gr), 0)
            self.assertEqual(gr.get_row_count(), 0)
            await gr.query()
            self.assertGreater(len(gr), 0)
            self.assertGreater(gr.get_row_count(), 0)
        finally:
            await client.session.aclose()

    def test_http_url(self):
        # same semantics as sync: http URLs are rejected at construction time
        self.assertRaises(
            exceptions.InstanceException,
            lambda: AsyncServiceNowClient('http://bunk.service-now.com', self.c.credentials),
        )
