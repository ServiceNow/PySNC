from unittest import TestCase

from pysnc import ServiceNowClient
from .constants import Constants
from .utils import TempTestRecord


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

    def test_add_delete_get(self):
        client = ServiceNowClient(self.c.server, self.c.credentials)
        with TempTestRecord(client, 'problem') as gr:
            self.assertIsNotNone(gr.sys_id)
            attachments = gr.get_attachments()
            self.assertNotEqual(attachments, None)
            self.assertEqual(len(attachments), 0)

            content = "this is a sample attachment\nwith\nmulti\nlines"
            test_url = gr.add_attachment('test.txt', content)
            self.assertIsNotNone(test_url, "expected the location of test.txt")

            attachments = gr.get_attachments()
            self.assertEqual(len(attachments), 1)
            attachments.next()
            self.assertEqual(attachments.get_link(), test_url)

            test_txt_sys_id = attachments.sys_id

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
                    self.assertEqual(a.file_name, 'test.txt')
                    lines = a.readlines()
                    print(lines)
                    print(repr(lines))
                    self.assertEqual(lines[0], "this is a sample attachment")
                    self.assertEqual(len(lines), 4)
                if a.file_name.endswith('bin'):
                    self.assertEqual(a.file_name, 'test.bin')
                    raw = a.read()
                    self.assertEqual(raw, bcontent, "binary content did not match")

            # get
            problem_attachment = client.Attachment('problem')
            problem_attachment.get(test_txt_sys_id)
            self.assertEqual(problem_attachment.get_link(), test_url)
            self.assertEqual(problem_attachment.sys_id, test_txt_sys_id)
            self.assertEqual(problem_attachment.read().decode('ascii'), content)


            # list
            problem_attachment = client.Attachment('problem')
            problem_attachment.add_query('file_name', 'thisdoesntexist918')
            problem_attachment.query()
            self.assertFalse(problem_attachment.next())


            problem_attachment = client.Attachment('problem')
            problem_attachment.add_query('file_name', 'test.txt')
            problem_attachment.query()
            self.assertTrue(problem_attachment.next())
            self.assertEqual(problem_attachment.sys_id, test_txt_sys_id)


        client.session.close()
