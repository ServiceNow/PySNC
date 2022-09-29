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

    def test_oauth(self):
        # Manual setup using legacy oauth
        server = self.c.server
        creds = self.c.credentials

        client_id = 'ac0dd3408c1031006907010c2cc6ef6d' #mobile
        secret = '7d8o4teb91hmwumraksf' # not actually a secret

        oauth = OAuth2Session(client=LegacyApplicationClient(client_id=client_id))
        token = oauth.fetch_token(token_url='%s/oauth_token.do' % server,
                              username=creds[0], password=creds[1], client_id=client_id,
                              client_secret=secret)

        client = ServiceNowClient(self.c.server, oauth)
        gr = client.GlideRecord('sys_user')
        gr.fields = 'sys_id'
        self.assertTrue(gr.get('6816f79cc0a8016401c5a33be04be441'))

    def test_oauth(self):
        # Manual setup using legacy oauth
        server = self.c.server
        creds = self.c.credentials

        client_id = 'ac0dd3408c1031006907010c2cc6ef6d' #mobile
        secret = '7d8o4teb91hmwumraksf' # not actually a secret

        client = ServiceNowClient(self.c.server, ServiceNowOAuth2(creds[0], creds[1], client_id, secret))
        gr = client.GlideRecord('sys_user')
        gr.fields = 'sys_id'
        self.assertTrue(gr.get('6816f79cc0a8016401c5a33be04be441'))

    def test_jwt(self):
        """
        we act as our own client here, which you should not do.
        """
        import jwt
        client_id = '91c9a3503e5e15104efa8fea3b37c3dd'
        client_secret = self.c.get_value('jwt-client-secret')
        key = self.c.get_value('jwt-shared-key')

        payload = {
            'aud': client_id,
            'iss': client_id,
            'sub': 'itil',
            'exp': int(time.time()+30), # expire in 30 seconds
        }
        token = jwt.encode(payload, key, algorithm="HS256")


        auth = ServiceNowJWTAuth(client_id, client_secret, token)
        client = ServiceNowClient(self.c.server, auth)

        gr = client.GlideRecord('sys_user')
        gr.fields = 'sys_id'
        assert gr.get('6816f79cc0a8016401c5a33be04be441'), "did not jwt auth"










