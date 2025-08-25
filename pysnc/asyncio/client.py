"""
Asynchronous ServiceNow client implementation using httpx.AsyncClient.
"""

from io import BytesIO
import httpx
import re
import logging
import base64
import asyncio
from typing import Callable, Dict, List, Optional, Any, Union, no_type_check

from httpx import AsyncClient, Response, Request
from urllib3.util import Retry

from ..exceptions import *
from .record import AsyncGlideRecord
from .attachment import AsyncAttachment
from ..utils import get_instance, MockHeaders
from .auth import AsyncServiceNowFlow


class AsyncServiceNowClient:
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
        self.__client = None
        self.__proxies = None
        self.__auth = None
        self.__verify = verify
        self.__cert = cert

        if proxy:
            if type(proxy) != dict:
                proxies = dict(http=proxy, https=proxy)
            else:
                proxies = proxy
            self.__proxies = proxies
            if verify is None:
                verify = True  # default to verify with proxy
        
        self.__verify = verify

        # Store auth for later client initialization
        self.__auth_params = (auth, cert)
        
        self.table_api = AsyncTableAPI(self)
        self.attachment_api = AsyncAttachmentAPI(self)
        self.batch_api = AsyncBatchAPI(self)

    async def init_client(self):
        """
        Initialize the httpx AsyncClient. This must be called before making any requests.
        """
        auth, cert = self.__auth_params
        
        if auth is not None and cert is not None:
            raise AuthenticationException('Cannot specify both auth and cert')
        
        # Create base client with common settings
        client_params = {
            "verify": self.__verify,
            "headers": {"Accept": "application/json"}
        }
        
        if self.__proxies:
            client_params["transport"] = httpx.AsyncHTTPTransport(proxies=self.__proxies)
        
        try:
            if isinstance(auth, tuple) and len(auth) == 2:
                self.__user = auth[0]
                client_params["auth"] = (auth[0], auth[1])
                self.__client = AsyncClient(**client_params)
            elif isinstance(auth, httpx.Auth):
                client_params["auth"] = auth
                self.__client = AsyncClient(**client_params)
            elif isinstance(auth, AsyncClient):
                # maybe we've got an oauth token? Let this be permissive
                self.__client = auth
            elif isinstance(auth, AsyncServiceNowFlow):
                # Make sure authenticate returns a valid client
                client = await auth.authenticate(
                    self.__instance, 
                    proxies=self.__proxies, 
                    verify=self.__verify
                )
                if client is None:
                    raise AuthenticationException('Authentication flow returned None instead of a client')
                self.__client = client
            elif cert is not None:
                client_params["cert"] = cert
                self.__client = AsyncClient(**client_params)
            else:
                raise AuthenticationException('No valid authentication method provided')
        except Exception as e:
            raise AuthenticationException(f'Failed to initialize client: {str(e)}')

        # Ensure we have a valid client
        if self.__client is None:
            raise AuthenticationException('Client initialization failed, client is None')

        # Add limits and retries
        if hasattr(self.__client, "transport") and hasattr(self.__client.transport, "retry"):
            self.__client.transport.retry.respect_retry_after_header = True
            self.__client.transport.retry.backoff_factor = 0.2
            self.__client.transport.retry.status_forcelist = [429, 500, 502, 503]
            self.__client.transport.retry.total = 4

        return self.__client

    async def GlideRecord(self, table, batch_size=100, rewindable=True) -> 'AsyncGlideRecord':
        """
        Create a :class:`pysnc.async.AsyncGlideRecord` for a given table against the current client

        :param str table: The table name e.g. ``problem``
        :param int batch_size: Batch size (items returned per HTTP request). Default is ``100``.
        :param bool rewindable: If we can rewind the record. Default is ``True``. If ``False`` then we cannot rewind 
                                the record, which means as an Iterable this object will be 'spent' after iteration.
                                When ``False`` less memory will be consumed, as each previous record will be collected.
        :return: :class:`pysnc.async.AsyncGlideRecord`
        """
        if self.__client is None:
            await self.init_client()
        return AsyncGlideRecord(self, table, batch_size, rewindable)

    async def Attachment(self, table) -> 'AsyncAttachment':
        """
        Create an AsyncAttachment object for the current client

        :return: :class:`pysnc.async.AsyncAttachment`
        """
        if self.__client is None:
            await self.init_client()
        return AsyncAttachment(self, table)

    def instance(self) -> str:
        """
        The instance we're associated with.

        :return: Instance URI
        :rtype: str
        """
        return self.__instance

    @property
    def client(self) -> AsyncClient:
        """
        :return: The httpx AsyncClient
        """
        if self.__client is None:
            raise RuntimeError("AsyncClient not initialized. Call init_client() first.")
        return self.__client
        
    async def close(self) -> None:
        """
        Close the httpx AsyncClient and release resources.
        This should be called when the client is no longer needed.
        """
        if self.__client is not None:
            await self.__client.aclose()
            self.__client = None

    @staticmethod
    def guess_is_sys_id(value) -> bool:
        """
        Attempt to guess if this is a probable sys_id

        :param str value: the value to check
        :return: If this is probably a sys_id
        :rtype: bool
        """
        if not value:
            return False
        if len(value) != 32:
            return False
        return bool(re.match(r'^[a-f0-9]{32}$', value))


