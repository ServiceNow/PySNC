"""
Asynchronous authentication implementations for ServiceNow client.
"""

import httpx
import time
from typing import Dict, Any, Optional

from ..exceptions import *

JWT_GRANT_TYPE = 'urn:ietf:params:oauth:grant-type:jwt-bearer'


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
        raise AuthenticationException('authenticate not implemented')


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

    def authorization_url(self, authorization_base_url):
        """Get the authorization URL"""
        return f"{authorization_base_url}/oauth_token.do"

    async def authenticate(self, instance: str, **kwargs) -> httpx.AsyncClient:
        """
        Authenticate and return an httpx.AsyncClient
        
        :param str instance: The instance URL
        :param kwargs: Additional parameters for authentication
        :return: An authenticated httpx.AsyncClient
        :raises: AuthenticationException if authentication fails
        """
        try:
            # Create a new async client
            client = httpx.AsyncClient(**kwargs)
            
            # Prepare the token request
            token_url = self.authorization_url(instance)
            data = {
                'grant_type': 'password',
                'client_id': self.client_id,
                'client_secret': self.__secret,
                'username': self.__username,
                'password': self.__password
            }
            
            # Make the token request
            response = await client.post(token_url, data=data)
            
            if response.status_code != 200:
                raise AuthenticationException(f"Failed to authenticate: {response.text}")
            
            token_data = response.json()
            access_token = token_data.get('access_token')
            
            if not access_token:
                raise AuthenticationException("No access token in response")
            
            # Configure the client with the token
            client.headers.update({"Authorization": f"Bearer {access_token}"})
            
            # Clear password from memory for security
            self.__password = None
            
            return client
            
        except httpx.RequestError as e:
            raise AuthenticationException(f"Error during authentication: {str(e)}")
        except Exception as e:
            raise AuthenticationException(f"Failed to authenticate: {str(e)}")


class AsyncServiceNowJWTAuth(httpx.Auth):
    """
    JWT-based authentication for async client
    """
    
    def __init__(self, client_id, client_secret, jwt):
        """
        You must obtain a signed JWT from your OIDC provider, e.g. okta or auth0 or the like.
        We then use that JWT to issue an OAuth refresh token, that we then use to auth.
        
        :param client_id: The client ID
        :param client_secret: The client secret
        :param jwt: The JWT token
        """
        self.client_id = client_id
        self.__secret = client_secret
        self.__jwt = jwt
        self.__token = None
        self.__expires_at = None
        self.requires_request_body = False
    
    async def _get_access_token(self, request):
        """Get or refresh the access token"""
        url = httpx.URL(request.url)
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
        
        async with httpx.AsyncClient() as client:
            r = await client.post(token_url, headers=headers, data=data)
            
            if r.status_code != 200:
                raise AuthenticationException(f"Failed to get token: {r.text}")
            
            data = r.json()
            expires = int(time.time() + data['expires_in'])
            return data['access_token'], expires
    
    async def auth_flow(self, request):
        """Auth flow implementation for httpx.Auth"""
        if not self.__token or time.time() > self.__expires_at:
            self.__token, self.__expires_at = await self._get_access_token(request)
        
        request.headers['Authorization'] = f"Bearer {self.__token}"
        yield request
