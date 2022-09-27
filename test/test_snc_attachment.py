from unittest import TestCase

from pysnc import ServiceNowClient
from constants import Constants
from utils import TempTestRecord


class TestAttachment(TestCase):
    c = Constants()

    def _deleteOrCreateTestRecord(self):
        client = ServiceNowClient(self.c.server, self.c.credentials)
        gr = client.GlideRecord('problem')
        gr.add_query('short_description', 'Unit Test - Attachments')
        gr.query()
        if gr.next():
            return gr
        gr.initialize()
        gr.short_description = "Unit Test - Attachments"
        gr.description = "Second Field"
        gr.insert()
        client.session.close()
        return gr

    def _getOrCreateEmptyTestRecord(self):
        client = ServiceNowClient(self.c.server, self.c.credentials)
        gr = client.GlideRecord('problem')
        gr.add_query('short_description', 'Unit Test - Attachments - Empty')
        gr.query()
        if gr.next():
            return gr
        gr.initialize()
        gr.short_description = "Unit Test - Attachments - Empty"
        gr.description = "Second Field"
        gr.insert()
        client.session.close()
        return gr


    def test_attachments_for(self):
        gr = self._getOrCreateEmptyTestRecord()
        attachments = gr.get_attachments()
        print(attachments)
        self.assertNotEqual(attachments, None)
        self.assertEqual(len(attachments), 0)

    def test_add_delete(self):
        client = ServiceNowClient(self.c.server, self.c.credentials)
        with TempTestRecord(client, 'problem') as gr:
            attachments = gr.get_attachments()
            self.assertNotEqual(attachments, None)
            self.assertEqual(len(attachments), 0)

            content = "this is a sample attachment\nwith\nmulti\nlines"
            gr.add_attachment('test.txt', content)

            attachments = gr.get_attachments()
            self.assertEqual(len(attachments), 1)

            bcontent = b'\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09'
            gr.add_attachment('test.bin', bcontent)

            attachments = gr.get_attachments()
            self.assertEqual(len(attachments), 2)

            tgr = client.GlideRecord(gr.table)
            assert tgr.get(gr.sys_id), "could not re-query the table?"
            self.assertEqual(len(tgr.get_attachments()), 2, "Could not see attachments on re-query?")

            for a in attachments:
                assert a.file_name.startswith('test'), f"expected a test file, not {a.file_name}"
                if a.file_name.endswith('txt'):
                    lines = a.readlines()
                    print(lines)
                    print(repr(lines))
                    self.assertEquals(lines[0], "this is a sample attachment")
                    self.assertEquals(len(lines), 4)
                if a.file_name.endswith('bin'):
                    raw = a.read()
                    self.assertEquals(raw, bcontent, "binary content did not match")

        client.session.close()

