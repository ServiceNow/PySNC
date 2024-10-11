from io import BytesIO

import requests
from requests.auth import AuthBase
import re
import logging
import base64
from typing import Callable, no_type_check

from requests.cookies import MockRequest, MockResponse
from requests.structures import CaseInsensitiveDict
from requests.utils import get_encoding_from_headers
from requests.adapters import HTTPAdapter, Retry

from .exceptions import *
from .record import GlideRecord
from .attachment import Attachment
from .utils import get_instance, MockHeaders
from .auth import ServiceNowFlow


class ServiceNowClient(object):
    """
    ServiceNow Python Client

    :param str instance: The instance to connect to e.g. ``https://dev00000.service-now.com`` or ``dev000000``
    :param auth: Username password combination ``(name,pass)`` or :class:`pysnc.ServiceNowOAuth2` or ``requests.sessions.Session`` or ``requests.auth.AuthBase`` object
    :param proxy: HTTP(s) proxy to use as a str ``'http://proxy:8080`` or dict ``{'http':'http://proxy:8080'}``
    :param bool verify: Verify the SSL/TLS certificate OR the certificate to use. Useful if you're using a self-signed HTTPS proxy.
    :param cert: if String, path to ssl client cert file (.pem). If Tuple, (‘cert’, ‘key’) pair.
    """
    def __init__(self, instance, auth, proxy=None, verify=None, cert=None, auto_retry=True):
        self._log = logging.getLogger(__name__)
        self.__instance = get_instance(instance)

        if proxy:
            if type(proxy) != dict:
                proxies = dict(http=proxy, https=proxy)
            else:
                proxies = proxy
            self.__proxies = proxies
            if verify is None:
                verify = True  # default to verify with proxy
        else:
            self.__proxies = None


        if auth is not None and cert is not None:
            raise AuthenticationException('Cannot specify both auth and cert')
        elif isinstance(auth, (list, tuple)) and len(auth) == 2:
            self.__user = auth[0]
            auth = requests.auth.HTTPBasicAuth(auth[0], auth[1])

            self.__session = requests.session()
            self.__session.auth = auth
        elif isinstance(auth, AuthBase):
            self.__session = requests.session()
            self.__session.auth = auth
        elif isinstance(auth, requests.sessions.Session):
            # maybe we've got an oauth token? Let this be permissive
            self.__session = auth
        elif isinstance(auth, ServiceNowFlow):
            self.__session = auth.authenticate(self.__instance, proxies=self.__proxies, verify=verify)
        elif cert is not None:
            self.__session.cert = cert
        else:
            raise AuthenticationException('No valid authentication method provided')

        if proxy:
            self.__session.proxies = self.__proxies

        if verify is not None:
            self.__session.verify = verify

        self.__session.headers.update(dict(Accept="application/json"))

        if auto_retry is True:
            # https://urllib3.readthedocs.io/en/latest/reference/urllib3.util.html#module-urllib3.util.retry
            retry = Retry(total=4, backoff_factor=0.2, status_forcelist=[429, 500, 502, 503])
            self.__session.mount(self.__instance, HTTPAdapter(max_retries=retry))

        self.table_api = TableAPI(self)
        self.attachment_api = AttachmentAPI(self)
        self.batch_api = BatchAPI(self)

    def GlideRecord(self, table, batch_size=100, rewindable=True) -> GlideRecord:
        """
        Create a :class:`pysnc.GlideRecord` for a given table against the current client

        :param str table: The table name e.g. ``problem``
        :param int batch_size: Batch size (items returned per HTTP request). Default is ``100``.
        :param bool rewindable: If we can rewind the record. Default is ``True``. If ``False`` then we cannot rewind 
                                the record, which means as an Iterable this object will be 'spent' after iteration.
                                This is normally the default behavior expected for a python Iterable, but not a GlideRecord.
                                When ``False`` less memory will be consumed, as each previous record will be collected.
        :return: :class:`pysnc.GlideRecord`
        """
        return GlideRecord(self, table, batch_size, rewindable)

    def Attachment(self, table) -> Attachment:
        """
        Create an Attachment object for the current client

        :return: :class:`pysnc.Attachment`
        """
        return Attachment(self, table)

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

    @staticmethod
    def guess_is_sys_id(value) -> bool:
        """
        Attempt to guess if this is a probable sys_id

        :param str value: the value to check
        :return: If this is probably a sys_id
        :rtype: bool
        """
        return re.match(r'^[A-Za-z0-9]{32}$', value) is not None


