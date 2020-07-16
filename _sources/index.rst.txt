.. pysnc documentation master file, created by
   sphinx-quickstart on Thu Jun  7 10:28:30 2018.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Welcome to PySNC's documentation!
=================================

Release v\ |version|. (:ref:`Installation <install>`)

------------------

PySNC was created to fill the need for a familiar interface to query data from an instance from python. The interface, modeled after GlideRecord, provides developers who already know ServiceNow record queries an easy, quick, and consistent method to interact with platform data.

**PySNC at a glance:**

    >>> client = pysnc.ServiceNowClient('dev00000', ('admin','admin'))
    >>> gr = client.GlideRecord('sys_user')
    >>> gr.add_query('user_name', 'admin')
    >>> gr.query()
    >>> for r in gr:
    ...     print(r.sys_id)
    ...
    6816f79cc0a8016401c5a33be04be441

Or more traditionally:

    >>> while gr.next():
    ...     print(gr.sys_id)
    ...
    6816f79cc0a8016401c5a33be04be441

User Guide
----------

.. toctree::
   :maxdepth: 2
   :caption: Contents:

   user/install
   user/getting_started
   user/advanced
   user/authentication

The API
-----------------------------

.. toctree::
   :maxdepth: 2

   api

