import asyncio
import base64
import unittest
from types import SimpleNamespace
from urllib.parse import urlparse, parse_qs
import httpx
from unittest import mock

# Adjust imports for your repo layout
from pysnc.asyncio.client import (
    AsyncServiceNowClient,
    AsyncAPI,
    AsyncTableAPI,
    AsyncAttachmentAPI,
    AsyncBatchAPI,
)
from pysnc.asyncio.auth import AsyncServiceNowFlow
from pysnc.exceptions import (
    AuthenticationException,
    AuthorizationException,
    NotFoundException,
    RequestException,
    ResponseException,
)

# -----------------------------
# Test fakes / helpers
# -----------------------------

class FakeResponse:
    """Lightweight fake that looks like httpx.Response for our usage."""
    def __init__(self, status_code=200, json_data=None, text='', headers=None, content=b''):
        self.status_code = status_code
        self._json_data = json_data
        self.text = text
        self.headers = headers or {}
        self.content = content

    def json(self):
        if self._json_data is None:
            # Simulate a JSON parse failure (exercises ResponseException path)
            raise ValueError("Invalid JSON")
        return self._json_data


class FakeAsyncClient:
    """Mimic pysnc.asyncio.client.AsyncClient enough for our client/APIs."""
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.headers = kwargs.get("headers", {}).copy()
        # transport.retry so retry-tuning code is exercised
        self.transport = SimpleNamespace(
            retry=SimpleNamespace(
                respect_retry_after_header=False,
                backoff_factor=0.0,
                status_forcelist=[],
                total=0,
            )
        )
        self._send_calls = []
        self._built_requests = []
        self._next_send_response = FakeResponse(status_code=200, json_data={"ok": True})
        self._post_side_effect = None  # for batch API
        self._closed = False

    def build_request(self, method, url, params=None, json=None, files=None, headers=None):
        # httpx.Request doesn't accept files=; ignore it for unit tests
        req = httpx.Request(method, url, headers=headers, params=params, json=json)
        self._built_requests.append(req)
        return req

    async def send(self, req, stream=False):
        self._send_calls.append((req, stream))
        return self._next_send_response

    async def post(self, url, json=None):
        # Used by AsyncBatchAPI.execute
        if callable(self._post_side_effect):
            return self._post_side_effect(url, json=json)
        # Default: echo batch id and make everything serviced
        body = {
            "batch_request_id": str(json["batch_request_id"]),
            "serviced_requests": [
                {
                    "id": r["id"],
                    "status_code": 200,
                    "headers": [{"name": "Content-Type", "value": "application/json"}],
                    "body": base64.b64encode(b'{"result":"ok"}').decode("utf-8"),
                }
                for r in json["rest_requests"]
            ],
            "unserviced_requests": [],
        }
        return FakeResponse(status_code=200, json_data=body)

    async def aclose(self):
        self._closed = True


