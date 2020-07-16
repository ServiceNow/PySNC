import requests
from .exceptions import *
from .utils import get_instance


class ServiceNowOAuth2(object):

    def __init__(self, username, password=None, client_id='3e57bb02663102004d010ee8f561307a'):
        """
        Password flow authentication using 'legacy mobile'

        :param username: The user name to authenticate with
        :param password: The user's password
        :param client_id: The ID of the provider
        """
        if isinstance(username, (tuple, list)):
            self.__username = username[0]
            self.__password = username[1]
        else:
            self.__username = username
            self.__password = password
        self.client_id = client_id

    def authenticate(self, instance):
        """
        Designed to be called by ServiceNowClient - internal method.
        """
        try:
            from oauthlib.oauth2 import LegacyApplicationClient
            from requests_oauthlib import OAuth2Session
            secret_url = '%s/api/now/mobileapp/plugin/secret' % instance
            r = requests.get(secret_url, auth=(self.__username, self.__password))
            if r.status_code != 200:
                # likely basic auth doesn't work, meaning password flow likely wont work
                raise AuthenticationException(r.text)
            client_secret = r.json()['result']['secret']

            oauth = OAuth2Session(client=LegacyApplicationClient(client_id=self.client_id))
            oauth.fetch_token(token_url='%s/oauth_token.do' % instance,
                              username=self.__username, password=self.__password, client_id=self.client_id,
                              client_secret=client_secret)
            self.__password = None # no longer need this.
            return oauth
        except ImportError:
            raise AuthenticationException('Install dependency requests-oauthlib')

