from unittest import TestCase, skip

from pysnc import ServiceNowClient
from pysnc.auth import *
from .constants import Constants
from pysnc import exceptions

import requests
import time

class TestAuth(TestCase):
    c = Constants()

    def test_basic(self):
        client = ServiceNowClient(self.c.server, self.c.credentials)
        gr = client.GlideRecord('sys_user')
        gr.fields = 'sys_id'
        self.assertTrue(gr.get('6816f79cc0a8016401c5a33be04be441'))

    def test_basic_fail(self):
        client = ServiceNowClient(self.c.server, ('admin', 'this is not a real password'))
        try:
            gr = client.GlideRecord('sys_user')
            gr.get('does not matter')
            assert 'Exception should have been thrown'
        except exceptions.AuthenticationException as e:
            self.assertTrue('not authenticated' in str(e).lower())
            self.assertTrue('required to provide auth information' in str(e).lower())
        except Exception:
            assert 'Should have got an Auth exception'

    @skip("Requires valid oauth client_id and secret, and I don't want to need anything not out of box")
    def test_oauth(self):
        # Manual setup using legacy oauth
        server = self.c.server
        creds = self.c.credentials

        client_id = self.c.get_value('CLIENT_ID')
        secret = self.c.get_value('CLIENT_SECRET')

        client = ServiceNowClient(self.c.server, ServiceNowPasswordGrantFlow(creds[0], creds[1], client_id, secret))
        gr = client.GlideRecord('sys_user')
        gr.fields = 'sys_id'
        self.assertTrue(gr.get('6816f79cc0a8016401c5a33be04be441'))

    def test_auth_param_check(self):
        self.assertRaisesRegex(AuthenticationException, r'Cannot specify both.+', lambda: ServiceNowClient('anyinstance', auth='asdf', cert='asdf'))
        self.assertRaisesRegex(AuthenticationException, r'No valid auth.+', lambda: ServiceNowClient('anyinstance', auth='zzz'))

    def nop_test_jwt(self):
        """
        we act as our own client here, which you should not do.
        """

        # to test this we would 1st: get a JWT from a provider
        # jwt = getJwtFromOkta(user, pass)
        # then we would do something like this...
        '''
        auth = ServiceNowJWTAuth(client_id, client_secret, jwt)
        client = ServiceNowClient(self.c.server, auth)

        gr = client.GlideRecord('sys_user')
        gr.fields = 'sys_id'
        assert gr.get('6816f79cc0a8016401c5a33be04be441'), "did not jwt auth"
        '''

    @skip("Requires keys and conf that makes automation hard")
    def test_mtls(self):
        # e.g. PYSNC_USER_KEY=x PYSNC_USER_CERT=y poetry run pytest test/test_snc_auth.py::TestAuth::test_mtls
        path_key = self.c.get_value('USER_KEY')
        assert path_key, 'Require user private key'
        path_cert = self.c.get_value('USER_CERT')
        assert path_cert, 'Require user x509 certificate'

        client = ServiceNowClient(self.c.server, cert=(path_cert, path_key))
        gr = client.GlideRecord('sys_user')
        gr.fields = 'sys_id'
        self.assertTrue(gr.get('6816f79cc0a8016401c5a33be04be441'))










