import requests
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
    :param auth: Username password combination ``(name,pass)``, :class:`pysnc.ServiceNowOAuth2` or ``requests.sessions.Session`` object
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

        self.attachment = AttachmentClient(self)

    def GlideRecord(self, table, batch_size=10):
        """
        Create a :class:`pysnc.GlideRecord` for a given table against the current client

        :param str table: The table name e.g. ``problem``
        :param int batch_size: Batch size (items returned per HTTP request). Default is ``10``.
        :return: :class:`pysnc.GlideRecord`
        """
        return GlideRecord(self, table, batch_size)

    def Attachment(self, table, sys_id=None):
        """
        Create an Attachment object for the current client

        :return: :class:`pysnc.Attachment`
        """
        return Attachment(self, table, sys_id)

    @property
    def instance(self):
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
    def guess_is_sys_id(value):
        """
        Attempt to guess if this is a probable sys_id

        :param str value: the value to check
        :return: If this is probably a sys_id
        :rtype: bool
        """
        return re.match(r'^[A-Za-z0-9]{32}$', value) is not None

    def _target(self, table, sys_id=None):
        target = "{url}/api/now/table/{table}".format(url=self.__instance, table=table)
        if sys_id:
            target = "{}/{}".format(target, sys_id)
        return target

    def _set_params(self, record=None):
        params = {} if record == None else record._parameters()
        params['sysparm_display_value'] = 'all'
        params['sysparm_exclude_reference_link'] = 'true'  # Scratch it!
        params['sysparm_suppress_pagination_header'] = 'true'  # Required for large queries
        return params

    def _validate_response(self, response):
        code = response.status_code
        if code == 403:
            rjson = response.json()
            raise RoleException(rjson)
        if code == 401:
            rjson = response.json()
            raise AuthenticationException(rjson)
        if code == 400:
            rjson = response.json()
            raise RequestException(rjson)

    def _list(self, record):
        params = self._set_params(record)
        target_url = self._target(record.table)
        r = self.session.get(target_url,
                             params=params,
                             headers=dict(Accept="application/json"))
        self._validate_response(r)
        return r

    def _get(self, record, sys_id):
        # delete extra stuff
        params = self._set_params(record)
        if 'sysparm_offset' in params:
            del params['sysparm_offset']
        r = self.session.get(self._target(record.table, sys_id),
                             params=params,
                             headers=dict(Accept="application/json"))
        self._validate_response(r)
        return r

    def _put(self, record):
        body = record.serialize(changes_only=True)  # changes only because why post data we don't change?
        params = self._set_params()
        r = self.session.put(self._target(record.table, record.sys_id),
                             params=params,
                             json=body,
                             headers=dict(Accept="application/json"))
        return r

    def _post(self, record):
        body = record.serialize()
        params = self._set_params()
        r = self.session.post(self._target(record.table, None),
                              params=params,
                              json=body,
                              headers=dict(Accept="application/json"))
        return r

    def _delete(self, record):
        r = self.session.delete(self._target(record.table, record.sys_id),
                                headers=dict(Accept="application/json"))
        return r


class APIClient(object):

    def __init__(self, session, table):
        self._session = session
        self._table = table

    def _set_params(self, record=None):
        params = {} if record == None else record._parameters()
        params['sysparm_display_value'] = 'all'
        params['sysparm_exclude_reference_link'] = 'true'  # Scratch it!
        params['sysparm_suppress_pagination_header'] = 'true'  # Required for large queries
        return params

    def _validate_response(self, response):
        code = response.status_code
        if code == 403:
            rjson = response.json()
            raise RoleException(rjson)
        if code == 401:
            rjson = response.json()
            raise AuthenticationException(rjson)
        if code == 400:
            rjson = response.json()
            raise RequestException(rjson)


class TableAPI(APIClient):

    def _target(self, table, sys_id=None):
        target = "{url}/api/now/table/{table}".format(url=self.__instance, table=table)
        if sys_id:
            target = "{}/{}".format(target, sys_id)
        return target

    def list(self, record):
        params = self._set_params(record)
        target_url = self._target(record.table)
        r = self.session.get(target_url, params=params)
        self._validate_response(r)
        return r

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

class AttachmentAPI(APIClient):
    API_VERSION = 'v1'

    def _target(self, sys_id=None):
        target = "{url}/api/now/{version}/attachment".format(url=self._client.instance, version=self.API_VERSION)
        if sys_id:
            target = "{}/{}".format(target, sys_id)
        return target

    def get(self, sys_id=None):
        params = {}
        r = self._client.session.get(self._target(sys_id),
                                     params=params)
        self._validate_response(r)
        return r

    def get_file(self, sys_id):
        """ This may be dangerous, as stream is true and if not fully read could leave open handles"""
        url = "{}/file".format(self._target(sys_id))
        r = self._client.session.get(url, stream=True)
        return r

    def list(self, params=None):
        params = self._set_params(params)
        r = self._client.session.get(self._url,
                                     params=params,
                                     headers=dict(Accept="application/json"))
        self._client._validate_response(r)
        return r

class AttachmentClient(object):
    """
    Internal class.
    """
    API_VERSION = 'v1'

    def __init__(self, client):
        self._client = client
        self._url = "{url}/api/now/{version}/attachment".format(url=self._client.instance, version=self.API_VERSION)

    def _get(self, sys_id=None):
        params = {}
        url = self._url
        if sys_id:
            url = "%s/%s" % (url, sys_id)
        r = self._client.session.get(url,
                             params=params,
                             headers=dict(Accept="application/json"))
        return r

    def _get_file(self, sys_id):
        url = "%s/%s/file" % (self._url, sys_id)
        r = self._client.session.get(url,
                             stream=True)
        return r

    def _set_params(self, record=None):
        params = {} if record == None else record._parameters()
        params['sysparm_suppress_pagination_header'] = 'true'  # Required for large queries
        return params

    def _list(self, params=None):
        params = self._set_params(params)
        r = self._client.session.get(self._url,
                             params=params,
                             headers=dict(Accept="application/json"))
        self._client._validate_response(r)
        return r

    def _upload_file(self, file_name, table_name, table_sys_id, file, content_type, encryption_context=None):
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

        r = self._client.session.post(url,
                            params=params,
                            headers=headers,
                            data=file)
        self._client._validate_response(r)
        return r

    def _delete(self, sys_id):
        url = "%s/%s" % (self._url, sys_id)
        r = self._client.session.delete(url)
        return r


