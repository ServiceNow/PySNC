import asyncio
import os
from unittest import TestCase

import pytest

from pysnc.asyncio import AsyncServiceNowClient
from ..constants import Constants
from ..utils import TempTestRecord


class TestAsyncAttachment(TestCase):
    c = Constants()

    async def _deleteOrCreateTestRecord(self):
        client = AsyncServiceNowClient(self.c.server, self.c.credentials)
        gr = client.GlideRecord('problem')
        gr.add_query('short_description', 'Async Unit Test - Attachments')
        await gr.query()
        if await gr.next():
            return gr
        await gr.initialize()
        gr.short_description = "Async Unit Test - Attachments"
        gr.description = "Second Field"
        await gr.insert()
        await client.close()
        return gr

    async def _getOrCreateEmptyTestRecord(self):
        client = AsyncServiceNowClient(self.c.server, self.c.credentials)
        gr = client.GlideRecord('problem')
        gr.add_query('short_description', 'Async Unit Test - Attachments - Empty')
        await gr.query()
        if await gr.next():
            return gr
        await gr.initialize()
        gr.short_description = "Async Unit Test - Attachments - Empty"
        gr.description = "Second Field"
        await gr.insert()
        await client.close()
        return gr

    @pytest.mark.asyncio
    async def test_attachments_for(self):
        gr = await self._getOrCreateEmptyTestRecord()
        attachments = await gr.get_attachments()
        self.assertNotEqual(attachments, None)
        self.assertEqual(len(attachments), 0)

    @pytest.mark.asyncio
    async def test_upload_attachment(self):
        gr = await self._deleteOrCreateTestRecord()
        
        # Create a temporary test file
        test_file_path = "test_attachment.txt"
        with open(test_file_path, "w") as f:
            f.write("This is a test attachment file")
        
        try:
            # Upload the attachment
            client = AsyncServiceNowClient(self.c.server, self.c.credentials)
            attachment = client.Attachment('problem')
            attachment.table_sys_id = gr.sys_id
            
            with open(test_file_path, "rb") as file_obj:
                sys_id = await attachment.upload(
                    file_name="test_attachment.txt",
                    file_obj=file_obj,
                    content_type="text/plain"
                )
            
            # Verify attachment was created
            self.assertIsNotNone(sys_id)
            self.assertEqual(attachment.file_name, "test_attachment.txt")
            self.assertEqual(attachment.content_type, "text/plain")
            
            # Get attachment details
            result = await attachment.get(sys_id)
            self.assertTrue(result)
            self.assertEqual(attachment.sys_id, sys_id)
            
            # List attachments
            gr_client = AsyncServiceNowClient(self.c.server, self.c.credentials)
            gr2 = gr_client.GlideRecord('problem')
            gr2.get(gr.sys_id)
            attachments = await gr2.get_attachments()
            self.assertGreaterEqual(len(attachments), 1)
            
            # Get file content
            response = await attachment.get_file()
            self.assertIsNotNone(response)
            content = await response.aread()
            self.assertEqual(content.decode(), "This is a test attachment file")
            
            # Delete attachment
            delete_result = await attachment.delete()
            self.assertTrue(delete_result)
            
            # Verify attachment is gone
            attachments_after = await gr2.get_attachments()
            found = False
            for att in attachments_after:
                if att.get('sys_id') == sys_id:
                    found = True
            self.assertFalse(found)
            
            await client.close()
            await gr_client.close()
            
        finally:
            # Clean up test file
            if os.path.exists(test_file_path):
                os.remove(test_file_path)

    @pytest.mark.asyncio
    async def test_multiple_attachments(self):
        gr = await self._deleteOrCreateTestRecord()
        
        # Create temporary test files
        test_files = ["test_attachment1.txt", "test_attachment2.txt"]
        for i, file_path in enumerate(test_files):
            with open(file_path, "w") as f:
                f.write(f"This is test attachment file {i+1}")
        
        try:
            # Upload multiple attachments
            client = AsyncServiceNowClient(self.c.server, self.c.credentials)
            attachment = client.Attachment('problem')
            attachment.table_sys_id = gr.sys_id
            
            sys_ids = []
            for file_path in test_files:
                with open(file_path, "rb") as file_obj:
                    sys_id = await attachment.upload(
                        file_name=file_path,
                        file_obj=file_obj,
                        content_type="text/plain"
                    )
                    sys_ids.append(sys_id)
            
            # List attachments
            attachments = await attachment.list()
            self.assertGreaterEqual(len(attachments), len(test_files))
            
            # Clean up attachments
            for sys_id in sys_ids:
                await attachment.delete(sys_id)
            
            await client.close()
            
        finally:
            # Clean up test files
            for file_path in test_files:
                if os.path.exists(file_path):
                    os.remove(file_path)
