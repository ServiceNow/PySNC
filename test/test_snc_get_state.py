import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from pysnc.record import GlideRecord
from pysnc.asyncio.record import AsyncGlideRecord
from pysnc.exceptions import NoRecordException, NotFoundException


@pytest.fixture(params=[False, True], ids=["sync", "async"])
def record(request):
    api = SimpleNamespace(
        get=AsyncMock() if request.param else Mock(),
        list=AsyncMock() if request.param else Mock(),
    )
    cls = AsyncGlideRecord if request.param else GlideRecord
    gr = cls(SimpleNamespace(table_api=api), "incident")

    def get(*args):
        result = gr.get(*args)
        return asyncio.run(result) if request.param else result

    return gr, api, get


@pytest.mark.parametrize("initialized", [False, True])
def test_missing_sys_id_clears_previous_record(record, initialized):
    gr, api, get = record
    if initialized:
        gr.initialize()
        gr.short_description = "old value"
    else:
        api.get.return_value = Mock(
            json=Mock(return_value={"result": {"sys_id": "old", "short_description": "old value"}})
        )
        assert get("old")
    api.get.side_effect = NotFoundException("not found")

    assert get("missing") is False
    assert len(gr) == 0
    assert gr.has_next() is False
    assert gr.is_new_record() is False
    with pytest.raises(NoRecordException):
        gr.get_value("short_description")


def test_empty_field_lookup_clears_previous_record(record):
    gr, api, get = record
    gr.initialize()
    gr.short_description = "old value"
    api.list.return_value = Mock(status_code=200, headers={"X-Total-Count": "0"},
                                 json=Mock(return_value={"result": []}))

    assert get("number", "missing") is False
    assert gr.has_next() is False
    assert len(gr) == 0
    with pytest.raises(NoRecordException):
        gr.get_value("short_description")


def test_successful_field_lookup_replaces_previous_record(record):
    gr, api, get = record
    gr.initialize()
    gr.short_description = "old value"
    api.list.return_value = Mock(status_code=200, headers={"X-Total-Count": "1"},
                                 json=Mock(return_value={"result": [{"sys_id": "new"}]}))

    assert get("number", "new") is True
    assert gr.get_value("sys_id") == "new"
    assert gr.get_value("short_description") is None
    assert len(gr) == 1
    assert gr.is_new_record() is False


def test_successful_lookup_after_missing_record(record):
    gr, api, get = record
    api.get.side_effect = [
        NotFoundException("not found"),
        Mock(json=Mock(return_value={"result": {"sys_id": "new"}})),
    ]
    assert get("missing") is False
    assert get("new") is True
    assert gr.get_value("sys_id") == "new"
    assert len(gr) == 1
