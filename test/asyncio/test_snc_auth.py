import asyncio
import os
import json
from unittest import TestCase, mock

import pytest
import httpx
import jwt

from pysnc.asyncio import AsyncServiceNowJWTAuth, AsyncServiceNowPasswordGrantFlow
from ..constants import Constants


class TestAsyncServiceNowAuth(TestCase):
    c = Constants()

    @pytest.mark.asyncio
    async def test_password_grant_flow(self):
        """Test the password grant flow authentication"""
        # Mock the token response
        mock_token_response = httpx.Response(
            status_code=200,
            json={
                "access_token": "mock_access_token",
                "refresh_token": "mock_refresh_token",
                "token_type": "Bearer",
                "expires_in": 3600
            }
        )
        
        # Create a mock for the AsyncClient
        with mock.patch('httpx.AsyncClient.post', return_value=mock_token_response):
            auth_flow = AsyncServiceNowPasswordGrantFlow(
                username=self.c.credentials[0],
                password=self.c.credentials[1],
                client_id="test_client_id",
                client_secret="test_client_secret"
            )
            
            client = await auth_flow.authenticate(self.c.server)
            
            # Verify the client has the correct auth headers
            self.assertIsNotNone(client)
            self.assertEqual(client.headers.get('Authorization'), 'Bearer mock_access_token')
            
            # Close the client
            await client.aclose()

    @pytest.mark.asyncio
    async def test_jwt_auth(self):
        """Test the JWT authentication"""
        # Create a mock JWT token
        private_key = """
        -----BEGIN PRIVATE KEY-----
        MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQC7VJTUt9Us8cKj
        MzEfYyjiWA4R4/M2bS1GB4t7NXp98C3SC6dVMvDuictGeurT8jNbvJZHtCSuYEvu
        NMoSfm76oqFvAp8Gy0iz5sxjZmSnXyCdPEovGhLa0VzMaQ8s+CLOyS56YyCFGeJZ
        agLQnJYi+zrwLXZUWPt8yvbPzJY/X/5LkWQtQjr1/y+aIQ4jeFTUU8oITGQ4Hc9h
        kxjMbJOTw4Xr9i3pJjBYNAOh0jWNxAKMVXiYoUJfgBJrr6lTcAUlIEW5rt3UTcR/
        TYRaOADMi5ZtOjLq9Vu6XBjBwEJRl/WrRFseEWS2HGtNAUgj9WQ2X5+DPuSXvzTc
        9wuLAgMBAAECggEADEEwgkjZfFDR84lWoztFXKDcZgrGDmDkI0ozpr4/t6mhIKSn
        0lxNYY2FiDS0cjU3ck52sZ6xCCwTTxLQP+ZZsXpBcbLjQJgJZ7Bw7vOhJqdUy2Ri
        vBpt7HfFzA8MuSEMvvj5bzjZ9JO1P7q2xzpxSqz66UsjKZ9SqyWPCqKZQAXBTVwk
        nqc6dAnGWzCkzGQCiPAZLwZGzGmwIyN8ENBEsKGAzHCKDQzSCy1NPWyFoh/UT8At
        u+F5MZQcmHj+JcY0hEWGLdY7Jz7HB8HLzWRASPLTxQDgr6QQ2VfDXFSrhOLfFPbG
        xHGpJDHZYvs0Vl7Xtx0T0xpKXVGW2MrGBzlKgQKBgQDyR6qUE+7rXJ7fJVqc8rqh
        7y9Dz1M6XeZyU5wPzWfQlkuMiC0WuNKBlFHIWpG4J6WvmXQkYXPmPBUUfJ2/5Epa
        cVMqQdAI+bLjG7q4Fkmuw5e5hJxCgJJ2uNE+DmTGmNHQ5JoIiUK2Ah9QvCjNLjVj
        WKwK4+5XQWqRE2NvAJDFIQKBgQDGQs7FRTisHV0xooiRmlvYF0UFgL/nUPNBEgOE
        GDjHxNXNUEw/VzSOBgFxUpGTnSvhBbQTvGQJHBeRfS/WaA9k1RAqUOkbC0NSU+JB
        +hjXwNy4+6RCxM0YIXgJSWyC/YYAOqZu5Rz1FPLYzBV2bEH6YW2a3ERnIHNJ+Qct
        GXOXawKBgCKVxuIoZRQY4/9WCnmDx6mzZ9c+zKkJqoLZ1r/KdD0FvbhcHqMDvKDU
        KbTQYlBzODUVBxRIGkqgNIQxNJVZGNyXnDEZTHJMCJwBpMa/ev/PMdQxQ0sBb+Oq
        OvYvz+9QGOyDEZu0ZRFNnuJiIAK5iMYi9eSj7COO1FPIt+QlN0/BAoGAcQN2aKTF
        WBjBjQ2LYn1gNjojBoMNkMGjh+3jQQqN5wIciTXhIPQa+xu34t1pqS0tJSI7V+ew
        JbFJOLjQrX7Jrva7QG2mRLzLwWJu+Fy5Wjeo6zbXmJVcWQ9gshesKe/DzYVpuwoE
        Jjy/78q3rL/WYI4bSz60speJ0eJCE7TH1ikCgYEArXgGT5IoYav8RoYCUGwYDgxj
        VSXbKp0C5KJGGk0aPZP/VqP8ZZxPkxLgwFHrCXv4KY+tLKRKFVUmGLKKGl7CuYPj
        K0OQTWWlJoXsrtEWQVGGAw5z7NuXzF0M4LEYk5uFhOPkiXKvQZe3lNfSPn3YSETA
        TCZ+k0hpxqQlUXpOWGE=
        -----END PRIVATE KEY-----
        """
        
        # Mock the token response
        mock_token_response = httpx.Response(
            status_code=200,
            json={
                "access_token": "mock_access_token",
                "refresh_token": "mock_refresh_token",
                "token_type": "Bearer",
                "expires_in": 3600
            }
        )
        
        # Create a JWT auth instance
        jwt_auth = AsyncServiceNowJWTAuth(
            client_id="test_client_id",
            private_key=private_key,
            user=self.c.credentials[0]
        )
        
        # Mock the token request
        with mock.patch('httpx.AsyncClient.post', return_value=mock_token_response):
            # Create a mock request
            request = httpx.Request("GET", f"{self.c.server}/api/now/table/incident")
            
            # Apply auth to the request
            await jwt_auth(request)
            
            # Verify the request has the correct auth header
            self.assertEqual(request.headers.get('Authorization'), 'Bearer mock_access_token')
            
            # Test token refresh
            jwt_auth._token_expiry = 0  # Force token refresh
            
            # Apply auth again to trigger refresh
            await jwt_auth(request)
            
            # Verify the request has the correct auth header after refresh
            self.assertEqual(request.headers.get('Authorization'), 'Bearer mock_access_token')

    @pytest.mark.asyncio
    async def test_jwt_auth_token_generation(self):
        """Test JWT token generation"""
        private_key = """
        -----BEGIN PRIVATE KEY-----
        MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQC7VJTUt9Us8cKj
        MzEfYyjiWA4R4/M2bS1GB4t7NXp98C3SC6dVMvDuictGeurT8jNbvJZHtCSuYEvu
        NMoSfm76oqFvAp8Gy0iz5sxjZmSnXyCdPEovGhLa0VzMaQ8s+CLOyS56YyCFGeJZ
        agLQnJYi+zrwLXZUWPt8yvbPzJY/X/5LkWQtQjr1/y+aIQ4jeFTUU8oITGQ4Hc9h
        kxjMbJOTw4Xr9i3pJjBYNAOh0jWNxAKMVXiYoUJfgBJrr6lTcAUlIEW5rt3UTcR/
        TYRaOADMi5ZtOjLq9Vu6XBjBwEJRl/WrRFseEWS2HGtNAUgj9WQ2X5+DPuSXvzTc
        9wuLAgMBAAECggEADEEwgkjZfFDR84lWoztFXKDcZgrGDmDkI0ozpr4/t6mhIKSn
        0lxNYY2FiDS0cjU3ck52sZ6xCCwTTxLQP+ZZsXpBcbLjQJgJZ7Bw7vOhJqdUy2Ri
        vBpt7HfFzA8MuSEMvvj5bzjZ9JO1P7q2xzpxSqz66UsjKZ9SqyWPCqKZQAXBTVwk
        nqc6dAnGWzCkzGQCiPAZLwZGzGmwIyN8ENBEsKGAzHCKDQzSCy1NPWyFoh/UT8At
        u+F5MZQcmHj+JcY0hEWGLdY7Jz7HB8HLzWRASPLTxQDgr6QQ2VfDXFSrhOLfFPbG
        xHGpJDHZYvs0Vl7Xtx0T0xpKXVGW2MrGBzlKgQKBgQDyR6qUE+7rXJ7fJVqc8rqh
        7y9Dz1M6XeZyU5wPzWfQlkuMiC0WuNKBlFHIWpG4J6WvmXQkYXPmPBUUfJ2/5Epa
        cVMqQdAI+bLjG7q4Fkmuw5e5hJxCgJJ2uNE+DmTGmNHQ5JoIiUK2Ah9QvCjNLjVj
        WKwK4+5XQWqRE2NvAJDFIQKBgQDGQs7FRTisHV0xooiRmlvYF0UFgL/nUPNBEgOE
        GDjHxNXNUEw/VzSOBgFxUpGTnSvhBbQTvGQJHBeRfS/WaA9k1RAqUOkbC0NSU+JB
        +hjXwNy4+6RCxM0YIXgJSWyC/YYAOqZu5Rz1FPLYzBV2bEH6YW2a3ERnIHNJ+Qct
        GXOXawKBgCKVxuIoZRQY4/9WCnmDx6mzZ9c+zKkJqoLZ1r/KdD0FvbhcHqMDvKDU
        KbTQYlBzODUVBxRIGkqgNIQxNJVZGNyXnDEZTHJMCJwBpMa/ev/PMdQxQ0sBb+Oq
        OvYvz+9QGOyDEZu0ZRFNnuJiIAK5iMYi9eSj7COO1FPIt+QlN0/BAoGAcQN2aKTF
        WBjBjQ2LYn1gNjojBoMNkMGjh+3jQQqN5wIciTXhIPQa+xu34t1pqS0tJSI7V+ew
        JbFJOLjQrX7Jrva7QG2mRLzLwWJu+Fy5Wjeo6zbXmJVcWQ9gshesKe/DzYVpuwoE
        Jjy/78q3rL/WYI4bSz60speJ0eJCE7TH1ikCgYEArXgGT5IoYav8RoYCUGwYDgxj
        VSXbKp0C5KJGGk0aPZP/VqP8ZZxPkxLgwFHrCXv4KY+tLKRKFVUmGLKKGl7CuYPj
        K0OQTWWlJoXsrtEWQVGGAw5z7NuXzF0M4LEYk5uFhOPkiXKvQZe3lNfSPn3YSETA
        TCZ+k0hpxqQlUXpOWGE=
        -----END PRIVATE KEY-----
        """
        
        jwt_auth = AsyncServiceNowJWTAuth(
            client_id="test_client_id",
            private_key=private_key,
            user=self.c.credentials[0]
        )
        
        # Generate a JWT token
        token = jwt_auth._generate_jwt()
        
        # Decode the token to verify its contents
        decoded = jwt.decode(token, options={"verify_signature": False})
        
        # Verify token claims
        self.assertEqual(decoded['iss'], "test_client_id")
        self.assertEqual(decoded['sub'], self.c.credentials[0])
        self.assertIn('exp', decoded)
        self.assertIn('iat', decoded)
