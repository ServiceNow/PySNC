from unittest import TestCase

from pysnc import ServiceNowClient
from constants import Constants
from pprint import pprint

class TestBatching(TestCase):
    c = Constants()

    def test_batch_multi(self):
        client = ServiceNowClient(self.c.server, self.c.credentials)
        gr = client.GlideRecord('problem')
        gr.fields = 'sys_id'
        gr.batch_size = 3
        gr.limit = 9
        gr.query()

        res = [r.sys_id for r in gr]
        self.assertEqual(len(res), 9)
        client.session.close()

    def test_batch_multi_uneven(self):
        client = ServiceNowClient(self.c.server, self.c.credentials)
        gr = client.GlideRecord('problem')
        gr.fields = 'sys_id'
        gr.batch_size = 3
        gr.limit = 7
        gr.query()

        res = [r.sys_id for r in gr]
        self.assertEqual(len(res), 7)
        client.session.close()

    def test_default_limit(self):
        client = ServiceNowClient(self.c.server, self.c.credentials)
        gr = client.GlideRecord('problem')
        gr.add_active_query()

        params = gr._parameters()
        print(params)
        self.assertFalse('sysparm_limit' in params, 'We have a default limit for some reason')

        gr.limit = 40
        print(gr.limit)
        params = gr._parameters()
        print(params)
        self.assertTrue('sysparm_limit' in params)
        client.session.close()


