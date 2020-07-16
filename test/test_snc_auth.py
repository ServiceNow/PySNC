from unittest import TestCase

from pysnc import ServiceNowClient
from pysnc import ServiceNowOAuth2
from constants import Constants
from pysnc import exceptions

import requests
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

    def test_oauth(self):
        # Manual setup using legacy oauth
        server = self.c.server
        creds = self.c.credentials

        client_id = '3e57bb02663102004d010ee8f561307a' #mobile

        # get the secret manually
        secret_url = '%s/api/now/mobileapp/plugin/secret' % server
        r = requests.get(secret_url, auth=creds)
        if r.status_code != 200:
            raise 'couldnt get secret'
        secret = r.json()['result']['secret']
        self.assertIsNotNone(secret)

        oauth = OAuth2Session(client=LegacyApplicationClient(client_id=client_id))
        token = oauth.fetch_token(token_url='%s/oauth_token.do' % server,
                              username=creds[0], password=creds[1], client_id=client_id,
                              client_secret=secret)

        client = ServiceNowClient(self.c.server, oauth)
        gr = client.GlideRecord('sys_user')
        gr.fields = 'sys_id'
        self.assertTrue(gr.get('6816f79cc0a8016401c5a33be04be441'))

    def test_oauth_builtin(self):
        client = ServiceNowClient(self.c.server, ServiceNowOAuth2(self.c.credentials))
        gr = client.GlideRecord('sys_user')
        gr.fields = 'sys_id'
        self.assertTrue(gr.get('6816f79cc0a8016401c5a33be04be441'))







