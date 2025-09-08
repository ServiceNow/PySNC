"""
Asynchronous ServiceNow client implementation using httpx.AsyncClient.
"""

from __future__ import annotations

import base64
import json
import logging
from typing import Any, Callable, Dict, Mapping, Optional

import httpx
from httpx import Auth as HTTPXAuth
from httpx import URL

from ..client import API, ServiceNowClient
from ..exceptions import *
from ..utils import get_instance
from .attachment import AsyncAttachment
from .auth import AsyncServiceNowFlow
from .record import AsyncGlideRecord

JSONHeaders = Mapping[str, str]


class AsyncServiceNowClient(ServiceNowClient):
    """
    Asynchronous ServiceNow Python Client

    :param str instance: The instance to connect to e.g. ``https://dev00000.service-now.com`` or ``dev000000``
    :param auth: Username password combination ``(name,pass)`` or :class:`pysnc.async.AsyncServiceNowOAuth2` or ``httpx.AsyncClient`` or ``httpx.Auth`` object
    :param proxy: HTTP(s) proxy to use as a str ``'http://proxy:8080`` or dict ``{'http':'http://proxy:8080'}``
    :param bool verify: Verify the SSL/TLS certificate OR the certificate to use. Useful if you're using a self-signed HTTPS proxy.
    :param cert: if String, path to ssl client cert file (.pem). If Tuple, ('cert', 'key') pair.
    """

    def __init__(self, instance, auth, proxy=None, verify=None, cert=None, auto_retry=True):
        self._log = logging.getLogger(__name__)
        self.__instance = get_instance(instance)

        self.__proxy_url = None
        if proxy:
            if isinstance(proxy, dict):
                http_url = proxy.get("http")
                https_url = proxy.get("https", http_url)
                # If they differ, choose https (or raise if you prefer strictness)
                if https_url and http_url and https_url != http_url:
                    # Pick https to be conservative. Alternatively, raise.
                    chosen = https_url
                else:
                    chosen = https_url or http_url
                self.__proxy_url = chosen
            else:
                self.__proxy_url = proxy
            if verify is None:
                verify = True  # default to verify with proxy

        if auth is not None and cert is not None:
            raise AuthenticationException("Cannot specify both auth and cert")

        self.__session: Optional[httpx.AsyncClient] = None
        headers: JSONHeaders = {"Accept": "application/json"}
        self.credentials = auth

        if isinstance(auth, (list, tuple)) and len(auth) == 2:
            # basic auth
            self.__session = httpx.AsyncClient(
                auth=(auth[0], auth[1]),
                headers=headers,
                verify=verify if verify is not None else True,
                cert=cert,
                proxy=self.__proxy_url,
                base_url=self.__instance,
                timeout=5.0,
                follow_redirects=True,
            )
        elif isinstance(auth, (HTTPXAuth, httpx.Auth)):
            self.__session = httpx.AsyncClient(
                auth=auth,
                headers=headers,
                verify=verify if verify is not None else True,
                cert=cert,
                proxy=self.__proxy_url,
                base_url=self.__instance,
                timeout=5.0,
                follow_redirects=True,
            )
        elif isinstance(auth, httpx.AsyncClient):
            # Caller supplied a preconfigured async client
            self.__session = auth
            # best-effort header merge
            self.__session.headers.update(headers)
        elif isinstance(auth, AsyncServiceNowFlow):  # accept either, adapt
            raise NotImplementedError("AsyncServiceNowFlow is not supported yet for async client")
        elif cert is not None:
            # cert-only client (no auth)
            self.__session = httpx.AsyncClient(
                headers=headers,
                verify=verify if verify is not None else True,
                cert=cert,
                proxy=self.__proxy_url,
                base_url=self.__instance,
                timeout=60.0,
                follow_redirects=True,
            )
        else:
            raise AuthenticationException("No valid authentication method provided")

        self.table_api = AsyncTableAPI(self)
        self.attachment_api = AsyncAttachmentAPI(self)
        self.batch_api = AsyncBatchAPI(self)

    async def GlideRecord(self, table, batch_size=100, rewindable=True) -> "AsyncGlideRecord": # type: ignore[override]
        """
        Create a :class:`pysnc.async.AsyncGlideRecord` for a given table against the current client

        :param str table: The table name e.g. ``problem``
        :param int batch_size: Batch size (items returned per HTTP request). Default is ``100``.
        :param bool rewindable: If we can rewind the record. Default is ``True``. If ``False`` then we cannot rewind
                                the record, which means as an Iterable this object will be 'spent' after iteration.
                                When ``False`` less memory will be consumed, as each previous record will be collected.
        :return: :class:`pysnc.async.AsyncGlideRecord`
        """
        return AsyncGlideRecord(self, table, batch_size, rewindable)

    async def Attachment(self, table) -> "AsyncAttachment": # type: ignore[override]
        """
        Create an AsyncAttachment object for the current client

        :return: :class:`pysnc.async.AsyncAttachment`
        """
        return AsyncAttachment(self, table)

    async def close(self) -> None:
        """
        Close the httpx AsyncClient and release resources.
        This should be called when the client is no longer needed.
        """
        if self.__session is not None:
            await self.__session.aclose()
            self.__session = None

    @property
    def instance(self) -> str:
        """
        The instance we're associated with.

        :return: Instance URI
        :rtype: str
        """
        return self.__instance

    @property
    def session(self):
        """
        :return: The requests session
        """
        return self.__session


