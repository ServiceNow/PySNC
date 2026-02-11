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

    @skip("Requires valid oauth client_id and secret for client credentials flow")
    def test_client_credentials(self):
        """
        Test OAuth2 Client Credentials Grant Flow.
        This flow only requires client_id and client_secret - no username/password needed.
        """
        client_id = self.c.get_value('CLIENT_ID')
        secret = self.c.get_value('CLIENT_SECRET')

        # Create client using client credentials flow
        flow = ServiceNowClientCredentialsFlow(client_id, secret)
        client = ServiceNowClient(self.c.server, flow)
        
        # Test basic query
        gr = client.GlideRecord('sys_user')
        gr.fields = 'sys_id'
        self.assertTrue(gr.get('6816f79cc0a8016401c5a33be04be441'))

    @skip("Requires valid oauth client_id and secret for client credentials flow")
    def test_client_credentials_token_refresh(self):
        """
        Test that tokens are automatically refreshed when they expire.
        """
        import time
        
        client_id = self.c.get_value('CLIENT_ID')
        secret = self.c.get_value('CLIENT_SECRET')

        flow = ServiceNowClientCredentialsFlow(client_id, secret)
        client = ServiceNowClient(self.c.server, flow)
        
        # Make first request
        gr1 = client.GlideRecord('sys_user')
        gr1.fields = 'sys_id'
        self.assertTrue(gr1.get('6816f79cc0a8016401c5a33be04be441'))
        
        # Force token expiration by manipulating the flow's internal state
        flow._ServiceNowClientCredentialsFlow__expires_at = int(time.time() - 100)
        
        # Make second request - should automatically refresh token
        gr2 = client.GlideRecord('sys_user')
        gr2.fields = 'sys_id'
        self.assertTrue(gr2.get('6816f79cc0a8016401c5a33be04be441'))

    @skip("Requires valid oauth client_id and secret for client credentials flow")  
    def test_client_credentials_invalid(self):
        """
        Test that invalid client credentials raise appropriate exceptions.
        """
        # Test with invalid credentials
        flow = ServiceNowClientCredentialsFlow('invalid_client_id', 'invalid_secret')
        client = ServiceNowClient(self.c.server, flow)
        
        with self.assertRaises(exceptions.AuthenticationException) as context:
            gr = client.GlideRecord('sys_user')
            gr.get('does not matter')
        
        # Check that error message is informative
        self.assertIn('access token', str(context.exception).lower())

    def test_auth_param_check(self):
        self.assertRaisesRegex(exceptions.AuthenticationException, r'Cannot specify both.+', lambda: ServiceNowClient('anyinstance', auth='asdf', cert='asdf'))
        self.assertRaisesRegex(exceptions.AuthenticationException, r'No valid auth.+', lambda: ServiceNowClient('anyinstance', auth='zzz'))

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