class API(object):

    def __init__(self, client):
        self._client = client

    @property
    def session(self):
        return self._client.session

    # noinspection PyMethodMayBeStatic
    def _set_params(self, record=None):
        params = {} if record is None else record._parameters()
        if 'sysparm_display_value' not in params:
            params['sysparm_display_value'] = 'all'
        if 'sysparm_exclude_reference_link' not in params:
            params['sysparm_exclude_reference_link'] = 'true'  # Scratch it!, by default
        params['sysparm_suppress_pagination_header'] = 'true'  # Required for large queries
        return params

    # noinspection PyMethodMayBeStatic
    def _validate_response(self, response: requests.Response) -> None:
        assert response is not None, f"response argument required"
        code = response.status_code
        if code >= 400:
            try:
                rjson = response.json()
                if code == 404:
                    raise NotFoundException(rjson)
                if code == 403:
                    raise RoleException(rjson)
                if code == 401:
                    raise AuthenticationException(rjson)
                raise RequestException(rjson)
            except requests.exceptions.JSONDecodeError:
                raise RequestException(response.text)

    def _send(self, req, stream=False) -> requests.Response:
        # https://stackoverflow.com/a/55889308/253594
        # if we're oauth, we have to do magic for prepared requests

        if hasattr(self.session, 'token'):
            try:
                req.url, req.headers, req.data = self.session._client.add_token(
                    req.url, http_method=req.method, body=req.data, headers=req.headers
                )
            except Exception as e:
                if e.__class__.__name__ == 'TokenExpiredError':
                    # use refresh token to get new token
                    if self.session.auto_refresh_url:
                        if hasattr(req, 'auth'):
                            req.auth = None
                        self.session.refresh_token(self.session.auto_refresh_url)
                    else:
                        raise e
                else:
                    raise e

        request = self.session.prepare_request(req)
        # Merge environment settings into session
        settings = self.session.merge_environment_settings(request.url, {}, stream, None, None)
        r = self.session.send(request, **settings)
        self._validate_response(r)
        return r


class TableAPI(API):

    def _target(self, table, sys_id=None) -> str:
        target = "{url}/api/now/table/{table}".format(url=self._client.instance, table=table)
        if sys_id:
            target = "{}/{}".format(target, sys_id)
        return target

    def list(self, record: GlideRecord) -> requests.Response:
        params = self._set_params(record)
        target_url = self._target(record.table)

        req = requests.Request('GET', target_url, params=params)
        return self._send(req)

    def get(self, record: GlideRecord, sys_id: str) -> requests.Response:
        params = self._set_params(record)
        # delete extra stuff
        if 'sysparm_offset' in params:
            del params['sysparm_offset']

        target_url = self._target(record.table, sys_id)
        req = requests.Request('GET', target_url, params=params)
        return self._send(req)

    def put(self, record: GlideRecord) -> requests.Response:
        return self.patch(record)

    def patch(self, record: GlideRecord) -> requests.Response:
        body = record.serialize(changes_only=True)
        params = self._set_params()
        target_url = self._target(record.table, record.sys_id)
        req = requests.Request('PATCH', target_url, params=params, json=body)
        return self._send(req)

    def post(self, record: GlideRecord) -> requests.Response:
        body = record.serialize()
        params = self._set_params()
        target_url = self._target(record.table)
        req = requests.Request('POST', target_url, params=params, json=body)
        return self._send(req)

    def delete(self, record: GlideRecord) -> requests.Response:
        target_url = self._target(record.table, record.sys_id)
        req = requests.Request('DELETE', target_url)
        return self._send(req)


class AttachmentAPI(API):
    API_VERSION = 'v1'

    def _target(self, sys_id=None):
        target = "{url}/api/now/{version}/attachment".format(url=self._client.instance, version=self.API_VERSION)
        if sys_id:
            target = "{}/{}".format(target, sys_id)
        return target

    def get(self, sys_id=None):
        target_url = self._target(sys_id)
        req = requests.Request('GET', target_url, params={})
        return self._send(req)

    def get_file(self, sys_id, stream=True):
        """
        This may be dangerous, as stream is true and if not fully read could leave open handles
        One should always ``with api.get_file(sys_id) as f:``
        """
        target_url = "{}/file".format(self._target(sys_id))
        req = requests.Request('GET', target_url)
        return self._send(req, stream=stream)

    def list(self, attachment: Attachment):
        params = self._set_params(attachment)
        url = self._target()
        req = requests.Request('GET', url, params=params, headers=dict(Accept="application/json"))
        return self._send(req)

    def upload_file(self, file_name, table_name, table_sys_id, file, content_type=None, encryption_context=None):
        url = f"{self._target()}/file"
        params = {'file_name': file_name, 'table_name': table_name, 'table_sys_id': f"{table_sys_id}"}
        if encryption_context:
            params['encryption_context'] = encryption_context

        if not content_type:
            content_type = 'application/octet-stream'
        headers = {'Content-Type': content_type}

        req = requests.Request('POST', url, params=params, headers=headers, data=file)
        return self._send(req)

    def delete(self, sys_id):
        target_url = self._target(sys_id)
        req = requests.Request('DELETE', target_url)
        return self._send(req)


