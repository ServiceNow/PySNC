.. _authentication:

Authentication
==============

Basic Authentication
-------------------------

Standard BasicAuth, every request contains your username and password base64 encoded in the request header.

    >>> client = pysnc.ServiceNowClient('dev00000', ('admin','password'))

OAuth Authentication
--------------------

OAuth2 password flow is currently supported out of box, utilizing the default legacy mobile authenticator. Requires BasicAuth to
be enabled on the server for the first step to grab the legacy mobile secret.

    >>> from pysnc import ServiceNowClient, ServiceNowOAuth2
    >>> client = ServiceNowClient(server_url, ServiceNowOAuth2(username, password))

This will retrieve and store an OAuth2 auth and refresh token, sending your auth token with every request and dropping your user password.

Alternatively you can specify your own client and you do not require basic auth:

    >>> client = ServiceNowClient(server_url, ServiceNowOAuth2(username, password, client_id, client_secret))

If this sleeps for a long enough time your refresh token will expire and you must re-auth.

Requests Authentication
-----------------------

Ultimately any authentication method supported by python requests (https://2.python-requests.org/en/master/user/authentication/) can be passed directly to ServiceNowClient.

Should be flexible enough for any use-case.

Storing Passwords
-----------------

The keystore module is highly recommended. For example::

    import keyring

    def check_keyring(instance, user):
        passw = keyring.get_password(instance, user)
        return passw

    def set_keyring(instance, user, passw):
        keyring.set_password(instance, user, passw)

    if options.password:
        passw = options.password
        set_keyring(options.instance, options.user, passw)
    else:
        passw = check_keyring(options.instance, options.user)
        if passw is None:
            print('No Password specified and none found in keyring')
            sys.exit(1)

    client = pysnc.ServiceNowClient(options.instance, ServiceNowOAuth2(options.user, passw))
