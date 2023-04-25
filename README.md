# ServiceNow Python API

**What:** 
PySnc is a python interface for the ServiceNow and the Table API. It is designed to mimic the familiar GlideRecord interface you know with pythonic support where applicable. 

**Why:** 
Spawned from the desire to interact with ServiceNow data in a familiar and consistent manner

## Install

```
pip install pysnc
```

## Quick Start

```python
from pysnc import ServiceNowClient

client = ServiceNowClient('https://dev0000.service-now.com', ('integration.user', password))

gr = client.GlideRecord('sys_user')
gr.add_query('user_name', 'admin')
gr.query()
for r in gr:
	print(r.sys_id)
```

## Documentation

Full documentation currently available at [https://servicenow.github.io/PySNC/](https://servicenow.github.io/PySNC/)

Or build them yourself:

```
cd docs && make html
```

## Development Notes

The following functions are not (yet?) supported:

* `choose_window(first_row, last_row, force_count=True)`  TODO
* `get_class_display_value()`
* `get_record_class_name()`
* `is_valid()` TODO
* `is_valid_record()`
* `new_record()`
* `_next()`
* `_query()`

The following will not be implemented:

* `get_attribute(field_name)` Not Applicable
* `get_ED()` Not Applicable
* `get_label()` Not Applicable
* `get_last_error_message()` Not Applicable
* `set_workflow(enable)` Not Possible
* `operation()` Not Applicable
* `set_abort_action()` Not Applicable
* `is_valid_field()` Not Possible
* `is_action_aborted()` Not Applicable

# Feature Wants and TODO

* GlideAggregate support (`/api/now/stats/{tableName}`)

And we want to:

* Improve documentation