class AsyncAPI(API):
    def __init__(self, client):
        super().__init__(client)

    # noinspection PyMethodMayBeStatic
    def _validate_response(self, response: httpx.Response) -> None:  # type: ignore[override]
        assert response is not None, "response argument required"
        code = response.status_code
        if code >= 400:
            # Try to decode JSON error bodies similarly to requests version
            try:
                rjson = response.json()
            except (ValueError, json.JSONDecodeError):
                # httpx raises ValueError on bad JSON
                raise RequestException(response.text)

            if code == 404:
                raise NotFoundException(rjson)
            if code == 403:
                raise RoleException(rjson)
            if code == 401:
                raise AuthenticationException(rjson)
            raise RequestException(rjson)

    async def _send(self, req: httpx.Request, stream: bool = False) -> httpx.Response: # type: ignore[override]
        """
        Async port of API._send.

        Accepts either:
          - an httpx.Request
          - an object shaped like requests.Request (with .method/.url/.headers/.data/.json/.files)
        Performs best-effort OAuth token injection (parity with original),
        builds an httpx request, sends it, validates, and returns the response.
        """
        # ----- OAuth token handling (best-effort parity with original) -----
        # If your token flow attaches attributes to the client (e.g., .token, ._client.add_token),
        # keep the same behavior guarded by hasattr().
        if hasattr(self.session, "token"):
            try:
                # Emulate: req.url, req.headers, req.data = self.session._client.add_token(...)
                if hasattr(self._client, "_client") and hasattr(self._client._client, "add_token"):
                    # Prepare inputs for add_token from the req-like object
                    method = getattr(req, "method", None)
                    url = getattr(req, "url", None)
                    headers = getattr(req, "headers", None) or {}
                    body = getattr(req, "data", None)
                    url, headers, body = self._client._client.add_token(  # type: ignore[attr-defined]
                        url, http_method=method, body=body, headers=headers
                    )
                    # Reflect updates back onto req if it is mutable
                    if hasattr(req, "url"):
                        req.url = url
                    if hasattr(req, "headers"):
                        req.headers = headers
                    if hasattr(req, "data"):
                        req.data = body
            except Exception as e:  # mirror original logic
                if e.__class__.__name__ == "TokenExpiredError":
                    # use refresh token to get new token
                    if getattr(self.session, "auto_refresh_url", None):
                        if hasattr(req, "auth"):
                            req.auth = None
                        refresh = getattr(self.session, "refresh_token", None)
                        if callable(refresh):
                            refresh(self.session.auto_refresh_url)
                    else:
                        raise
                else:
                    raise

        # ----- Build an httpx.Request from the input -----
        if isinstance(req, httpx.Request):
            request = req
        else:
            method = getattr(req, "method", "GET")
            url = getattr(req, "url", "")
            headers = getattr(req, "headers", None)
            json_payload = getattr(req, "json", None)
            data_payload = getattr(req, "data", None) if json_payload is None else None
            files_payload = getattr(req, "files", None)
            params_payload = getattr(req, "params", None)
            auth_payload = getattr(req, "auth", None)

            request = self.session.build_request(
                method=method,
                url=url,
                headers=headers,
                params=params_payload,
                json=json_payload,
                data=data_payload,
                files=files_payload,
                auth=auth_payload,
            )

        # ----- Send -----
        # httpx supports streaming via stream=True; the returned Response can be consumed with aiter_*.
        resp = await self.session.send(request, stream=stream, follow_redirects=True)
        self._validate_response(resp)
        return resp


