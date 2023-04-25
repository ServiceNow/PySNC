from .exceptions import *


def get_instance(instance):
    """
    Return a well formed instance or raise

    :param instance: A string
    :return: The full instance URL
    :raise: InstanceException
    """
    if '://' in instance:
        instance = instance.rstrip('/')
        if instance.startswith('http://'):
            raise InstanceException("Must provide https:// url not http://")
        return instance
    if '.' not in instance:
        return 'https://%s.service-now.com' % instance

    raise InstanceException("Instance name not well-formed. Pass a full URL or instance name.")


class MockHeaders:
    def __init__(self, headers):
        self._headers = headers

    def getheaders(self, name):
        return self._headers[name]

    def get_all(self, name, default):
        return getattr(self._headers, name, default)