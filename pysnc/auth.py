import requests
import time
from requests.auth import AuthBase
from urllib3.util import parse_url
from .exceptions import *

JWT_GRANT_TYPE = 'urn:ietf:params:oauth:grant-type:jwt-bearer'

__all__ = [
    'ServiceNowFlow',
    'ServiceNowPasswordGrantFlow',
    'ServiceNowClientCredentialsFlow',
    'ServiceNowJWTAuth',
]


class ServiceNowFlow:
    def authenticate(self, instance: str, **kwargs) -> requests.Session:
        raise AuthenticationException('authenticate not implemented')


# note: not extending LegacyApplicationClient mostly to make oauth libs optional
class ServiceNowPasswordGrantFlow(ServiceNowFlow):

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

    def authorization_url(self, authorization_base_url):
        return f"{authorization_base_url}/oauth_token.do"

    def authenticate(self, instance: str, **kwargs) -> requests.Session:
        """
        Designed to be called by ServiceNowClient - internal method.
        """
        try:
            from oauthlib.oauth2 import LegacyApplicationClient
            from requests_oauthlib import OAuth2Session  # type: ignore

            oauth = OAuth2Session(client=LegacyApplicationClient(client_id=self.client_id),
                                  auto_refresh_url=self.authorization_url(instance),
                                  auto_refresh_kwargs=dict(client_id=self.client_id, client_secret=self.__secret))
            oauth.fetch_token(token_url=self.authorization_url(instance),
                              username=self.__username, password=self.__password, client_id=self.client_id,
                              client_secret=self.__secret, **kwargs)
            self.__password = None  # no longer need this.
            return oauth
        except ImportError:
            raise AuthenticationException('Install dependency requests-oauthlib')


class ServiceNowClientCredentialsFlow(ServiceNowFlow):
    """
    OAuth2 Client Credentials Grant Flow for ServiceNow.
    
    This flow is ideal for machine-to-machine authentication where no user context is needed.
    Only requires client_id and client_secret (no username/password).
    
    Example:
        >>> flow = ServiceNowClientCredentialsFlow('my_client_id', 'my_client_secret')
        >>> client = ServiceNowClient('dev12345', flow)
    """
    
    def __init__(self, client_id, client_secret):
        """
        Client Credentials flow authentication (OAuth 2.0)
        
        :param client_id: The OAuth application client ID
        :param client_secret: The OAuth application client secret
        """
        self.client_id = client_id
        self.__secret = client_secret
        self.__token = None
        self.__expires_at = None
        
    def authorization_url(self, authorization_base_url):
        """Generate the token endpoint URL"""
        return f"{authorization_base_url}/oauth_token.do"
    
    def _get_access_token(self, instance):
        """
        Request an access token from ServiceNow using client credentials.
        
        :param instance: The ServiceNow instance URL
        :return: Access token string
        :raises AuthenticationException: If token request fails
        """
        token_url = self.authorization_url(instance)
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8'
        }
        data = {
            'grant_type': 'client_credentials',
            'client_id': self.client_id,
            'client_secret': self.__secret
        }
        
        try:
            r = requests.post(token_url, headers=headers, data=data, timeout=30)
        except requests.exceptions.RequestException as e:
            raise AuthenticationException(f"Failed to connect to token endpoint: {e}")
        
        if r.status_code != 200:
            try:
                error_data = r.json()
                error_msg = error_data.get('error_description', error_data.get('error', r.text))
            except ValueError:
                error_msg = r.text
            raise AuthenticationException(
                f"Failed to obtain access token: {r.status_code} {r.reason} - {error_msg}"
            )
        
        try:
            token_data = r.json()
        except ValueError:
            raise AuthenticationException(f"Invalid JSON response from token endpoint: {r.text}")
        
        if 'access_token' not in token_data:
            raise AuthenticationException(f"No access_token in response: {token_data}")
        
        self.__token = token_data['access_token']
        # Use expires_in from response, default to 3600 seconds (1 hour) if not provided
        expires_in = token_data.get('expires_in', 3600)
        # Refresh 60 seconds before actual expiry to avoid edge cases
        self.__expires_at = int(time.time() + expires_in - 60)
        
        return self.__token
    
    def authenticate(self, instance: str, **kwargs) -> requests.Session:
        """
        Create and return an authenticated requests.Session with Bearer token.
        The session will automatically refresh the token when it expires.
        
        :param instance: The ServiceNow instance URL
        :param kwargs: Additional arguments (proxies, verify, etc.)
        :return: Authenticated requests.Session
        """
        session = requests.Session()
        
        # Get initial token
        if not self.__token or time.time() > (self.__expires_at or 0):
            self._get_access_token(instance)
        
        # Use a custom auth handler that refreshes tokens
        session.auth = _ClientCredentialsAuth(self, instance)
        
        return session


class _ClientCredentialsAuth(AuthBase):
    """
    Internal auth handler that automatically refreshes client credentials tokens.
    """
    
    def __init__(self, flow, instance):
        self._flow = flow
        self._instance = instance
    
    def __call__(self, request):
        # Check if token needs refresh
        if not self._flow._ServiceNowClientCredentialsFlow__token or \
           time.time() > (self._flow._ServiceNowClientCredentialsFlow__expires_at or 0):
            self._flow._get_access_token(self._instance)
        
        request.headers['Authorization'] = f"Bearer {self._flow._ServiceNowClientCredentialsFlow__token}"
        return request


class ServiceNowJWTAuth(AuthBase):

    def __init__(self, client_id, client_secret, jwt):
        """
        You must obtain a signed JWT from your OIDC provider, e.g. okta or auth0 or the like.
        We then use that JWT to issue an OAuth refresh token, that we then use to auth.
        """
        self.client_id = client_id
        self.__secret = client_secret
        self.__jwt = jwt
        self.__token = None
        self.__expires_at = None

    def _get_access_token(self, request):
        url = parse_url(request.url)
        token_url = f"{url.scheme}://{url.host}/oauth_token.do"
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'Authentication': f"Bearer {self.__jwt}"
        }
        data = {
            'grant_type': JWT_GRANT_TYPE,
            'client_id': self.client_id,
            'client_secret': self.__secret
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
