from unittest import TestCase

from pysnc import ServiceNowClient
from pysnc.auth import ServiceNowJWTAuth, ServiceNowOAuth2
from constants import Constants
from pysnc import exceptions

import requests
import time
from oauthlib.oauth2 import LegacyApplicationClient
from requests_oauthlib import OAuth2Session

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
            self.assertTrue('User Not Authenticated' in str(e))
            self.assertTrue('Required to provide Auth information' in str(e))
        except Exception:
            assert 'Should have got an Auth exception'

    def test_oauth_manual(self):
        # Manual setup using legacy oauth
        server = self.c.server
        creds = self.c.credentials

        client_id = self.c.get_value('CLIENT_ID')
        secret = self.c.get_value('CLIENT_SECRET')

        oauth = OAuth2Session(client=LegacyApplicationClient(client_id=client_id))
        token_url = "%s/oauth_token.do" % server

        token = oauth.fetch_token(token_url=token_url,
                              username=creds[0], password=creds[1], client_id=client_id,
                              client_secret=secret)

        print("failed after this")

        client = ServiceNowClient(self.c.server, oauth)
        gr = client.GlideRecord('sys_user')
        gr.fields = 'sys_id'
        self.assertTrue(gr.get('6816f79cc0a8016401c5a33be04be441'))

    def test_oauth(self):
        # Manual setup using legacy oauth
        server = self.c.server
        creds = self.c.credentials

        client_id = self.c.get_value('CLIENT_ID')
        secret = self.c.get_value('CLIENT_SECRET')

        client = ServiceNowClient(self.c.server, ServiceNowOAuth2(creds[0], creds[1], client_id, secret))
        gr = client.GlideRecord('sys_user')
        gr.fields = 'sys_id'
        self.assertTrue(gr.get('6816f79cc0a8016401c5a33be04be441'))

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










