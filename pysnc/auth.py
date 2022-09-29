import requests
import time
from requests.auth import AuthBase
from urllib3.util import parse_url, Url
from .exceptions import *
from .utils import get_instance

JWT_GRANT_TYPE = 'urn:ietf:params:oauth:grant-type:jwt-bearer'

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


class ServiceNowJWTAuth(AuthBase):

    def __init__(self, client_id, client_secret, assertion):
        """
        """
        assert client_id, "Requires client_id"
        assert client_secret, "Requires the secret"
        assert assertion, "Requires assertion, aka the JWT from your providver"
        self.__secret = client_secret
        self.client_id = client_id
        self.assertion = assertion
        self.__token = None
        self.__expires_at = None

    def get_assertion(self):
        """
        if you need to over-ride this.
        """
        return self.assertion

    def _get_access_token(self, request):
        url = parse_url(request.url)
        token_url = f"{url.scheme}://{url.host}/oauth_token.do"
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8'
        }
        data = {
            'grant_type': JWT_GRANT_TYPE,
            'client_id': self.client_id,
            'client_secret': self.__secret,
            'assertion': self.get_assertion()
        }
        r = requests.post(token_url, headers=headers, data=data)
        assert r.status_code == 200, f"Failed to auth, see syslogs {r.text}"
        data = r.json()
        expires = int(time.time()+data['expires_in'])
        return data['access_token'], expires

    def __call__(self, request):
        if not self.__token or time.time() > self.__expires_at:
            self.__token, self.__expires_at = self._get_access_token(request)
        request.headers['Authorization'] = f"Bearer {self.__token}"
        return request