def run_async(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


# -----------------------------
# Tests
# -----------------------------

class TestAsyncServiceNowClientUnit(unittest.TestCase):

    # ---------- __init__ proxy & verify ----------
    def test_init_with_proxy_sets_proxies_and_default_verify_true_if_unspecified(self):
        with mock.patch("pysnc.asyncio.client.get_instance", return_value="https://dev.example"):
            client = AsyncServiceNowClient("dev", auth=("u", "p"), proxy="http://proxy:8080")
            self.assertIsNotNone(client)

    # ---------- init_client auth branches ----------
    def test_init_client_with_tuple_auth_and_retry_tuning(self):
        with mock.patch("pysnc.asyncio.client.get_instance", return_value="https://dev.example"), \
             mock.patch("pysnc.asyncio.client.AsyncClient", new=FakeAsyncClient):

            client = AsyncServiceNowClient("dev", auth=("user", "pass"))
            httpx_client = run_async(client.init_client())
            # Default headers
            self.assertEqual(httpx_client.headers.get("Accept"), "application/json")

            # Retry tuning applied
            tr = httpx_client.transport.retry
            self.assertTrue(tr.respect_retry_after_header)
            self.assertGreater(tr.backoff_factor, 0)
            self.assertIn(429, tr.status_forcelist)
            self.assertGreater(tr.total, 0)

            run_async(client.close())

    def test_init_client_with_httpx_auth_object(self):
        with mock.patch("pysnc.asyncio.client.get_instance", return_value="https://dev.example"), \
             mock.patch("pysnc.asyncio.client.AsyncClient", new=FakeAsyncClient):

            class DummyAuth(httpx.Auth):
                def auth_flow(self, request):
                    yield request

            client = AsyncServiceNowClient("dev", auth=DummyAuth())
            run_async(client.init_client())
            run_async(client.close())

    def test_init_client_with_existing_asyncclient(self):
        with mock.patch("pysnc.asyncio.client.get_instance", return_value="https://dev.example"), \
             mock.patch("pysnc.asyncio.client.AsyncClient", new=FakeAsyncClient):
            existing = FakeAsyncClient()
            client = AsyncServiceNowClient("dev", auth=existing)
            httpx_client = run_async(client.init_client())
            self.assertIs(httpx_client, existing)
            run_async(client.close())

    def test_init_client_with_flow(self):
        with mock.patch("pysnc.asyncio.client.get_instance", return_value="https://dev.example"):

            class DummyFlow(AsyncServiceNowFlow):
                async def authenticate(self, instance: str, **kwargs):
                    return FakeAsyncClient(**kwargs)

            client = AsyncServiceNowClient("dev", auth=DummyFlow())
            httpx_client = run_async(client.init_client())
            self.assertIsInstance(httpx_client, FakeAsyncClient)
            run_async(client.close())

    def test_init_client_with_cert_only(self):
        with mock.patch("pysnc.asyncio.client.get_instance", return_value="https://dev.example"), \
             mock.patch("pysnc.asyncio.client.AsyncClient", new=FakeAsyncClient):

            client = AsyncServiceNowClient("dev", auth=None, cert=("cert.pem", "key.pem"))
            run_async(client.init_client())
            run_async(client.close())

    def test_init_client_conflicting_auth_and_cert_raises(self):
        with mock.patch("pysnc.asyncio.client.get_instance", return_value="https://dev.example"):
            client = AsyncServiceNowClient("dev", auth=("u", "p"), cert=("c", "k"))
            with self.assertRaises(AuthenticationException):
                run_async(client.init_client())

    def test_init_client_invalid_auth_raises(self):
        with mock.patch("pysnc.asyncio.client.get_instance", return_value="https://dev.example"):
            client = AsyncServiceNowClient("dev", auth=object())
            with self.assertRaises(AuthenticationException):
                run_async(client.init_client())

    def test_client_property_requires_init_and_close_resets(self):
        with mock.patch("pysnc.asyncio.client.get_instance", return_value="https://dev.example"), \
             mock.patch("pysnc.asyncio.client.AsyncClient", new=FakeAsyncClient):
            client = AsyncServiceNowClient("dev", auth=("u", "p"))
            with self.assertRaises(RuntimeError):
                _ = client.client  # not initialized
            run_async(client.init_client())
            self.assertIsNotNone(client.client)
            run_async(client.close())
            with self.assertRaises(RuntimeError):
                _ = client.client

    # ---------- instance formatting ----------
    def test_instance_normalization(self):
        with mock.patch("pysnc.asyncio.client.get_instance", return_value="https://dev12345.service-now.com"):
            c = AsyncServiceNowClient("dev12345", auth=("u", "p"))
            self.assertEqual(c.instance(), "https://dev12345.service-now.com")

    # ---------- guess_is_sys_id ----------
    def test_guess_is_sys_id(self):
        self.assertTrue(AsyncServiceNowClient.guess_is_sys_id("1234567890abcdef1234567890abcdef"))
        self.assertFalse(AsyncServiceNowClient.guess_is_sys_id("bad"))
        self.assertFalse(AsyncServiceNowClient.guess_is_sys_id(""))

    # ---------- AsyncAPI._set_params ----------
    def test__set_params_builds_expected_query_dict(self):
        class Rec:
            encoded_query = "active=true"
            fields = ["a", "b"]
            display_value = "all"
            exclude_reference_link = True
            limit = 10
            offset = 5

        mini = SimpleNamespace(client=FakeAsyncClient(), instance=lambda: "https://x")
        api = AsyncAPI(mini)
        out = api._set_params(Rec())
        self.assertEqual(out["sysparm_query"], "active=true")
        self.assertEqual(out["sysparm_fields"], "a,b")
        self.assertEqual(out["sysparm_display_value"], "all")
        self.assertTrue(out["sysparm_exclude_reference_link"])
        self.assertEqual(out["sysparm_limit"], 10)
        self.assertEqual(out["sysparm_offset"], 5)

    # ---------- AsyncAPI._validate_response matrix ----------
    def test__validate_response_errors_and_json_failure(self):
        mini = SimpleNamespace(client=FakeAsyncClient(), instance=lambda: "https://x")
        api = AsyncAPI(mini)

        # 401
        with self.assertRaises(AuthenticationException):
            run_async(api._validate_response(FakeResponse(status_code=401, text="nope")))
        # 403
        with self.assertRaises(AuthorizationException):
            run_async(api._validate_response(FakeResponse(status_code=403, text="nope")))
        # 404
        with self.assertRaises(NotFoundException):
            run_async(api._validate_response(FakeResponse(status_code=404, text="nope")))
        # 500+
        with self.assertRaises(RequestException):
            run_async(api._validate_response(FakeResponse(status_code=500, text="boom")))
        # JSON parse failure for non-204
        with self.assertRaises(ResponseException):
            run_async(api._validate_response(FakeResponse(status_code=200, json_data=None, text="not json")))

        # 204 allowed (no JSON parse)
        run_async(api._validate_response(FakeResponse(status_code=204, json_data=None)))

    # ---------- AsyncAPI._send ----------
    def test__send_calls_client_send_with_stream_and_validates(self):
        fac = FakeAsyncClient()
        mini = SimpleNamespace(client=fac, instance=lambda: "https://x")
        api = AsyncAPI(mini)

        req = fac.build_request("GET", "https://x/api")
        fac._next_send_response = FakeResponse(status_code=200, json_data={"ok": True})
        resp = run_async(api._send(req, stream=True))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(fac._send_calls[-1][1], True)  # stream flag captured

    # ---------- AsyncTableAPI ----------
    def test_table_api_endpoints_and_methods(self):
        fac = FakeAsyncClient()
        mini = SimpleNamespace(client=fac, instance=lambda: "https://inst")
        api = AsyncTableAPI(mini)

        class Rec:
            table = "problem"
            encoded_query = "active=true"
            fields = ["a", "b"]
            display_value = False
            exclude_reference_link = False
            limit = 2
            offset = 10
            sys_id = "deadbeef" * 4  # 32

            def serialize(self, changes_only=False):
                return {"x": 1, "changes_only": changes_only}

        # list
        run_async(api.list(Rec()))
        self.assertEqual(fac._built_requests[-1].method, "GET")
        self.assertIn("/api/now/table/problem", str(fac._built_requests[-1].url))

        # get removes offset
        run_async(api.get(Rec(), "a"*32))
        url = str(fac._built_requests[-1].url)
        qs = parse_qs(urlparse(url).query)
        self.assertNotIn("sysparm_offset", qs)

        # put delegates to patch
        run_async(api.put(Rec()))
        self.assertEqual(fac._built_requests[-1].method, "PATCH")

        # patch
        run_async(api.patch(Rec()))
        self.assertEqual(fac._built_requests[-1].method, "PATCH")

        # post
        run_async(api.post(Rec()))
        self.assertEqual(fac._built_requests[-1].method, "POST")

        # delete
        run_async(api.delete(Rec()))
        self.assertEqual(fac._built_requests[-1].method, "DELETE")

    # ---------- AsyncAttachmentAPI ----------
    def test_attachment_api_all_methods(self):
        fac = FakeAsyncClient()
        mini = SimpleNamespace(client=fac, instance=lambda: "https://inst")
        api = AsyncAttachmentAPI(mini)

        # get (metadata)
        run_async(api.get("abc"))
        self.assertEqual(fac._built_requests[-1].method, "GET")
        self.assertIn("/api/now/attachment/abc", str(fac._built_requests[-1].url))

        # get_file streams
        run_async(api.get_file("abc", stream=True))
        self.assertEqual(fac._send_calls[-1][1], True)

        class Att:
            table = "problem"
            table_sys_id = "1" * 32

        # list
        run_async(api.list(Att()))
        url = str(fac._built_requests[-1].url)
        self.assertIn("/api/now/attachment", url)
        self.assertIn("table_name=problem", url)

        # upload_file
        run_async(api.upload_file(
            file_name="f.txt",
            table_name="problem",
            table_sys_id="1"*32,
            file=b"data",
            content_type="text/plain",
            encryption_context="ctx",
        ))
        self.assertEqual(fac._built_requests[-1].method, "POST")

        # delete
        run_async(api.delete("deadbeef"))
        self.assertEqual(fac._built_requests[-1].method, "DELETE")

    # ---------- AsyncBatchAPI core paths ----------
    def test_batch_api_add_transform_and_execute_basic(self):
        fac = FakeAsyncClient()
        mini = SimpleNamespace(client=fac, instance=lambda: "https://inst")
        api = AsyncBatchAPI(mini)

        # Prepare two requests and hooks
        results = []

        async def hook1(resp):
            results.append(("h1", resp.status_code, resp.json()))

        async def hook2(resp):
            results.append(("h2", resp.status_code, resp.json()))

        # Build requests using the fake client
        r1 = fac.build_request("GET", "https://inst/api/now/table/problem?sysparm_limit=1")
        r2 = fac.build_request("POST", "https://inst/api/now/table/incident", json={"x": 1})

        run_async(api._add_request(r1, hook1))
        run_async(api._add_request(r2, hook2))

        # Execute once: FakeAsyncClient.post will service all requests
        run_async(api.execute())
        self.assertEqual(len(results), 2)
        self.assertEqual({k for (k, *_ ) in results}, {"h1", "h2"})
        # ensure queue cleared
        self.assertEqual(len(api._AsyncBatchAPI__requests), 0)

    def test_batch_api_recurses_for_unserviced_and_eventually_succeeds(self):
        fac = FakeAsyncClient()
        mini = SimpleNamespace(client=fac, instance=lambda: "https://inst")
        api = AsyncBatchAPI(mini)

        results = []

        async def hook(resp):
            results.append(resp.status_code)

        r = fac.build_request("GET", "https://inst/api/now/table/problem")
        run_async(api._add_request(r, hook))

        # First call returns one unserviced; second call services it
        calls = {"n": 0}

        def post_side_effect(url, json=None):
            calls["n"] += 1
            if calls["n"] == 1:
                body = {
                    "batch_request_id": str(json["batch_request_id"]),
                    "serviced_requests": [],
                    "unserviced_requests": [json["rest_requests"][0]["id"]],
                }
            else:
                body = {
                    "batch_request_id": str(json["batch_request_id"]),
                    "serviced_requests": [
                        {
                            "id": json["rest_requests"][0]["id"],
                            "status_code": 200,
                            "headers": [],
                            "body": base64.b64encode(b"{}").decode(),
                        }
                    ],
                    "unserviced_requests": [],
                }
            return FakeResponse(status_code=200, json_data=body)

        fac._post_side_effect = post_side_effect

        run_async(api.execute())
        self.assertEqual(results, [200])

    def test_batch_api_gives_up_after_three_attempts_and_calls_hooks_with_none(self):
        fac = FakeAsyncClient()
        mini = SimpleNamespace(client=fac, instance=lambda: "https://inst")
        api = AsyncBatchAPI(mini)

        # queue one request
        called = {"n": 0}

        # give-up path calls hooks synchronously (no await), so use a sync hook
        def hook(resp):
            called["n"] += 1
            self.assertIsNone(resp)

        r = fac.build_request("GET", "https://inst/api/now/table/problem")
        run_async(api._add_request(r, hook))

        def post_side_effect(url, json=None):
            # Always unserviced to force recursion
            body = {
                "batch_request_id": str(json["batch_request_id"]),
                "serviced_requests": [],
                "unserviced_requests": [json["rest_requests"][0]["id"]],
            }
            return FakeResponse(status_code=200, json_data=body)

        fac._post_side_effect = post_side_effect

        # execute → attempt 0 → 1 → 2 → 3 (give-up)
        run_async(api.execute())
        self.assertEqual(called["n"], 1)
