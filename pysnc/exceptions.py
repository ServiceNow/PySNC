class PackageNotFound(Exception):
    pass


class AuthenticationException(Exception):
    pass


class EvaluationException(Exception):
    pass


class AclQueryException(Exception):
    pass


class RoleException(Exception):
    pass


class RestException(Exception):
    def __init__(self, message, status_code=None):
        '''if isinstance(message, dict) and 'error' in message:
            message = message['error']['message']
            self.detail = message['error']['detail']
            self.status = message['error']['status']'''
        super(RestException, self).__init__(self, "%s - %s" % (status_code, message))
        self.status_code = status_code


class InsertException(RestException):
    pass


class UpdateException(RestException):
    pass


class DeleteException(RestException):
    pass


class RequestException(Exception):
    pass


class InstanceException(Exception):
    pass