class AsyncTableAPI(AsyncAPI):
    def _target(self, table: str, sys_id: Optional[str] = None) -> str:
        target = "{url}/api/now/table/{table}".format(url=self._client.instance, table=table)
        if sys_id:
            target = "{}/{}".format(target, sys_id)
        return target

    async def list(self, record) -> httpx.Response:
        params = self._set_params(record)
        target_url = self._target(record.table)

        req = httpx.Request("GET", target_url, params=params)
        return await self._send(req)

    async def get(self, record, sys_id: str) -> httpx.Response:
        params = self._set_params(record)
        params.pop("sysparm_offset", None)

        target_url = self._target(record.table, sys_id)
        req = httpx.Request("GET", target_url, params=params)

        return await self._send(req)

    async def put(self, record) -> httpx.Response:
        # keep aliasing behavior exactly like the sync version
        return await self.patch(record)

    async def patch(self, record) -> httpx.Response:
        body = record.serialize(changes_only=True)
        params = self._set_params()
        target_url = self._target(record.table, record.sys_id)
        req = httpx.Request("PATCH", target_url, params=params, json=body)
        return await self._send(req)

    async def post(self, record) -> httpx.Response:
        body = record.serialize()
        params = self._set_params()
        target_url = self._target(record.table)
        req = httpx.Request("POST", target_url, params=params, json=body)
        return await self._send(req)

    async def delete(self, record) -> httpx.Response:
        target_url = self._target(record.table, record.sys_id)
        req = httpx.Request("DELETE", target_url)
        return await self._send(req)


class AsyncAttachmentAPI(AsyncAPI):
    API_VERSION = "v1"

    def _target(self, sys_id: Optional[str] = None) -> str:
        target = "{url}/api/now/{version}/attachment".format(url=self._client.instance, version=self.API_VERSION)
        if sys_id:
            target = "{}/{}".format(target, sys_id)
        return target

    async def get(self, sys_id: Optional[str] = None) -> httpx.Response:
        target_url = self._target(sys_id)
        req = httpx.Request("GET", target_url, params={})
        return await self._send(req)

    async def get_file(self, sys_id: str, stream: bool = True) -> httpx.Response:
        """
        This may be dangerous, as stream is true and if not fully read could leave open handles
        One should always ``with api.get_file(sys_id) as f:``
        """
        target_url = "{}/file".format(self._target(sys_id))
        req = httpx.Request("GET", target_url)
        return await self._send(req, stream=stream)

    async def list(self, attachment) -> httpx.Response:
        params = self._set_params(attachment)
        url = self._target()
        req = httpx.Request("GET", url, params=params, headers=dict(Accept="application/json"))
        return await self._send(req)

    async def upload_file(
        self,
        file_name: str,
        table_name: str,
        table_sys_id: str,
        file: bytes,
        content_type: Optional[str] = None,
        encryption_context: Optional[str] = None,
    ) -> httpx.Response:
        url = f"{self._target()}/file"
        params: Dict[str, Any] = {
            "file_name": file_name,
            "table_name": table_name,
            "table_sys_id": f"{table_sys_id}",
        }
        if encryption_context:
            params["encryption_context"] = encryption_context

        if not content_type:
            content_type = "application/octet-stream"
        headers = {"Content-Type": content_type}

        req = httpx.Request("POST", url, params=params, headers=headers, content=file)
        return await self._send(req)

    async def delete(self, sys_id: str) -> httpx.Response:
        target_url = self._target(sys_id)
        req = httpx.Request("DELETE", target_url)
        return await self._send(req)


