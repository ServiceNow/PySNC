from .exceptions import *


def get_instance(instance):
    """
    Return a well formed instance or raise

    :param instance: A string
    :return: The full instance URL
    :raise: InstanceException
    """
    if '://' in instance:
        return instance.rstrip('/')
    if '.' not in instance:
        return 'https://%s.service-now.com' % instance

    raise InstanceException("Instance name not well-formed. Pass a full URL or instance name.")
