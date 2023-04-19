import requests
from requests.auth import AuthBase
import re
import logging
from .exceptions import *
from .record import GlideRecord
from .attachment import Attachment
from .utils import get_instance
from .auth import ServiceNowOAuth2


class ServiceNowClient(object):
    """
    ServiceNow Python Client

    :param str instance: The instance to connect to e.g. ``https://dev00000.service-now.com`` or ``dev000000``
    :param auth: Username password combination ``(name,pass)`` or :class:`pysnc.ServiceNowOAuth2` or ``requests.sessions.Session`` or ``requests.auth.AuthBase`` object
    :param proxy: HTTP(s) proxy to use as a str ``'http://proxy:8080`` or dict ``{'http':'http://proxy:8080'}``
    :param bool verify: Verify the SSL/TLS certificate. Useful if you're using a self-signed HTTPS proxy.
    """
    def __init__(self, instance, auth, proxy=None, verify=True):
        self._log = logging.getLogger(__name__)
        self.__instance = get_instance(instance)

        if isinstance(auth, (list, tuple)) and len(auth) == 2:
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
        elif isinstance(auth, ServiceNowOAuth2):
            self.__session = auth.authenticate(self.__instance)
        else:
            raise AuthenticationException('No valid authentication method provided')

        if proxy:
            if type(proxy) != dict:
                proxies = dict(http=proxy, https=proxy)
            else:
                proxies = proxy
            self.__session.proxies = proxies
            self.__session.verify = verify

        self.__session.headers.update(dict(Accept="application/json"))

        self.tableapi = TableAPI(self)
        self.attachment = AttachmentClient(self)

    def GlideRecord(self, table, batch_size=100) -> GlideRecord:
        """
        Create a :class:`pysnc.GlideRecord` for a given table against the current client

        :param str table: The table name e.g. ``problem``
        :param int batch_size: Batch size (items returned per HTTP request). Default is ``100``.
        :return: :class:`pysnc.GlideRecord`
        """
        return GlideRecord(self, table, batch_size)

    def Attachment(self, table, sys_id=None) -> Attachment:
        """
        Create an Attachment object for the current client

        :return: :class:`pysnc.Attachment`
        """
        return Attachment(self, table, sys_id)

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

    def __init__(self, client, table):
        self._client = client
        self._table = table

    @property
    def session(self):
        return self._client.session

    def _set_params(self, record=None):
        params = {} if record == None else record._parameters()
        params['sysparm_display_value'] = 'all'
        params['sysparm_exclude_reference_link'] = 'true'  # Scratch it!
        params['sysparm_suppress_pagination_header'] = 'true'  # Required for large queries
        return params

    def _validate_response(self, response):
        code = response.status_code
        if code >= 400:
            try:
                rjson = response.json()
                if code == 403:
                    raise RoleException(rjson)
                if code == 401:
                    raise AuthenticationException(rjson)
                if code == 400:
                    raise RequestException(rjson)
            except JSONDecodeError:
                raise RequestException(response.text)

    def _send(self, req):
        request = self.session.prepare_request(req)
        r = self.session.send(request)
        self._validate_response(r)
        return r

class TableAPI(API):

    def _target(self, table, sys_id=None):
        target = "{url}/api/now/table/{table}".format(url=self.__instance, table=table)
        if sys_id:
            target = "{}/{}".format(target, sys_id)
        return target

    def list(self, record):
        params = self._set_params(record)
        target_url = self._target(record.table)

        req = requests.Request('GET', target_url, params=params)
        return self._send(req)

    def get(self, record, sys_id):
        params = self._set_params(record)
        # delete extra stuff
        if 'sysparm_offset' in params:
            del params['sysparm_offset']
        r = self.session.get(self._target(record.table, sys_id),
                             params=params)
        self._validate_response(r)
        return r

    def put(self, record):
        self.patch(record)

    def patch(self, record):
        body = record.serialize()
        params = self._set_params()
        r = self.session.put(self._target(record.table, record.sys_id),
                             params=params,
                             json=body)
        self._validate_response(r)
        return r

    def post(self, record):
        body = record.serialize()
        params = self._set_params()
        r = self.session.post(self._target(record.table),
                              params=params,
                              json=body)
        self._validate_response(r)
        return r

    def delete(self, record):
        r = self.session.delete(self._target(record.table, record.sys_id))
        self._validate_response(r)
        return r


