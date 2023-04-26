.. _getting_started:

Getting Started
===============

Ensure you are :ref:`installed <install>` and have an instance to talk to. A `PDI <https://developer.servicenow.com>`_ may be good start for playing around if you do not have access to a development instance.

The ServiceNow client
---------------------

The ``ServiceNowClient`` is your interface to an instance.

First we import::

    >>> from pysnc import ServiceNowClient

Then we create a client::

    >>> client = ServiceNowClient('dev00000', ServiceNowPasswordGrantFlow('admin', password, client_id, client_secret))
    # or more insecurely...
    >>> client = pysnc.ServiceNowClient('dev00000', ('admin', password))

We use the client to create a ``GlideRecord`` object::

    >>> gr = client.GlideRecord('incident')

Familiar? The real difference is we follow python naming conventions::

    >>> gr.add_query("active", "true")
    >>> gr.query()

Or even:

    >>> gr.add_active_query()

This means that instead of Java/JavaScript camelCase we use python standard in PEP-8. For example ``addQuery`` has become ``add_query``.

Querying a record
-----------------

The query methods are designed to behave very similarly to the glide implementations::

    >>> gr.add_query("value", ">", "1")

Or encoded queries::

    >>> gr.add_encoded_query("valuesLIKE1^active=true")

We can do or conditions::

    >>> o = gr.add_query('priority','1')
    >>> o.add_or_condition('priority','2')

Followed by a query::

    >>> gr.query()

No HTTP requests are made until `query()` is called.

Get a single record
-------------------

We can do our standard get::

    >>> gr.get('6816f79cc0a8016401c5a33be04be441')
    True

Or an advanced get::

    >>> gr.get('number', 'PRB123456')
    True

Iterating a record
------------------

There are two methods to iterate a GlideRecord::

    >>> while gr.next():
            pass
    >>> for r in gr:
            pass

When using the traditional `next()` function you will have to call `rewind()` if you wish to iterate a second time. The pythonic iteration does not require this and allows for list comprehensions and other python goodies.

Limiting Results
----------------

We are using the REST api after all, and sometimes we want to limit the number of requests we make for testing or sanity checking.

We can set limits on the number of results returned, the following will return up to 5 records::

    >>> gr.limit = 5

There is no default limit to the number of records we can query. We can also specify the fields we want to return::

    >>> gr.fields = 'sys_id,short_description'

Or like this::

    >>> gr.fields = ['sys_id', 'short_description']

This can reduce the load on our instance and how long it takes to query results. We can also use the fields feature to dotwalk table to reduce the record queries we need:

    >>> gr.fields = 'sys_id,assignment_group.short_description'

We can also modify the batch size, which is by default 10:

    >>> gr = client.GlideRecord('...', batch_size=50)
    >>> gr.batch_size = 60

Batch size, along with fields and limits, will affect how the API and instance perform. This should be tuned against API usage and instance semaphore set configuration. This documentation does not provide said guidance, when in doubt leave it default.

As a rule of thumb, query only the fields you actually want.

Accessing fields
----------------

We can access any field value via dot notation or the standard :py:func:`get_value` and :py:func:`get_display_value` methods. Fields are backed by :py:class:`record.GlideElement`

For example::

    >>> gr = client.GlideRecord('problem')
    >>> gr.query()
    >>> gr.next()
    True
    >>> gr.state
    record.GlideElement(name='state', value='3', display_value='Pending Change', changed=False)
    >>> gr.get_value('state')
    '3'
    >>> gr.get_display_value('state')
    'Pending Change'
    >>> gr.state == '3'
    True
    >>> f"State is {gr.state}"
    'State is 3'
    >>> gr.state.nil()
    False
    >>> gr.state = '4'
    >>> gr.state
    record.GlideElement(name='state', value='4', display_value=None, changed=True)
    >>> gr.state.get_value()
    '4'


The PySNC module cannot infer what a given columns data type may be from the REST API -- this gives some limitations on possible methods such as the `getRefRecord`

Setting fields
--------------

    >>> gr = client.GlideRecord('incident')
    >>> gr.initialize()
    >>> gr.state = 4
    >>> gr.get_value('state')
    4
    >>> gr.set_value('state', 4)

Length
--------------

You can use `len` or `get_row_count()` (they are the same)::

    >>> gr = client.GlideRecord('incident')
    >>> len(gr)
    0
    >>> gr.get_row_count()
    0
    >>> gr.query()
    >>> len(gr)
    20
    >>> gr.get_row_count()
    20


Insert, Update, Delete
----------------------

We can insert new records (you must call `initialize()` first):

    >>> gr = client.GlideRecord('problem')
    >>> gr.initialize()
    >>> gr.short_description = "Example Problem"
    >>> gr.description = "Example Description"
    >>> gr.insert()
    'a06252790b6693009fde8a4b33673aed'

And update:

    >>> gr = client.GlideRecord('problem')
    >>> gr.get('a06252790b6693009fde8a4b33673aed')
    True
    >>> gr.short_description = "Updated Problem"
    >>> gr.update()
    'a06252790b6693009fde8a4b33673aed'

And delete:

    >>> gr = client.GlideRecord('problem')
    >>> gr.get('a06252790b6693009fde8a4b33673aed')
    True
    >>> gr.delete()
    True
