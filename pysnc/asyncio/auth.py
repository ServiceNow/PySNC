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
