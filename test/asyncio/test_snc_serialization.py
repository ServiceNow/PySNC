# tests/asyncio/test_snc_serialization.py
from unittest import IsolatedAsyncioTestCase
from types import SimpleNamespace

from pysnc.asyncio import AsyncServiceNowClient
from ..constants import Constants
from pysnc.record import GlideRecord  # used for local (no-network) serialization tests


class TestAsyncSerialization(IsolatedAsyncioTestCase):
    c = Constants()

    async def test_pandas_smart(self):
        client = AsyncServiceNowClient(self.c.server, self.c.credentials)
        try:
            gr = await client.GlideRecord('problem')
            gr.fields = 'sys_id,short_description,state'
            gr.limit = 4
            await gr.query()

            # print(await gr.serialize_all(display_value='both'))

            data = await gr.to_pandas()
            self.assertIsInstance(data, dict)
            self.assertIn('sys_id', data)
            self.assertIn('short_description', data)
            self.assertIn('state__value', data)
            self.assertIn('state__display', data)
            self.assertEqual(len(data['sys_id']), 4)
            self.assertEqual(len(data['short_description']), 4)
            self.assertEqual(len(data['state__value']), 4)
            self.assertEqual(len(data['state__display']), 4)
        finally:
            await client.session.aclose()

    async def test_pandas_both(self):
        client = AsyncServiceNowClient(self.c.server, self.c.credentials)
        try:
            gr = await client.GlideRecord('problem')
            gr.fields = 'sys_id,short_description,state'
            gr.limit = 4
            await gr.query()

            # print(await gr.serialize_all(display_value='both'))

            data = await gr.to_pandas(mode='both')
            self.assertIsInstance(data, dict)
            self.assertIn('sys_id__value', data)
            self.assertIn('short_description__display', data)
            self.assertIn('state__value', data)
            self.assertIn('state__display', data)
            self.assertEqual(len(data['sys_id__value']), 4)
            self.assertEqual(len(data['short_description__display']), 4)
            self.assertEqual(len(data['state__value']), 4)
            self.assertEqual(len(data['state__display']), 4)
        finally:
            await client.session.aclose()

    async def test_pandas_value(self):
        client = AsyncServiceNowClient(self.c.server, self.c.credentials)
        try:
            gr = await client.GlideRecord('problem')
            gr.fields = 'sys_id,short_description,state'
            gr.limit = 4
            await gr.query()

            # print(await gr.serialize_all(display_value='both'))

            data = await gr.to_pandas(mode='value')
            self.assertIsInstance(data, dict)
            self.assertIn('sys_id', data)
            self.assertIn('short_description', data)
            self.assertIn('state', data)
            self.assertNotIn('state__value', data)
            self.assertEqual(len(data['sys_id']), 4)
        finally:
            await client.session.aclose()

    async def test_pandas_order_cols(self):
        client = AsyncServiceNowClient(self.c.server, self.c.credentials)
        try:
            gr = await client.GlideRecord('problem')
            gr.fields = 'sys_id,short_description,state'
            gr.limit = 4
            await gr.query()

            # print(await gr.serialize_all(display_value='both'))

            data = await gr.to_pandas()
            self.assertListEqual(list(data.keys()), ['sys_id', 'short_description', 'state__value', 'state__display'])
            data = await gr.to_pandas(mode='display')
            self.assertListEqual(list(data.keys()), ['sys_id', 'short_description', 'state'])
            data = await gr.to_pandas(columns=['jack', 'jill', 'hill'], mode='display')
            self.assertListEqual(list(data.keys()), ['jack', 'jill', 'hill'])
        finally:
            await client.session.aclose()

    async def test_serialize_all_batch(self):
        client = AsyncServiceNowClient(self.c.server, self.c.credentials)
        try:
            gr = await client.GlideRecord('problem')
            gr.batch_size = 3
            gr.limit = 9
            await gr.query()

            records = await gr.serialize_all()
            self.assertEqual(len(records), 9)
        finally:
            await client.session.aclose()

    async def test_serialize_noncurrent(self):
        client = AsyncServiceNowClient(self.c.server, self.c.credentials)
        try:
            gr = await client.GlideRecord('problem')
            gr.fields = 'sys_id,short_description,state'
            gr.limit = 4
            await gr.query()
            self.assertIsNone(gr.serialize())
            await gr.next()
            self.assertIsNotNone(gr.serialize())
        finally:
            await client.session.aclose()

    async def test_serialize_changes(self):
        client = AsyncServiceNowClient(self.c.server, self.c.credentials)
        try:
            gr = await client.GlideRecord('problem')
            gr.fields = 'sys_id,short_description,state'
            gr.limit = 4
            await gr.query()
            await gr.next()
            data = gr.serialize()
            self.assertIsNotNone(data)
            self.assertListEqual(list(data.keys()), ['sys_id', 'short_description', 'state'])
            self.assertListEqual(list(gr.serialize(changes_only=True).keys()), [])
            gr.short_description = 'new'
            self.assertListEqual(list(gr.serialize(changes_only=True).keys()), ['short_description'])
        finally:
            await client.session.aclose()

    # -------- no-network serialization tests (same as sync) --------

    async def test_serialize(self):
        gr = GlideRecord(None, 'some_table')
        gr.initialize()
        gr.strfield = 'my string'
        gr.set_display_value('strfield', 'my string display value')
        gr.intfield = 5
        data = gr.serialize()
        self.assertIsNotNone(data)
        self.assertEqual(data, {'intfield': 5, 'strfield': 'my string'})

    async def test_serialize_display(self):
        gr = GlideRecord(None, 'some_table')
        gr.initialize()
        gr.strfield = 'my string'
        gr.set_display_value('strfield', 'my string display value')
        gr.intfield = 5
        data = gr.serialize(display_value=True)
        self.assertIsNotNone(data)
        self.assertEqual(gr.get_value('strfield'), 'my string')
        self.assertEqual(gr.get_display_value('strfield'), 'my string display value')
        self.assertEqual(gr.serialize(), {'intfield': 5, 'strfield': 'my string'})
        self.assertEqual(data, {'intfield': 5, 'strfield': 'my string display value'})

    async def test_serialize_reference_link(self):
        gr = GlideRecord(None, 'some_table')
        gr.initialize()
        gr.reffield = 'my reference'
        gr.set_link('reffield', 'https://dev00000.service-now.com/api/now/table/sys___/abcde12345')
        gr._client = SimpleNamespace(instance=self.c.server)

        data = gr.serialize(exclude_reference_link=False)
        self.assertIsNotNone(data)
        self.assertEqual(gr.get_value('reffield'), 'my reference')
        self.assertTrue(gr.get_link(True).endswith('/some_table.do?sys_id=-1'), f"was {gr.get_link()}")
        self.assertEqual(gr.reffield.get_link(), 'https://dev00000.service-now.com/api/now/table/sys___/abcde12345')
        self.assertEqual(
            gr.serialize(exclude_reference_link=False),
            {'reffield': {'value': 'my reference', 'link': 'https://dev00000.service-now.com/api/now/table/sys___/abcde12345'}}
        )
        self.assertEqual(
            data,
            {'reffield': {'value': 'my reference', 'link': 'https://dev00000.service-now.com/api/now/table/sys___/abcde12345'}}
        )

        gr.reffield.set_link('https://dev00000.service-now.com/api/now/table/sys___/xyz789')
        self.assertEqual(gr.reffield.get_link(), 'https://dev00000.service-now.com/api/now/table/sys___/xyz789')

    async def test_serialize_reference_link_all(self):
        gr = GlideRecord(None, 'some_table')
        gr.initialize()
        gr.reffield = 'my reference'
        gr.set_link('reffield', 'https://dev00000.service-now.com/api/now/table/sys___/abcde12345')
        gr.set_display_value('reffield', 'my reference display')

        self.assertEqual(gr.get_value('reffield'), 'my reference')
        self.assertEqual(gr.get_display_value('reffield'), 'my reference display')
        self.assertEqual(gr.reffield.get_link(), 'https://dev00000.service-now.com/api/now/table/sys___/abcde12345')

        self.assertEqual(gr.serialize(), {'reffield': 'my reference'})
        self.assertEqual(
            gr.serialize(exclude_reference_link=False),
            {'reffield': {'value': 'my reference', 'link': 'https://dev00000.service-now.com/api/now/table/sys___/abcde12345'}}
        )
        self.assertEqual(
            gr.serialize(display_value=True, exclude_reference_link=False),
            {'reffield': {'display_value': 'my reference display', 'link': 'https://dev00000.service-now.com/api/now/table/sys___/abcde12345'}}
        )
        self.assertEqual(
            gr.serialize(display_value='both', exclude_reference_link=False),
            {'reffield': {'value': 'my reference', 'display_value': 'my reference display', 'link': 'https://dev00000.service-now.com/api/now/table/sys___/abcde12345'}}
        )

    async def test_str(self):
        gr = GlideRecord(None, 'some_table')
        gr.initialize()
        gr.strfield = 'my string'
        gr.set_display_value('strfield', 'my string display value')
        gr.intfield = 5
        data = str(gr)
        self.assertIsNotNone(data)
        self.assertTrue(data.startswith('some_table'))
        self.assertIn('my string', data)
        self.assertIn('intfield', data)

    async def test_serialize_all(self):
        client = AsyncServiceNowClient(self.c.server, self.c.credentials)
        try:
            gr = await client.GlideRecord('problem')
            gr.fields = 'sys_id,short_description,state'
            gr.limit = 4
            await gr.query()
            data = await gr.serialize_all()
            self.assertEqual(len(data), 4)
            for prb in data:
                self.assertEqual(list(prb.keys()), ['sys_id', 'short_description', 'state'])

            # value-only serialization should not include link objects
            data = await gr.serialize_all(exclude_reference_link=False)
            self.assertIsInstance(data[0]['short_description'], str)

            # (optional TODO parity case kept commented as in the original)
            # data = await gr.serialize_all(display_value='both', exclude_reference_link=False)
            # self.assertEqual(type(data[0]['short_description']), dict)
        finally:
            await client.session.aclose()