class AsyncAPI:
    def __init__(self, client: AsyncServiceNowClient):
        self._client = client

    @property
    def client(self) -> AsyncClient:
        return self._client.client

    def _set_params(self, record=None) -> Dict[str, Any]:
        params = {}
        if record is not None:
            if record.encoded_query:
                params['sysparm_query'] = record.encoded_query
            if record.fields:
                params['sysparm_fields'] = ','.join(record.fields)
            if record.display_value:
                params['sysparm_display_value'] = record.display_value
            if record.exclude_reference_link:
                params['sysparm_exclude_reference_link'] = record.exclude_reference_link
            if record.limit:
                params['sysparm_limit'] = record.limit
            if record.offset:
                params['sysparm_offset'] = record.offset
        return params

    async def _validate_response(self, response: Response) -> None:
        if response.status_code == 401:
            raise AuthenticationException(f"Authentication failed: {response.text}")
        if response.status_code == 403:
            raise AuthorizationException(f"Authorization failed: {response.text}")
        if response.status_code == 404:
            raise NotFoundException(f"Not found: {response.text}")
        if response.status_code >= 400:
            raise RequestException(f"Request failed with status code {response.status_code}: {response.text}")
        
        # Ensure we have a valid response
        if response.status_code != 204:  # No content is valid
            try:
                response.json()
            except Exception as e:
                raise ResponseException(f"Failed to parse response as JSON: {e}")

    async def _send(self, req: Request, stream=False) -> Response:
        response = await self.client.send(req, stream=stream)
        await self._validate_response(response)
        return response


class AsyncTableAPI(AsyncAPI):
    async def _target(self, table, sys_id=None) -> str:
        base = f"{self._client.instance()}/api/now/table/{table}"
        if sys_id:
            return f"{base}/{sys_id}"
        return base

    async def list(self, record: 'AsyncGlideRecord') -> Response:
        params = self._set_params(record)
        target_url = await self._target(record.table)
        req = self.client.build_request("GET", target_url, params=params)
        return await self._send(req)

    async def get(self, record: 'AsyncGlideRecord', sys_id: str) -> Response:
        params = self._set_params(record)
        if 'sysparm_offset' in params:
            del params['sysparm_offset']
        target_url = await self._target(record.table, sys_id)
        req = self.client.build_request("GET", target_url, params=params)
        return await self._send(req)

    async def put(self, record: 'AsyncGlideRecord') -> Response:
        return await self.patch(record)

    async def patch(self, record: 'AsyncGlideRecord') -> Response:
        body = record.serialize(changes_only=True)
        params = self._set_params()
        target_url = await self._target(record.table, record.sys_id)
        req = self.client.build_request("PATCH", target_url, params=params, json=body)
        return await self._send(req)

    async def post(self, record: 'AsyncGlideRecord') -> Response:
        body = record.serialize()
        params = self._set_params()
        target_url = await self._target(record.table)
        req = self.client.build_request("POST", target_url, params=params, json=body)
        return await self._send(req)

    async def delete(self, record: 'AsyncGlideRecord') -> Response:
        target_url = await self._target(record.table, record.sys_id)
        req = self.client.build_request("DELETE", target_url)
        return await self._send(req)


class AsyncAttachmentAPI(AsyncAPI):
    API_VERSION = 'v1'

    async def _target(self, sys_id=None) -> str:
        base = f"{self._client.instance()}/api/now/attachment"
        if sys_id:
            return f"{base}/{sys_id}"
        return base

    async def get(self, sys_id=None) -> Response:
        target_url = await self._target(sys_id)
        req = self.client.build_request("GET", target_url)
        return await self._send(req)

    async def get_file(self, sys_id, stream=True) -> Response:
        """
        This may be dangerous, as stream is true and if not fully read could leave open handles
        One should always ``async with api.get_file(sys_id) as f:``
        """
        target_url = f"{await self._target(sys_id)}/file"
        req = self.client.build_request("GET", target_url)
        return await self._send(req, stream=stream)

    async def list(self, attachment: 'AsyncAttachment') -> Response:
        params = {
            'table_name': attachment.table,
            'table_sys_id': attachment.table_sys_id
        }
        target_url = await self._target()
        req = self.client.build_request("GET", target_url, params=params)
        return await self._send(req)

    async def upload_file(self, file_name, table_name, table_sys_id, file, content_type=None, encryption_context=None) -> Response:
        target_url = await self._target()
        
        headers = {}
        if content_type:
            headers['Content-Type'] = content_type
        
        params = {
            'table_name': table_name,
            'table_sys_id': table_sys_id,
            'file_name': file_name
        }
        
        if encryption_context:
            params['encryption_context'] = encryption_context
        
        files = {'file': (file_name, file, content_type)}
        
        # Using httpx's files parameter for multipart form data
        req = self.client.build_request("POST", target_url, params=params, files=files, headers=headers)
        return await self._send(req)

    async def delete(self, sys_id) -> Response:
        target_url = await self._target(sys_id)
        req = self.client.build_request("DELETE", target_url)
        return await self._send(req)


