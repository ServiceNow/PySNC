.. _advanced:

Advanced
========

Serialization
-------------

We can serialize to a python ``dict`` which can be useful for other storage mechanisms::

    >>> gr = client.GlideRecord('problem')
    >>> gr.fields = 'sys_id,short_description,state'
    >>> gr.query()
    >>> gr.next()
    True
    >>> gr.serialize()
    {u'short_description': u'Windows Something', u'state': u'3', u'sys_id': u'46eaa7c9a9fe198100bbe282da0d4b7d'}

The serialize method supports the ``display_value``, ``fields``,  and ``fmt`` arguments::

    >>> gr.serialize(display_value=True)
    {u'short_description': u'Windowsz', u'state': u'Pending Change', u'sys_id': u'46eaa7c9a9fe198100bbe282da0d4b7d'}
    >>> gr.serialize(display_value='both')
    {u'short_description': {u'display_value': u'Windowsz', u'value': u'Windowsz'}, u'state': {u'display_value': u'Pending Change', u'value': u'3'}, u'sys_id': {u'display_value': u'46eaa7c9a9fe198100bbe282da0d4b7d', u'value': u'46eaa7c9a9fe198100bbe282da0d4b7d'}}
    >>> gr.serialize(fields='sys_id')
    {u'sys_id': u'46eaa7c9a9fe198100bbe282da0d4b7d'}

The only supported ``fmt`` is ``pandas``.

Join Queries
------------

See the API documentation for additional details::

    >>> gr = client.GlideRecord('sys_user')
    >>> join_query = gr.add_join_query('sys_user_group', join_table_field='manager')
    >>> join_query.add_query('active','true')
    >>> gr.query()

Proxies
-------

You can use HTTP proxies, either specify a URL string or dict::

    >>> proxy_url = 'http://localhost:8080'
    >>> client = pysnc.ServiceNowClient(..., proxy=proxy_url)
    >>> client = pysnc.ServiceNowClient(..., proxy={'http': proxy_url, 'https': proxy_url}

Pandas
------

Transform a query into a DataFrame::

    >>> import pandas as pd
    >>> df = pd.DataFrame(gr.to_pandas())