class BatchAPI(API):
    API_VERSION = 'v1'

    def __init__(self, client):
        API.__init__(self, client)
        self.__requests = []
        self.__stored_requests = {}
        self.__hooks = {}
        self.__request_id = 0

    def _batch_target(self):
        return "{url}/api/now/{version}/batch".format(url=self._client.instance, version=self.API_VERSION)

    def _table_target(self, table, sys_id=None):
        # note: the instance is still in here so requests behaves normally when preparing requests
        target = "{url}/api/now/table/{table}".format(url=self._client.instance, table=table)
        if sys_id:
            target = "{}/{}".format(target, sys_id)
        return target

    def _next_id(self):
        self.__request_id += 1
        return self.__request_id

    def _add_request(self, request: requests.Request, hook: Callable):
        prepared = request.prepare()
        request_id = str(id(prepared))
        headers = [{'name': k, 'value': v} for (k,v) in prepared.headers.items()]
        relative_url = prepared.url[prepared.url.index('/', 8):]  # type: ignore ## slice from the first non https:// slash

        now_request = {
            'id': request_id,
            'method': prepared.method,
            'url': relative_url,
            'headers': headers,
            #'exclude_response_headers': False
        }
        if prepared.body:
            now_request['body'] = base64.b64encode(prepared.body).decode()  # type: ignore ## could theoretically do us dirty
        self.__hooks[request_id] = hook
        self.__stored_requests[request_id] = prepared
        self.__requests.append(now_request)

    @no_type_check
    def _transform_response(self, req: requests.PreparedRequest, serviced_request) -> requests.Response:
        # modeled after requests.adapters.HttpAdapter.build_response
        response = requests.Response()
        response.status_code = serviced_request['status_code']
        headers = {k: v for (k, v) in [(e['name'], e['value']) for e in serviced_request.get("headers", [])]}
        response.headers = CaseInsensitiveDict(headers)
        response.encoding = get_encoding_from_headers(response.headers)

        body = base64.b64decode(serviced_request.get('body', ''))
        response.raw = BytesIO(body)

        if isinstance(req.url, bytes):
            response.url = req.url.decode("utf-8")
        else:
            response.url = req.url  # type: ignore

        # cookies - kinda hack an adapter in
        req = MockRequest(req)
        res = MockResponse(MockHeaders(headers))
        response.cookies.extract_cookies(res, req)

        response.request = req
        # response.connection = None

        return response

    def execute(self, attempt=0):
        if attempt > 2:
            # just give up and tell em we tried
            for h in self.__hooks:
                self.__hooks[h](None)
            self.__hooks = {}
            self.__requests = []
            self.__stored_requests = {}
        bid = self._next_id()
        body = {
            'batch_request_id': bid,
            'rest_requests': self.__requests
        }
        r = self.session.post(self._batch_target(), json=body)
        self._validate_response(r)
        data = r.json()
        assert str(bid) == data['batch_request_id'], f"How did we get a response id different from {bid}"

        for response in data['serviced_requests']:
            response_id = response['id']
            assert response_id in self.__hooks, f"Somehow has no hook for {response_id}"
            assert response_id in self.__stored_requests, f"Somehow we did not store request for {response_id}"
            self.__hooks[response['id']](self._transform_response(self.__stored_requests.pop(response_id), response))
            del self.__hooks[response_id]
            self.__requests = list(filter(lambda x: x['id'] != response_id, self.__requests))

        if len(data['unserviced_requests']) > 0:
            self.execute(attempt=attempt+1)

    def get(self, record: GlideRecord, sys_id: str, hook: Callable) -> None:
        params = self._set_params(record)
        if 'sysparm_offset' in params:
            del params['sysparm_offset']
        target_url = self._table_target(record.table, sys_id)
        req = requests.Request('GET', target_url, params=params)
        self._add_request(req, hook)

    def put(self, record: GlideRecord, hook: Callable) -> None:
        self.patch(record, hook)

    def patch(self, record: GlideRecord, hook: Callable) -> None:
        body = record.serialize(changes_only=True)
        params = self._set_params()
        target_url = self._table_target(record.table, record.sys_id)
        req = requests.Request('PATCH', target_url, params=params, json=body)
        self._add_request(req, hook)

    def post(self, record: GlideRecord, hook: Callable):
        body = record.serialize()
        params = self._set_params()
        target_url = self._table_target(record.table)
        req = requests.Request('POST', target_url, params=params, json=body)
        self._add_request(req, hook)

    def delete(self, record: GlideRecord, hook: Callable):
        target_url = self._table_target(record.table, record.sys_id)
        req = requests.Request('DELETE', target_url)
        self._add_request(req, hook)

    def list(self, record: GlideRecord, hook: Callable):
        params = self._set_params(record)
        target_url = self._table_target(record.table)

        req = requests.Request('GET', target_url, params=params)
        self._add_request(req, hook)