class AsyncBatchAPI(AsyncAPI):
    def __init__(self, client):
        super().__init__(client)
        self.__requests = []
        self.__stored_requests = {}
        self.__hooks = {}
        self.__id = 0

    def _next_id(self) -> int:
        self.__id += 1
        return self.__id

    def _batch_target(self) -> str:
        return f"{self._client.instance()}/api/now/v1/batch"

    async def _add_request(self, req: Request, hook: Callable) -> None:
        prepared = req
        request_id = str(self._next_id())
        
        # Convert httpx Request to the format expected by ServiceNow batch API
        now_request = {
            'id': request_id,
            'url': str(prepared.url),
            'method': prepared.method,
        }
        
        # Add headers if present
        if prepared.headers:
            now_request['headers'] = [{'name': k, 'value': v} for k, v in prepared.headers.items()]
        
        # Add body if present
        if prepared.content:
            now_request['body'] = base64.b64encode(prepared.content).decode('utf-8')
        
        self.__hooks[request_id] = hook
        self.__stored_requests[request_id] = prepared
        self.__requests.append(now_request)

    @no_type_check
    async def _transform_response(self, req: Request, serviced_request) -> Response:
        # Create a new Response object
        response = Response(
            status_code=serviced_request['status_code'],
            headers={e['name']: e['value'] for e in serviced_request.get("headers", [])},
            content=base64.b64decode(serviced_request.get('body', '')),
            request=req
        )
        return response

    async def execute(self, attempt=0) -> None:
        if attempt > 2:
            # just give up and tell em we tried
            for h in self.__hooks:
                self.__hooks[h](None)
            self.__hooks = {}
            self.__requests = []
            self.__stored_requests = {}
            return
            
        bid = self._next_id()
        body = {
            'batch_request_id': bid,
            'rest_requests': self.__requests
        }
        
        r = await self.client.post(self._batch_target(), json=body)
        await self._validate_response(r)
        data = r.json()
        assert str(bid) == data['batch_request_id'], f"How did we get a response id different from {bid}"

        for response in data['serviced_requests']:
            response_id = response['id']
            assert response_id in self.__hooks, f"Somehow has no hook for {response_id}"
            assert response_id in self.__stored_requests, f"Somehow we did not store request for {response_id}"
            
            transformed_response = await self._transform_response(
                self.__stored_requests.pop(response_id), 
                response
            )
            
            await self.__hooks[response['id']](transformed_response)
            del self.__hooks[response_id]
            self.__requests = [req for req in self.__requests if req['id'] != response_id]

        if len(data['unserviced_requests']) > 0:
            await self.execute(attempt=attempt+1)

    async def get(self, record: 'AsyncGlideRecord', sys_id: str, hook: Callable) -> None:
        params = self._set_params(record)
        if 'sysparm_offset' in params:
            del params['sysparm_offset']
        target_url = await self._target(record.table, sys_id)
        req = self.client.build_request("GET", target_url, params=params)
        await self._add_request(req, hook)

    async def put(self, record: 'AsyncGlideRecord', hook: Callable) -> None:
        await self.patch(record, hook)

    async def patch(self, record: 'AsyncGlideRecord', hook: Callable) -> None:
        body = record.serialize(changes_only=True)
        params = self._set_params()
        target_url = await self._target(record.table, record.sys_id)
        req = self.client.build_request("PATCH", target_url, params=params, json=body)
        await self._add_request(req, hook)

    async def post(self, record: 'AsyncGlideRecord', hook: Callable) -> None:
        body = record.serialize()
        params = self._set_params()
        target_url = await self._target(record.table)
        req = self.client.build_request("POST", target_url, params=params, json=body)
        await self._add_request(req, hook)

    async def delete(self, record: 'AsyncGlideRecord', hook: Callable) -> None:
        target_url = await self._target(record.table, record.sys_id)
        req = self.client.build_request("DELETE", target_url)
        await self._add_request(req, hook)

    async def list(self, record: 'AsyncGlideRecord', hook: Callable) -> None:
        params = self._set_params(record)
        target_url = await self._target(record.table)
        req = self.client.build_request("GET", target_url, params=params)
        await self._add_request(req, hook)