class AttachmentAPI(API):
    API_VERSION = 'v1'

    def _target(self, sys_id=None):
        target = "{url}/api/now/{version}/attachment".format(url=self._client.instance, version=self.API_VERSION)
        if sys_id:
            target = "{}/{}".format(target, sys_id)
        return target

    def get(self, sys_id=None):
        params = {}
        r = self.session.get(self._target(sys_id),
                                     params=params)
        self._validate_response(r)
        return r

    def get_file(self, sys_id):
        """ This may be dangerous, as stream is true and if not fully read could leave open handles"""
        url = "{}/file".format(self._target(sys_id))
        r = self.session.get(url, stream=True)
        return r

    def list(self, params=None):
        params = self._set_params(params)
        r = self.session.get(self._url,
                                     params=params,
                                     headers=dict(Accept="application/json"))
        self._validate_response(r)
        return r

    def upload_file(self, file_name, table_name, table_sys_id, file, content_type, encryption_context=None):
        url = "%s/file" % (self._url)
        params = {}
        params['file_name'] = file_name
        params['table_name'] = table_name
        params['table_sys_id'] = table_sys_id
        if encryption_context:
            params['encryption_context'] = encryption_context

        headers = {'Content-Type': 'application/octet-stream'}
        if content_type:
            headers['Content-Type'] = content_type

        r = self.session.post(url,
                              params=params,
                              headers=headers,
                              data=file)
        self._validate_response(r)
        return r

    def delete(self, sys_id):
        url = "%s/%s" % (self._url, sys_id)
        r = self.session.delete(url)
        return r



class BatchAPI(APIClient):
    API_VERSION = 'v1'

    def __init__(self, client, batch_size=50):
        APIClient.__init__(client)
        self.request_id = 0
        self._queue = []
        self.batch_size = batch_size

    def _target(self):
        return "{url}/api/now/{version}/batch".format(url=self._client.instance, version=self.API_VERSION)

    def _generate_request(self, method, url, headers, body):
        return {
            'method': method,
            'url': url,
            'headers': headers,
            'body': body
        }

    def execute(self):
        rid = ++request_id
        body = {
            'batch_request_id':rid,
            'rest_requests': []
        }
        r = self.session.post(self._target(),
                              json=body)

    def list(self, record): # querying is not a batched action... right?
        params = self._set_params(record)
        target_url = "{url}/api/now/table/{table}".format(url=self.__instance, table=record.table)
        r = self.session.get(target_url, params=params)
        self._validate_response(r)
        return r

    def get(self, record, sys_id):
        params = self._set_params(record)
        if 'sysparm_offset' in params:
            del params['sysparm_offset']
        r = self.session.get(self._target(record.table, sys_id),
                             params=params)
        r = requests.Request('GET', _self._target(record.table))
        pass

    def put(self, record):
        self.patch(record)

    def patch(self, record):
        body = record.serialize()
        params = self._set_params()
        r = self.session.put(self._target(record.table, record.sys_id),
                             params=params,
                             json=body)
        self._validate_response(r)
        return r

    def post(self, record):
        body = record.serialize()
        params = self._set_params()
        r = self.session.post(self._target(record.table),
                              params=params,
                              json=body)
        self._validate_response(r)
        return r

    def delete(self, record):
        r = self.session.delete(self._target(record.table, record.sys_id))
        self._validate_response(r)
        return r
