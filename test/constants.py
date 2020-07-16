import getpass
import os
import yaml

class Constants(object):
    CONF_FILE = 'settings-test.yaml'

    _server = None
    _username = 'admin'
    _plugin = None

    def __init__(self, conf=None):
        if conf:
            self.CONF_FILE = conf
        try:
            with open(self.CONF_FILE, 'r') as f:
                self._settings = yaml.load(f)
        except:
            self._settings = {}

        try:
            # Attempt to pull from environment
            self._settings['server'] = os.environ['PYSNC_SERVER']
            self._settings['username'] = os.environ['PYSNC_USERNAME']
            self._settings['password'] = os.environ['PYSNC_PASSWORD']
        except:
            pass

    @property
    def password(self):
        if 'password' in self._settings:
            self._password = self._settings['password']
        try:
            with open('.password','r') as f:
                self._password = f.read().strip()
        except:
            pass
        if not hasattr(self, '_password'):
            self._password = getpass.getpass('\nPassword: ')
        return self._password

    @property
    def username(self):
        if 'username' in self._settings:
            return self._settings['username']
        return self._username

    @property
    def credentials(self):
        return (self.username, self.password)

    @property
    def server(self):
        if 'server' in self._settings:
            return self._settings['server']
        return self._server

    @property
    def plugin(self):
        if 'plugin' in self._settings:
            return self._settings['plugin']
        return self._plugin
