# tests/asyncio/test_async_auth.py
from unittest import IsolatedAsyncioTestCase, skip

from pysnc.asyncio import AsyncServiceNowClient
from pysnc.asyncio.auth import AsyncServiceNowPasswordGrantFlow, AsyncServiceNowClientCredentialsFlow, AsyncServiceNowJWTAuth  # noqa: F401 (used in nop test)
from pysnc import exceptions
from ..constants import Constants


class TestAsyncAuth(IsolatedAsyncioTestCase):
    c = Constants()

    async def test_basic(self):
        client = AsyncServiceNowClient(self.c.server, self.c.credentials)
        try:
            gr = await client.GlideRecord('sys_user')
            print(gr.fields)
            gr.fields = 'sys_id'
            print(gr.fields)
            self.assertTrue(await gr.get('6816f79cc0a8016401c5a33be04be441'))
        finally:
            await client.session.aclose()

    async def test_basic_fail(self):
        client = AsyncServiceNowClient(self.c.server, ('admin', 'this is not a real password'))
        try:
            gr = await client.GlideRecord('sys_user')
            try:
                await gr.get('does not matter')
                self.fail('Exception should have been thrown')
            except exceptions.AuthenticationException as e:
                self.assertTrue('not authenticated' in str(e).lower())
                self.assertTrue('required to provide auth information' in str(e).lower())
            except Exception:
                self.fail('Should have got an Auth exception')
        finally:
            await client.session.aclose()

    @skip("Requires valid oauth client_id and secret, and I don't want to need anything not out of box")
    async def test_oauth(self):
        # Manual setup using legacy oauth (async)
        creds = self.c.credentials
        client_id = self.c.get_value('CLIENT_ID')
        secret = self.c.get_value('CLIENT_SECRET')

        flow = AsyncServiceNowPasswordGrantFlow(creds[0], creds[1], client_id, secret)
        # If your AsyncServiceNowClient accepts an httpx.AsyncClient, you can do:
        # headers = await flow.authenticate(self.c.server, verify=True)
        # client = httpx.AsyncClient(base_url=self.c.server, headers={"Accept": "application/json", **headers})
        # aclient = AsyncServiceNowClient(self.c.server, client)
        # Otherwise, if you wired flow support directly into AsyncServiceNowClient, use that instead.

        aclient = AsyncServiceNowClient(self.c.server, flow)  # only if your client supports flows
        try:
            gr = await aclient.GlideRecord('sys_user')
            gr.fields = 'sys_id'
            self.assertTrue(await gr.get('6816f79cc0a8016401c5a33be04be441'))
        finally:
            await aclient.session.aclose()

    @skip("Requires valid oauth client_id and secret for client credentials flow")
    async def test_client_credentials(self):
        """
        Test async OAuth2 Client Credentials Grant Flow.
        This flow only requires client_id and client_secret - no username/password needed.
        """
        client_id = self.c.get_value('CLIENT_ID')
        secret = self.c.get_value('CLIENT_SECRET')

        # Create client using client credentials flow
        flow = AsyncServiceNowClientCredentialsFlow(client_id, secret)
        aclient = AsyncServiceNowClient(self.c.server, flow)
        
        try:
            # Test basic query
            gr = await aclient.GlideRecord('sys_user')
            gr.fields = 'sys_id'
            self.assertTrue(await gr.get('6816f79cc0a8016401c5a33be04be441'))
        finally:
            await aclient.session.aclose()

    @skip("Requires valid oauth client_id and secret for client credentials flow")
    async def test_client_credentials_token_refresh(self):
        """
        Test that tokens are automatically refreshed when they expire (async).
        """
        import time
        
        client_id = self.c.get_value('CLIENT_ID')
        secret = self.c.get_value('CLIENT_SECRET')

        flow = AsyncServiceNowClientCredentialsFlow(client_id, secret)
        aclient = AsyncServiceNowClient(self.c.server, flow)
        
        try:
            # Make first request
            gr1 = await aclient.GlideRecord('sys_user')
            gr1.fields = 'sys_id'
            self.assertTrue(await gr1.get('6816f79cc0a8016401c5a33be04be441'))
            
            # Force token expiration by manipulating the flow's internal state
            flow._AsyncServiceNowClientCredentialsFlow__expires_at = time.time() - 100
            
            # Make second request - should automatically refresh token
            gr2 = await aclient.GlideRecord('sys_user')
            gr2.fields = 'sys_id'
            self.assertTrue(await gr2.get('6816f79cc0a8016401c5a33be04be441'))
        finally:
            await aclient.session.aclose()

    @skip("Requires valid oauth client_id and secret for client credentials flow")  
    async def test_client_credentials_invalid(self):
        """
        Test that invalid client credentials raise appropriate exceptions (async).
        """
        # Test with invalid credentials
        flow = AsyncServiceNowClientCredentialsFlow('invalid_client_id', 'invalid_secret')
        aclient = AsyncServiceNowClient(self.c.server, flow)
        
        try:
            with self.assertRaises(exceptions.AuthenticationException) as context:
                gr = await aclient.GlideRecord('sys_user')
                await gr.get('does not matter')
            
            # Check that error message is informative
            self.assertIn('access token', str(context.exception).lower())
        finally:
            await aclient.session.aclose()

    async def test_auth_param_check(self):
        with self.assertRaisesRegex(exceptions.AuthenticationException, r'Cannot specify both.+'):
            AsyncServiceNowClient('anyinstance', auth='asdf', cert='asdf')
        with self.assertRaisesRegex(exceptions.AuthenticationException, r'No valid auth.+'):
            AsyncServiceNowClient('anyinstance', auth='zzz')

    def nop_test_jwt(self):
        """
        we act as our own client here, which you should not do.

        Example async usage:

        auth = AsyncServiceNowJWTAuth(client_id, client_secret, jwt)
        client = AsyncServiceNowClient(self.c.server, auth)

        gr = await client.GlideRecord('sys_user')
        gr.fields = 'sys_id'
        assert await gr.get('6816f79cc0a8016401c5a33be04be441'), "did not jwt auth"
        """
        pass

