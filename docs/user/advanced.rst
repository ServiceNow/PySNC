.. _advanced:

Advanced
========

Attachments
-----------

The most likely way to interact with an attachment:

    >>> gr = client.GlideRecord('problem')
    >>> assert gr.get(my_sys_id), 'did not find record'
    >>> for attachment in gr.get_attachments():
    >>>     data = attachment.read().decode('utf-8')

or

    >>> for attachment in gr.get_attachments():
    >>>     for line in attachment.readlines():
    >>>         ...

Other useful attachment methods being `read()` and `writeto(...)` and `as_temp_file()`.

Dot Walking
-----------

Since we are using the TableAPI we miss out on useful dot-walking features that the standard GlideRecord object has, such as the `.getRefRecord()` function. To mimic this behavior we must specify the fields we which to dot walk before we query as such:

    >>> gr.fields = 'sys_id,opened_by,opened_by.email,opened_by.department.dept_head'
    >>> gr.query()
    >>> gr.next()
    True
    >>> gr.get_value('opened_by.email')
    'example@servicenow.com'
    >>> gr.get_value('opened_by.department.dept_head')
    'a4eac1d55b64900083193b9b3e42148d'
    >>> gr.get_display_value('opened_by.department.dept_head')
    'Fred Luddy'

But we can also do it like this:

    >>> print(f"Our department head is {gr.opened_by.department.dept_head}")
    Our department head is a4eac1d55b64900083193b9b3e42148d
    >>> gr.opened_by.department.dept_head
    GlideElement(value='a4eac1d55b64900083193b9b3e42148d', name='dept_head', display_value='Fred Luddy', changed=False)


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

Related List Queries
--------------------

Allows a user to perform a query comparing a related list, which allows the simulation of LEFT OUTER JOIN and etc.
See the API documentation and tests for additional details.

All users with the role which has a `name` of `admin`::

    >>> gr = client.GlideRecord('sys_user')
    >>> qc = gr.add_rl_query('sys_user_has_role', 'user', '>0', True)
    >>> qc.add_query('role.name', 'admin')
    >>> gr.query()

All users without any role::

    >>> gr = client.GlideRecord('sys_user')
    >>> qc = gr.add_rl_query('sys_user_has_role', 'user', '=0')
    >>> gr.query()

Proxies
-------

You can use HTTP proxies, either specify a URL string or dict::

    >>> proxy_url = 'http://localhost:8080'
    >>> client = pysnc.ServiceNowClient(..., proxy=proxy_url)
    >>> client = pysnc.ServiceNowClient(..., proxy={'http': proxy_url, 'https': proxy_url}

Password2 Fields
----------------

According to official documentation, the `value` of a Password2 field will be encrypted and the `display_value` will be unencrypted based on the requesting user's encryption context

Pandas
------

Transform a query into a DataFrame::

    >>> import pandas as pd
    >>> df = pd.DataFrame(gr.to_pandas())


Performance Concerns
--------------------

1. Why is my query so slow?

The following can improve performance:

* Set the :ref:`GlideRecord.fields` to the minimum number of required fields
* Increase (or decrease) the default :ref:`batch_size` for GlideRecord
* According to `KB0534905 <https://support.servicenow.com/kb_view.do?sysparm_article=KB0534905>`_ try disabling display values if they are not required via `gr.display_value = False`
* Try setting a query :ref:`limit` if you do not need all results

2. Why am I consuming so much memory?

By default, GlideRecord can be 'rewound' in that it stores all previously fetched records in memory. This can be disabled by setting :ref:`rewind` to False on GlideRecord
