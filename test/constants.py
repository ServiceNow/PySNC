import getpass
import os
from dotenv import load_dotenv
import warnings
import logging

warnings.filterwarnings(action="ignore", message="unclosed", category=ResourceWarning)
logging.getLogger("urllib3").propagate = False # get rid of all the extra test logging junk
logging.getLogger('requests_oauthlib').propagate = False


class Constants(object):

    _server = None
    _username = 'admin'
    _plugin = None

    def __init__(self):
        load_dotenv()
        self._settings = {}

    @property
    def password(self):
        try:
            if os.path.exists('.password'):
                with open('.password', 'r') as f:
                    return f.read().strip()
        except:
            pass
        pw = self.get_value('password')
        if pw:
            return pw
        return getpass.getpass('\nPassword: ')

    @property
    def username(self):
        return self.get_value('username')

    @property
    def credentials(self):
        return (self.username, self.get_value('password'))

    @property
    def server(self):
        return self.get_value('server')

    @property
    def plugin(self):
        if 'plugin' in self._settings:
            return self._settings['plugin']
        return self._plugin

    def get_value(self, name):
        if name in self._settings:
            return self._settings[name]
        return os.environ[f"PYSNC_{name.replace('-','_')}".upper()]
