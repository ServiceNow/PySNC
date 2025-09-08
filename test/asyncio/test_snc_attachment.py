from typing import Any, Dict, Optional
from unittest import IsolatedAsyncioTestCase

from pysnc.asyncio import AsyncServiceNowClient

from ..constants import Constants


class AsyncTempTestRecord:
    """Minimal async version of TempTestRecord used in sync tests."""

    def __init__(self, client, table: str, default_data: Optional[Dict[str, Any]] = None):
        self._client = client
        self._table = table
        self._data = default_data or {}
        self._gr = None

    async def __aenter__(self):
        self._gr = await self._client.GlideRecord(self._table)
        self._gr.initialize()  # local, no I/O
        for k, v in self._data.items():
            self._gr.set_value(k, v)  # local, no I/O
        await self._gr.insert()  # network I/O
        return self._gr

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        try:
            if self._gr and getattr(self._gr, "sys_id", None):
                await self._gr.delete()  # network I/O
        finally:
            self._gr = None
        # Do not suppress exceptions
        return False


class TestAsyncAttachment(IsolatedAsyncioTestCase):
    c = Constants()

    async def _deleteOrCreateTestRecord(self, short_description: str):
        client = AsyncServiceNowClient(self.c.server, self.c.credentials)
        try:
            gr = await client.GlideRecord("problem")
            gr.add_query("short_description", short_description)
            await gr.query()
            if await gr.next():
                return gr
            gr.initialize()
            gr.short_description = short_description
            gr.description = "Second Field"
            await gr.insert()
            return gr
        finally:
            await client.session.aclose()

    async def _getOrCreateEmptyTestRecord(self):
        client = AsyncServiceNowClient(self.c.server, self.c.credentials)
        try:
            gr = await client.GlideRecord("problem")
            gr.add_query("short_description", "Unit Test - Attachments")
            await gr.query()
            if await gr.next():
                return gr
            gr.initialize()
            gr.short_description = "Unit Test - Attachments"
            gr.description = "Second Field"
            await gr.insert()
            return gr
        finally:
            await client.session.aclose()

    async def test_attachments_for(self):
        gr = await self._getOrCreateEmptyTestRecord()
        attachments = await gr.get_attachments()
        self.assertIsNotNone(attachments)
        self.assertEqual(len(attachments), 0)

    async def test_add_delete_get(self):
        client = AsyncServiceNowClient(self.c.server, self.c.credentials)
        try:
            async with AsyncTempTestRecord(client, "problem") as gr:
                self.assertIsNotNone(gr.sys_id)

                attachments = await gr.get_attachments()
                self.assertIsNotNone(attachments)
                self.assertEqual(len(attachments), 0)

                content = "this is a sample attachment\nwith\nmulti\nlines"
                test_url = await gr.add_attachment("test.txt", content)
                self.assertIsNotNone(test_url, "expected the location of test.txt")

                attachments = await gr.get_attachments()
                self.assertEqual(len(attachments), 1)
                await attachments.next()
                self.assertEqual(attachments.get_link(), test_url)

                test_txt_sys_id = attachments.sys_id

                bcontent = b"\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09"
                await gr.add_attachment("test.bin", bcontent)

                attachments = await gr.get_attachments()
                self.assertEqual(len(attachments), 2)

                tgr = await client.GlideRecord(gr.table)
                assert await tgr.get(gr.sys_id), "could not re-query the table?"
                self.assertEqual(len(await tgr.get_attachments()), 2, "Could not see attachments on re-query?")

                # iterate over attachments (async)
                async for a in attachments:
                    self.assertTrue(a.file_name.startswith("test"), f"expected a test file, not {a.file_name}")
                    if a.file_name.endswith("txt"):
                        self.assertEqual(a.file_name, "test.txt")
                        lines = await a.readlines()
                        self.assertEqual(lines[0], "this is a sample attachment")
                        self.assertEqual(len(lines), 4)
                    if a.file_name.endswith("bin"):
                        self.assertEqual(a.file_name, "test.bin")
                        raw = await a.read()
                        self.assertEqual(raw, bcontent, "binary content did not match")

                # get
                problem_attachment = await client.Attachment("problem")
                await problem_attachment.get(test_txt_sys_id)
                self.assertEqual(problem_attachment.get_link(), test_url)
                self.assertEqual(problem_attachment.sys_id, test_txt_sys_id)
                self.assertEqual((await problem_attachment.read()).decode("ascii"), content)

                # list (no results)
                problem_attachment = await client.Attachment("problem")
                problem_attachment.add_query("file_name", "thisdoesntexist918")
                await problem_attachment.query()
                self.assertFalse(await problem_attachment.next())

                # list (find specific)
                problem_attachment = await client.Attachment("problem")
                problem_attachment.add_query("file_name", "test.txt")
                await problem_attachment.query()
                self.assertTrue(await problem_attachment.next())
                self.assertEqual(problem_attachment.sys_id, test_txt_sys_id)
        finally:
            await client.session.aclose()
