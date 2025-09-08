# tests/asyncio/test_snc_iteration.py
from unittest import IsolatedAsyncioTestCase

from pysnc.asyncio import AsyncServiceNowClient
from ..constants import Constants


class TestAsyncIteration(IsolatedAsyncioTestCase):
    c = Constants()

    async def test_default_behavior(self):
        client = AsyncServiceNowClient(self.c.server, self.c.credentials)
        try:
            gr = await client.GlideRecord('sys_metadata', batch_size=100)
            gr.fields = 'sys_id'
            gr.limit = 500
            await gr.query()
            self.assertTrue(gr._is_rewindable())

            self.assertTrue(len(gr) > 500, 'Expected more than 500 records')

            count = 0
            while await gr.next():
                count += 1
            self.assertEqual(count, 500, 'Expected 500 records when using next')

            self.assertEqual(len([r.sys_id async for r in gr]), 500, 'Expected 500 records when an iterable')
            self.assertEqual(len([r.sys_id async for r in gr]), 500, 'Expected 500 records when iterated again')

            # expect the same for next
            count = 0
            while await gr.next():
                count += 1
            self.assertEqual(count, 0, 'Expected 0 records when not rewound, as next does not auto-rewind')
            gr.rewind()
            while await gr.next():
                count += 1
            self.assertEqual(count, 500, 'Expected 500 post rewind')

            # should not throw
            await gr.query()
            await gr.query()
        finally:
            await client.session.aclose()

    async def test_rewind_behavior(self):
        client = AsyncServiceNowClient(self.c.server, self.c.credentials)
        try:
            gr = await client.GlideRecord('sys_metadata', batch_size=250, rewindable=False)
            gr.fields = 'sys_id'
            gr.limit = 500
            await gr.query()
            self.assertEqual(gr._GlideRecord__current, -1)
            self.assertFalse(gr._is_rewindable())
            self.assertEqual(len([r async for r in gr]), 500, 'Expected 500 records when an iterable')
            self.assertEqual(len([r async for r in gr]), 0, 'Expected no records when iterated again')

            # but if we query again...
            with self.assertRaises(RuntimeError):
                await gr.query()
        finally:
            await client.session.aclose()
