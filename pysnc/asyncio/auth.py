"""
Asynchronous authentication implementations for ServiceNow client.
"""

import time
from typing import Optional

import httpx

from ..exceptions import *

JWT_GRANT_TYPE = "urn:ietf:params:oauth:grant-type:jwt-bearer"


class AsyncServiceNowFlow:
    """Base class for async authentication flows"""

    async def authenticate(self, instance: str, **kwargs) -> httpx.AsyncClient:
        """
        Authenticate and return an httpx.AsyncClient

        :param str instance: The instance URL
        :param kwargs: Additional parameters for authentication
        :return: An authenticated httpx.AsyncClient
        :raises: AuthenticationException if authentication fails
        """
        raise AuthenticationException("authenticate not implemented")


class AsyncServiceNowPasswordGrantFlow(AsyncServiceNowFlow):
    """
    Password grant flow authentication for async client
    """

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

    def authorization_url(self, authorization_base_url: str) -> str:
        return f"{authorization_base_url}/oauth_token.do"

    async def authenticate(self, instance: str, **kwargs) -> httpx.AsyncClient:  # type: ignore[override]
        """
        Designed to be called by AsyncServiceNowClient (async).
        Returns an authenticated httpx.AsyncClient.
        """
        token_url = self.authorization_url(instance)
        form = {
            "grant_type": "password",
            "username": self.__username,
            "password": self.__password,
            "client_id": self.client_id,
            "client_secret": self.__secret,
        }
        if "scope" in kwargs and kwargs["scope"]:
            form["scope"] = kwargs["scope"]

        verify = kwargs.get("verify", True)
        proxies = kwargs.get("proxies", None)
        timeout = kwargs.get("timeout", 30.0)

        # Build the client we will return on success
        client = httpx.AsyncClient(
            base_url=instance,
            headers={"Accept": "application/json"},
            verify=verify,
            proxy=proxies,
            timeout=timeout,
            follow_redirects=True,
        )
        try:
            resp = await client.post(token_url, data=form, headers={"Accept": "application/json"})
        except Exception:
            await client.aclose()
            raise AuthenticationException("Failed to authenticate")

        try:
            payload = resp.json()
        except Exception:
            await client.aclose()
            raise AuthenticationException(resp.text)

        if resp.status_code >= 400 or "access_token" not in payload:
            await client.aclose()
            raise AuthenticationException(payload)

        # drop password after successful exchange
        self.__password = None

        client.headers["Authorization"] = f"Bearer {payload['access_token']}"
        return client


