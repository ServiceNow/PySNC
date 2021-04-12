import requests
from .exceptions import *
from .utils import get_instance


class ServiceNowOAuth2(object):

    def __init__(self, username, password, client_id, client_secret):
        """
        Password flow authentication using 'legacy mobile'

        :param username: The user name to authenticate with
        :param password: The user's password
        :param client_id: The ID of the provider
        :param client_secret: Secret for the given provider (client_id)
        """
        if isinstance(username, (tuple, list)):
            self.__username = username[0]
            self.__password = username[1]
        else:
            self.__username = username
            self.__password = password
        self.client_id = client_id
        self.__secret = client_secret

    def authenticate(self, instance):
        """
        Designed to be called by ServiceNowClient - internal method.
        """
        try:
            from oauthlib.oauth2 import LegacyApplicationClient
            from requests_oauthlib import OAuth2Session

            oauth = OAuth2Session(client=LegacyApplicationClient(client_id=self.client_id))
            oauth.fetch_token(token_url='%s/oauth_token.do' % instance,
                              username=self.__username, password=self.__password, client_id=self.client_id,
                              client_secret=self.__secret)
            self.__password = None  # no longer need this.
            return oauth
        except ImportError:
            raise AuthenticationException('Install dependency requests-oauthlib')

