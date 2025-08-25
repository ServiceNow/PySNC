import asyncio
import time
import unittest
from unittest import mock

# Adjust these imports to your repo structure
from pysnc.asyncio.auth import (
    AsyncServiceNowFlow,
    AsyncServiceNowPasswordGrantFlow,
    AsyncServiceNowJWTAuth,
)
from pysnc.exceptions import AuthenticationException


# ----------------------
# Test helpers / fakes
# ----------------------

class FakeHTTPXResponse:
    """Minimal stand-in for httpx.Response used by the code under test."""
    def __init__(self, status_code: int = 200, json_data=None, text: str = ""):
        self.status_code = status_code
        self._json_data = json_data or {}
        self.text = text

    def json(self):
        return self._json_data


class TestAsyncAuth(unittest.TestCase):
    """unittest.TestCase with a helper to run async coroutines."""

    def run_async(self, coro):
        return asyncio.get_event_loop().run_until_complete(coro)

    # ---------- Base flow ----------

    def test_base_flow_authenticate_raises(self):
        flow = AsyncServiceNowFlow()
        with self.assertRaises(AuthenticationException):
            self.run_async(flow.authenticate("https://instance"))

    # ---------- Password grant flow ----------

    def test_password_grant_flow_authorization_url(self):
        flow = AsyncServiceNowPasswordGrantFlow("u", "p", "cid", "secret")
        self.assertEqual(
            flow.authorization_url("https://example.service-now.com"),
            "https://example.service-now.com/oauth_token.do",
        )

    def test_password_grant_flow_accepts_tuple_username(self):
        # username as a tuple/list should set internal username/password from it
        flow = AsyncServiceNowPasswordGrantFlow(("user_tuple", "pass_tuple"), None, "cid", "secret")
        # Access the mangled attribute names to verify they were set correctly
        self.assertEqual(flow._AsyncServiceNowPasswordGrantFlow__password, "pass_tuple")

    def test_password_grant_flow_sets_secret(self):
        flow = AsyncServiceNowPasswordGrantFlow("user", "pass", "cid", "secret123")
        self.assertEqual(flow.client_id, "cid")
        # ensure secret is stored
        self.assertEqual(flow._AsyncServiceNowPasswordGrantFlow__secret, "secret123")

    def test_password_grant_success_sets_header_and_clears_password(self):
        # Mock AsyncClient.post to return a 200 with access_token
        token_payload = {"access_token": "tok123", "expires_in": 3600}
        fake_resp = FakeHTTPXResponse(status_code=200, json_data=token_payload)

        with mock.patch("httpx.AsyncClient.post", new=mock.AsyncMock(return_value=fake_resp)):
            flow = AsyncServiceNowPasswordGrantFlow("user", "pass", "cid", "secret")
            client = self.run_async(flow.authenticate("https://inst"))

            # Authorization header is set
            self.assertEqual(client.headers.get("Authorization"), "Bearer tok123")
            # password cleared
            self.assertIsNone(flow._AsyncServiceNowPasswordGrantFlow__password)

            # Close the client to avoid warnings
            self.run_async(client.aclose())

    def test_password_grant_non_200_raises(self):
        fake_resp = FakeHTTPXResponse(status_code=401, json_data={"error": "invalid"}, text="nope")
        with mock.patch("httpx.AsyncClient.post", new=mock.AsyncMock(return_value=fake_resp)):
            flow = AsyncServiceNowPasswordGrantFlow("user", "pass", "cid", "secret")
            with self.assertRaises(AuthenticationException):
                self.run_async(flow.authenticate("https://inst"))

    def test_password_grant_missing_access_token_raises(self):
        fake_resp = FakeHTTPXResponse(status_code=200, json_data={"not_access_token": "x"})
        with mock.patch("httpx.AsyncClient.post", new=mock.AsyncMock(return_value=fake_resp)):
            flow = AsyncServiceNowPasswordGrantFlow("user", "pass", "cid", "secret")
            with self.assertRaises(AuthenticationException):
                self.run_async(flow.authenticate("https://inst"))

    def test_password_grant_wrapped_request_error(self):
        # Simulate httpx.RequestError from the POST
        async def raise_request_error(*args, **kwargs):
            raise Exception("low-level")

        with mock.patch("httpx.AsyncClient.post", new=mock.AsyncMock(side_effect=raise_request_error)):
            flow = AsyncServiceNowPasswordGrantFlow("user", "pass", "cid", "secret")
            with self.assertRaises(AuthenticationException):
                self.run_async(flow.authenticate("https://inst"))

    # ---------- JWT auth (httpx.Auth) ----------

    def test_jwt_get_access_token_success(self):
        # Build a request whose URL controls where /oauth_token.do goes
        import httpx
        request = httpx.Request("GET", "https://foo.example/api/now/table/task")

        # access_token + expiry
        payload = {"access_token": "jwt_tok", "expires_in": 120}
        fake_resp = FakeHTTPXResponse(status_code=200, json_data=payload)

        with mock.patch("httpx.AsyncClient.post", new=mock.AsyncMock(return_value=fake_resp)):
            auth = AsyncServiceNowJWTAuth(client_id="cid", client_secret="sec", jwt="signed.jwt.here")

            # Call private to verify return values
            token, exp = self.run_async(auth._get_access_token(request))

            self.assertEqual(token, "jwt_tok")
            self.assertGreaterEqual(exp, int(time.time()))  # expiry is in the future

    def test_jwt_get_access_token_failure_raises(self):
        import httpx
        request = httpx.Request("GET", "https://foo.example/api/now/table/task")
        fake_resp = FakeHTTPXResponse(status_code=400, json_data={"error": "bad"}, text="bad")
        with mock.patch("httpx.AsyncClient.post", new=mock.AsyncMock(return_value=fake_resp)):
            auth = AsyncServiceNowJWTAuth(client_id="cid", client_secret="sec", jwt="jwt")
            with self.assertRaises(AuthenticationException):
                self.run_async(auth._get_access_token(request))

    def test_jwt_auth_flow_sets_header_and_refreshes(self):
        import httpx
        # First token response
        payload1 = {"access_token": "tok1", "expires_in": 1}
        # Second token (after expiry)
        payload2 = {"access_token": "tok2", "expires_in": 3600}
        calls = [
            FakeHTTPXResponse(status_code=200, json_data=payload1),
            FakeHTTPXResponse(status_code=200, json_data=payload2),
        ]

        async def post_side_effect(*args, **kwargs):
            return calls.pop(0)

        with mock.patch("httpx.AsyncClient.post", new=mock.AsyncMock(side_effect=post_side_effect)):
            auth = AsyncServiceNowJWTAuth(client_id="cid", client_secret="sec", jwt="jwt")

            # Build request and run the auth flow generator manually
            request = httpx.Request("GET", "https://foo.example/api/now/table/incident")
            agen = auth.auth_flow(request)

            # First yield (fetch tok1)
            req1 = self.run_async(agen.__anext__())
            self.assertEqual(req1.headers.get("Authorization"), "Bearer tok1")

            # Force expiry
            auth._AsyncServiceNowJWTAuth__expires_at = 0

            # Next yield (should refresh to tok2)
            agen = auth.auth_flow(request)
            req2 = self.run_async(agen.__anext__())
            self.assertEqual(req2.headers.get("Authorization"), "Bearer tok2")