class AsyncServiceNowClientCredentialsFlow(AsyncServiceNowFlow):
    """
    OAuth2 Client Credentials Grant Flow for async ServiceNow client.
    
    This flow is ideal for machine-to-machine authentication where no user context is needed.
    Only requires client_id and client_secret (no username/password).
    
    Example:
        >>> flow = AsyncServiceNowClientCredentialsFlow('my_client_id', 'my_client_secret')
        >>> client = AsyncServiceNowClient('dev12345', flow)
    """
    
    def __init__(self, client_id: str, client_secret: str):
        """
        Client Credentials flow authentication (OAuth 2.0)
        
        :param client_id: The OAuth application client ID
        :param client_secret: The OAuth application client secret
        """
        self.client_id = client_id
        self.__secret = client_secret
        self.__token: Optional[str] = None
        self.__expires_at: Optional[float] = None
        
    def authorization_url(self, authorization_base_url: str) -> str:
        """Generate the token endpoint URL"""
        return f"{authorization_base_url}/oauth_token.do"
    
    async def _get_access_token(self, instance: str) -> str:
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
        
        async with httpx.AsyncClient() as client:
            try:
                r = await client.post(token_url, headers=headers, data=data, timeout=30.0)
            except httpx.RequestError as e:
                raise AuthenticationException(f"Failed to connect to token endpoint: {e}")
            
            if r.status_code != 200:
                try:
                    error_data = r.json()
                    error_msg = error_data.get('error_description', error_data.get('error', r.text))
                except Exception:
                    error_msg = r.text
                raise AuthenticationException(
                    f"Failed to obtain access token: {r.status_code} {r.reason_phrase} - {error_msg}"
                )
            
            try:
                token_data = r.json()
            except Exception:
                raise AuthenticationException(f"Invalid JSON response from token endpoint: {r.text}")
            
            if 'access_token' not in token_data:
                raise AuthenticationException(f"No access_token in response: {token_data}")
            
            self.__token = token_data['access_token']
            # Use expires_in from response, default to 3600 seconds (1 hour) if not provided
            expires_in = token_data.get('expires_in', 3600)
            # Refresh 60 seconds before actual expiry to avoid edge cases
            self.__expires_at = time.time() + expires_in - 60
            
            return self.__token
    
    async def authenticate(self, instance: str, **kwargs) -> httpx.AsyncClient:
        """
        Create and return an authenticated httpx.AsyncClient with Bearer token.
        The client will automatically refresh the token when it expires.
        
        :param instance: The ServiceNow instance URL
        :param kwargs: Additional arguments (proxies, verify, timeout, etc.)
        :return: Authenticated httpx.AsyncClient
        """
        verify = kwargs.get("verify", True)
        proxies = kwargs.get("proxies", None)
        timeout = kwargs.get("timeout", 30.0)
        
        # Get initial token
        if not self.__token or (self.__expires_at is not None and time.time() > self.__expires_at):
            await self._get_access_token(instance)
        
        # Create client with custom auth handler that refreshes tokens
        client = httpx.AsyncClient(
            base_url=instance,
            headers={"Accept": "application/json"},
            auth=_AsyncClientCredentialsAuth(self, instance),
            verify=verify,
            proxy=proxies,
            timeout=timeout,
            follow_redirects=True,
        )
        
        return client


class _AsyncClientCredentialsAuth(httpx.Auth):
    """
    Internal auth handler that automatically refreshes client credentials tokens for async client.
    """
    
    def __init__(self, flow: AsyncServiceNowClientCredentialsFlow, instance: str):
        self._flow = flow
        self._instance = instance
    
    async def async_auth_flow(self, request: httpx.Request):
        """httpx Auth flow that checks and refreshes token before each request"""
        # Check if token needs refresh
        if not self._flow._AsyncServiceNowClientCredentialsFlow__token or \
           (self._flow._AsyncServiceNowClientCredentialsFlow__expires_at is not None and 
            time.time() > self._flow._AsyncServiceNowClientCredentialsFlow__expires_at):
            await self._flow._get_access_token(self._instance)
        
        request.headers['Authorization'] = f"Bearer {self._flow._AsyncServiceNowClientCredentialsFlow__token}"
        yield request


class AsyncServiceNowJWTAuth(httpx.Auth):
    """
    JWT-based authentication for async client
    """

    def __init__(self, client_id: str, client_secret: str, jwt: str):
        """
        You must obtain a signed JWT from your OIDC provider (Okta/Auth0/etc.).
        We then use that JWT to obtain an OAuth access token.
        """
        self.client_id = client_id
        self.__secret = client_secret
        self.__jwt = jwt
        self.__token: Optional[str] = None
        self.__expires_at: Optional[float] = None

    async def _get_access_token(self, request: httpx.Request) -> tuple[str, float]:
        # Build token endpoint from the request URL
        url = request.url
        token_url = f"{url.scheme}://{url.host}/oauth_token.do"

        headers = {
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "Authentication": f"Bearer {self.__jwt}",
        }
        data = {
            "grant_type": JWT_GRANT_TYPE,
            "client_id": self.client_id,
            "client_secret": self.__secret,
        }

        async with httpx.AsyncClient() as ac:
            r = await ac.post(token_url, headers=headers, data=data)
        assert r.status_code == 200, f"Failed to auth, see syslogs {r.text}"
        data = r.json()
        expires = int(time.time() + data["expires_in"])
        return data["access_token"], expires

    async def async_auth_flow(self, request: httpx.Request):
        """Instead of __call__"""
        # Refresh token if missing/expired
        if not self.__token or (self.__expires_at is not None and time.time() > self.__expires_at):
            self.__token, self.__expires_at = await self._get_access_token(request)

        request.headers["Authorization"] = f"Bearer {self.__token}"
        yield request
