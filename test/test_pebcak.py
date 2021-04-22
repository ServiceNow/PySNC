from unittest import TestCase

from pysnc import ServiceNowClient
from pysnc.exceptions import *
from constants import Constants


class TestPEBCAK(TestCase):
    c = Constants()

    def test_table(self):
        client = ServiceNowClient(self.c.server, self.c.credentials)
        gr = client.GlideRecord('sys_user_list')
        client.session.close()
        self.assertRaises(RequestException, gr.get, 'doesntmatter')

    def test_instance(self):
        with self.assertRaises(InstanceException) as context:
            client = ServiceNowClient('test.x', self.c.credentials)
            self.assertTrue(isinstance(context.exception, InstanceException))

    def test_creds(self):
        with self.assertRaises(AuthenticationException) as context:
            client = ServiceNowClient(self.c.server, ('test','test'))
            gr = client.GlideRecord('sys_user')
            gr.get('asdf')
            self.assertTrue(isinstance(context.exception, AuthenticationException))

    def test_no_result_without_query(self):
        client = ServiceNowClient(self.c.server, self.c.credentials)
        gr = client.GlideRecord('sys_user')
        gr.add_query('sys_id', 'bunk')
        self.assertFalse(gr.has_next())
        for e in gr:
            assert "Should not have iterated!"
        client.session.close()

