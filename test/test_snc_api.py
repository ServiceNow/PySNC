from unittest import TestCase

from pysnc import ServiceNowClient
from constants import Constants

class TestAuditScoped(TestCase):
    c = Constants()

    def test_connect(self):
        client = ServiceNowClient(self.c.server, self.c.credentials)
        gr = client.GlideRecord('sys_user')
        r = gr.get('6816f79cc0a8016401c5a33be04be441')
        self.assertEqual(r, True)
        client.session.close()

    def test_link(self):
        client = ServiceNowClient(self.c.server, self.c.credentials)
        gr = client.GlideRecord('sys_user')
        gr.get('6816f79cc0a8016401c5a33be04be441')
        link = gr.get_link(no_stack=True)
        self.assertTrue(link.endswith('sys_user.do?sys_id=6816f79cc0a8016401c5a33be04be441'))
        link = gr.get_link()
        self.assertTrue(link.endswith('sys_user.do?sys_id=6816f79cc0a8016401c5a33be04be441&sysparm_stack=sys_user_list.do?sysparm_query=active=true'))
        client.session.close()

    def test_link_query(self):
        client = ServiceNowClient(self.c.server, self.c.credentials)
        gr = client.GlideRecord('sys_user')
        gr.limit = 5;
        gr.query()
        link = gr.get_link(no_stack=True)
        print(link)
        self.assertTrue(link.endswith('sys_user.do?sys_id=null'))
        self.assertTrue(gr.next())
        link = gr.get_link(no_stack=True)
        print(link)
        self.assertFalse(link.endswith('sys_user.do?sys_id=null'))
        client.session.close()

    def test_link_list(self):
        client = ServiceNowClient(self.c.server, self.c.credentials)
        gr = client.GlideRecord('sys_user')
        gr.add_active_query()
        gr.add_query("name","CONTAINS","a")
        link = gr.get_link_list()
        print(link)
        self.assertTrue(link.endswith('sys_user_list.do?sysparm_query=active%3Dtrue%5EnameCONTAINSa'))
        client.session.close()


    def test_next(self):
        client = ServiceNowClient(self.c.server, self.c.credentials)
        gr = client.GlideRecord('sys_user')
        gr.add_active_query()
        gr.limit = 2
        gr.query()
        #print(gr.serialize_all())
        self.assertTrue(gr.next())
        self.assertTrue(gr.has_next())
        self.assertTrue(gr.next())
        self.assertFalse(gr.has_next())
        client.session.close()

    def test_proxy(self):
        proxy = 'http://localhost:4444'
        obj = {'http': 'http://localhost:4444', 'https': 'http://localhost:4444'}
        client = ServiceNowClient(self.c.server, self.c.credentials, proxy=proxy)
        self.assertEqual(client.session.proxies, obj)
        client = ServiceNowClient(self.c.server, self.c.credentials, proxy=obj)
        self.assertEqual(client.session.proxies, obj)
        client.session.close()

    def test_len(self):
        client = ServiceNowClient(self.c.server, self.c.credentials)
        gr = client.GlideRecord('sys_user')
        self.assertEqual(len(gr), 0)
        self.assertEqual(gr.get_row_count(), 0)
        gr.query()
        self.assertGreater(len(gr), 0)
        self.assertGreater(gr.get_row_count(), 0)
        client.session.close()


