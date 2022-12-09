from unittest import TestCase

from pysnc import ServiceNowClient
import pysnc
from constants import Constants

class TestBatching(TestCase):
    """
    TODO: active query
    """
    c = Constants()

    def test_get_query(self):
        client = ServiceNowClient(self.c.server, self.c.credentials)
        gr = client.GlideRecord('sys_db_object', batched=True)
        gr.add_query('name', 'alm_asset')
        gr.query()

        gr.execute()