class AsyncBatchAPI(AsyncAPI):
    API_VERSION = "v1"

    def __init__(self, client):
        super().__init__(client)
        self.__requests = []
        self.__stored_requests = {}
        self.__hooks = {}
        self.__request_id = 0

    def _batch_target(self) -> str:
        return "{url}/api/now/{version}/batch".format(url=self._client.instance, version=self.API_VERSION)

    def _table_target(self, table: str, sys_id: Optional[str] = None) -> str:
        # note: the instance is still in here so requests behaves normally when preparing requests
        target = "{url}/api/now/table/{table}".format(url=self._client.instance, table=table)
        if sys_id:
            target = "{}/{}".format(target, sys_id)
        return target

    def _next_id(self) -> int:
        self.__request_id += 1
        return self.__request_id

    def _add_request(self, request: httpx.Request, hook: Callable[[Optional[httpx.Response]], None]) -> None:
        """
        Build a batchable representation of an httpx.Request.

        Mirrors the original behavior which used requests.PreparedRequest,
        but adapted to httpx (auth headers are not applied until send time,
        so we merge session headers + request headers here).
        """

        # Best-effort OAuth token injection parity (like in AsyncAPI._send)
        if hasattr(self.session, "token"):
            try:
                if hasattr(self.session, "_client") and hasattr(self.session._client, "add_token"):
                    method = request.method
                    token_url_str = str(request.url)
                    headers = dict(request.headers)
                    body = request.content if request.content is not None else None
                    token_url_str, headers, body = self.session._client.add_token(  # type: ignore[attr-defined]
                        token_url_str, http_method=method, body=body, headers=headers
                    )
                    request = httpx.Request(method=method, url=token_url_str, headers=headers, content=body)

            except Exception as e:
                if e.__class__.__name__ == "TokenExpiredError":
                    if getattr(self.session, "auto_refresh_url", None):
                        refresh = getattr(self.session, "refresh_token", None)
                        if callable(refresh):
                            refresh(self.session.auto_refresh_url)
                    else:
                        raise
                else:
                    raise

        # Merge session default headers (e.g., Accept, auth) with per-request headers
        merged_headers = dict(self.session.headers)
        merged_headers.update(request.headers)

        req_url: URL = request.url  # httpx.URL

        # Always get a str path
        path: str = getattr(req_url, "path", "")
        if not isinstance(path, str):
            # Fallback just in case stubs/types say bytes
            path = getattr(req_url, "raw_path", b"").decode()

        # Always get a str query
        raw_q = getattr(req_url, "raw_query", None)
        if isinstance(raw_q, (bytes, bytearray)):
            query: str = raw_q.decode()
        else:
            query = getattr(req_url, "query", "") or ""

        relative_url = path + (f"?{query}" if query else "")

        request_id = str(id(request))

        now_request: Dict[str, Any] = {
            "id": request_id,
            "method": request.method,
            "url": relative_url,
            "headers": [{"name": k, "value": v} for (k, v) in merged_headers.items()],
            # "exclude_response_headers": False,
        }

        if request.content:
            now_request["body"] = base64.b64encode(request.content).decode()

        self.__hooks[request_id] = hook
        self.__stored_requests[request_id] = request
        self.__requests.append(now_request)

    def _transform_response(self, req: httpx.Request, serviced_request: Dict[str, Any]) -> httpx.Response:
        """
        Build an httpx.Response from the batch serviced_request payload.
        Parity with the original behavior (which constructed a requests.Response).
        """
        status_code = serviced_request["status_code"]
        headers_list = serviced_request.get("headers", [])
        headers = {h["name"]: h["value"] for h in headers_list}

        body_b64 = serviced_request.get("body", "")
        content = base64.b64decode(body_b64) if body_b64 else b""

        # Create httpx.Response with the originating request
        response = httpx.Response(
            status_code=status_code,
            headers=headers,
            content=content,
            request=req,
        )
        return response

    async def execute(self, attempt: int = 0) -> None:
        if attempt > 2:
            # just give up and tell em we tried
            for h in list(self.__hooks.keys()):
                try:
                    self.__hooks[h](None)
                except Exception:
                    pass
            self.__hooks = {}
            self.__requests = []
            self.__stored_requests = {}
            return

        bid = self._next_id()
        body = {
            "batch_request_id": bid,
            "rest_requests": self.__requests,
        }

        r = await self.session.post(self._batch_target(), json=body, follow_redirects=True)
        self._validate_response(r)

        data = r.json()
        assert str(bid) == data["batch_request_id"], f"How did we get a response id different from {bid}"

        for response in data.get("serviced_requests", []):
            response_id = response["id"]
            assert response_id in self.__hooks, f"Somehow has no hook for {response_id}"
            assert response_id in self.__stored_requests, f"Somehow we did not store request for {response_id}"

            hook = self.__hooks.pop(response_id)
            orig_req = self.__stored_requests.pop(response_id)
            try:
                hook(self._transform_response(orig_req, response))
            finally:
                # remove from queue
                self.__requests = [x for x in self.__requests if x["id"] != response_id]

        if len(data.get("unserviced_requests", [])) > 0:
            await self.execute(attempt=attempt + 1)

    # -------- enqueue helpers (same signatures, no I/O) --------

    def get(self, record, sys_id: str, hook: Callable[[Optional[httpx.Response]], None]) -> None:
        params = self._set_params(record)
        if "sysparm_offset" in params:
            del params["sysparm_offset"]
        target_url = self._table_target(record.table, sys_id)
        req = httpx.Request("GET", target_url, params=params)
        self._add_request(req, hook)

    def put(self, record, hook: Callable[[Optional[httpx.Response]], None]) -> None:
        self.patch(record, hook)

    def patch(self, record, hook: Callable[[Optional[httpx.Response]], None]) -> None:
        body = record.serialize(changes_only=True)
        params = self._set_params()
        target_url = self._table_target(record.table, record.sys_id)
        req = httpx.Request("PATCH", target_url, params=params, json=body)
        self._add_request(req, hook)

    def post(self, record, hook: Callable[[Optional[httpx.Response]], None]) -> None:
        body = record.serialize()
        params = self._set_params()
        target_url = self._table_target(record.table)
        req = httpx.Request("POST", target_url, params=params, json=body)
        self._add_request(req, hook)

    def delete(self, record, hook: Callable[[Optional[httpx.Response]], None]) -> None:
        target_url = self._table_target(record.table, record.sys_id)
        req = httpx.Request("DELETE", target_url)
        self._add_request(req, hook)

    def list(self, record, hook: Callable[[Optional[httpx.Response]], None]) -> None:
        params = self._set_params(record)
        target_url = self._table_target(record.table)
        req = httpx.Request("GET", target_url, params=params)
        self._add_request(req, hook)
