from unittest import TestCase

from pysnc import ServiceNowClient
from constants import Constants
from pprint import pprint

class TestIteration(TestCase):
    c = Constants()

    def test_default_behavior(self):
        client = ServiceNowClient(self.c.server, self.c.credentials)
        gr = client.GlideRecord('sys_metadata', batch_size=100)
        gr.fields = 'sys_id'
        gr.limit = 500
        gr.query()
        self.assertTrue(gr._is_rewindable())

        self.assertTrue(len(gr) > 500, 'Expected more than 500 records')

        count = 0
        while gr.next():
            count += 1
        self.assertEqual(count, 500, 'Expected 500 records when using next')

        self.assertEqual(len([r.sys_id for r in gr]), 500, 'Expected 500 records when an iterable')
        self.assertEqual(len([r.sys_id for r in gr]), 500, 'Expected 500 records when iterated again')

        # expect the same for next
        count = 0
        while gr.next():
            count += 1
        self.assertEqual(count, 0, 'Expected 0 records when not rewound, as next does not auto-rewind')
        gr.rewind()
        while gr.next():
            count += 1
        self.assertEqual(count, 500, 'Expected 500 post rewind')

        # should not throw
        gr.query()
        gr.query()

        client.session.close()

    def test_rewind_behavior(self):
        client = ServiceNowClient(self.c.server, self.c.credentials)
        gr = client.GlideRecord('sys_metadata', batch_size=250, rewindable=False)
        gr.fields = 'sys_id'
        gr.limit = 500
        gr.query()
        self.assertEqual(gr._GlideRecord__current, -1)
        self.assertFalse(gr._is_rewindable())
        self.assertEqual(len([r for r in gr]), 500, 'Expected 500 records when an iterable')
        self.assertEqual(len([r for r in gr]), 0, 'Expected no records when iterated again')

        # but if we query again...
        with self.assertRaises(RuntimeError):
            gr.query()