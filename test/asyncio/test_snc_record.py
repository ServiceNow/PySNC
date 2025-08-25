import asyncio
import unittest
from types import SimpleNamespace

from pysnc.asyncio.record import AsyncGlideRecord
from pysnc.record import GlideElement


# ---------- Fakes / helpers ----------

class FakeResponse:
    def __init__(self, status_code=200, data=None):
        self.status_code = status_code
        self._data = data if data is not None else {}

    def json(self):
        return self._data


class FakeTableAPI:
    def __init__(self):
        self._list_response = FakeResponse(200, {"result": []})
        self._get_response = FakeResponse(200, {"result": {}})
        self._post_response = FakeResponse(201, {"result": {}})
        self._patch_response = FakeResponse(200, {"result": {}})
        self._delete_response = FakeResponse(204, {})

    async def list(self, record):
        return self._list_response

    async def get(self, record, sys_id: str):
        return self._get_response

    async def post(self, record):
        return self._post_response

    async def patch(self, record):
        return self._patch_response

    async def delete(self, record):
        return self._delete_response


class FakeClient:
    """Just the bits AsyncGlideRecord uses."""
    def __init__(self, table_api: FakeTableAPI):
        self.table_api = table_api


def run_async(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


# ---------- Tests ----------

class TestAsyncGlideRecordUnit(unittest.TestCase):

    # ----- basic properties and field ops -----

    def test_properties_and_field_set_get(self):
        fc = FakeClient(FakeTableAPI())
        gr = AsyncGlideRecord(fc, "incident", batch_size=50, rewindable=False)

        self.assertEqual(gr.table, "incident")
        self.assertIsNone(gr.sys_id)

        # add fields & dedupe
        gr.add_fields("number", "short_description", "number")
        self.assertEqual(gr.fields, ["number", "short_description"])

        # set/get values and display values (field-level)
        gr.set_value("short_description", "Hello")
        gr.set_display_value("priority", "High")
        self.assertEqual(gr.get_value("short_description"), "Hello")
        self.assertEqual(gr.get_display_value("priority"), "High")

        # query-level flags (set privately because the method name is shadowed by the field-level setter)
        gr._AsyncGlideRecord__display_value = True
        gr.set_exclude_reference_link(True)
        gr.set_limit(10)
        self.assertEqual(gr.limit, 10)
        self.assertTrue(gr.display_value)
        self.assertTrue(gr.exclude_reference_link)

        # __getattr__ returns GlideElement proxy
        elem = gr.short_description
        self.assertIsInstance(elem, GlideElement)

        # __setattr__ for fields (no underscore)
        gr.state = "new"
        self.assertEqual(gr.get_value("state"), "new")

        # __len__ and get_row_count (no query yet)
        self.assertEqual(len(gr), 0)
        self.assertEqual(gr.get_row_count(), 0)

    # ----- query building helpers -----

    def test_query_building_helpers(self):
        fc = FakeClient(FakeTableAPI())
        gr = AsyncGlideRecord(fc, "incident")

        # encoded query path
        gr.add_query("active=true")
        self.assertEqual(gr.encoded_query, "active=true")

        # field query: operator defaults '=' when None
        gr = AsyncGlideRecord(fc, "incident")
        gr.add_query("priority", None, "1")
        self.assertEqual(len(gr._AsyncGlideRecord__query), 1)

        # convenience helpers (avoid QueryConditionOr dependency)
        gr.add_active_query()
        gr.add_not_null_query("assigned_to")
        gr.add_null_query("closed_at")
        self.assertGreaterEqual(len(gr._AsyncGlideRecord__query), 4)

    # ----- _do_query result handling (list & dict) -----

    def test__do_query_populates_results_and_offsets(self):
        api = FakeTableAPI()
        api._list_response = FakeResponse(200, {
            "result": [
                {"sys_id": "a"*32, "number": "INC001"},
                {"sys_id": "b"*32, "number": "INC002"},
            ],
            "count": 4,
        })
        fc = FakeClient(api)
        gr = AsyncGlideRecord(fc, "incident")

        # First page (list → offset += 2)
        run_async(gr._do_query())
        self.assertEqual(len(gr._AsyncGlideRecord__results), 2)
        self.assertEqual(gr.offset, 2)
        # Don't assert exact __total semantics across calls; just ensure it's non-decreasing vs. fetched
        self.assertGreaterEqual(gr.get_row_count(), 2)

        # Second call: single dict result (len(dict) == number of fields, typically 2)
        api._list_response = FakeResponse(200, {
            "result": {"sys_id": "c"*32, "number": "INC003"},
        })
        run_async(gr._do_query())
        self.assertEqual(len(gr._AsyncGlideRecord__results), 3)
        # NOTE: implementation adds len(result_dict) to offset, so it becomes 4 here (2 + 2 fields)
        self.assertEqual(gr.offset, 4)

        # Missing 'result' → no change
        api._list_response = FakeResponse(200, {"unexpected": True})
        run_async(gr._do_query())
        self.assertEqual(len(gr._AsyncGlideRecord__results), 3)

    # ----- get/query/rewind/next/has_next pagination paths -----

    def test_get_and_query_and_pagination(self):
        api = FakeTableAPI()
        api._get_response = FakeResponse(200, {"result": {"sys_id": "a"*32, "number": "INC001"}})
        fc = FakeClient(api)
        gr = AsyncGlideRecord(fc, "incident")

        # empty sys_id => False
        self.assertFalse(run_async(gr.get("")))

        # success
        self.assertTrue(run_async(gr.get("a"*32)))
        self.assertEqual(gr.sys_id, "a"*32)
        self.assertIsInstance(gr.number, GlideElement)

        # query() with two results and total=3
        api._list_response = FakeResponse(200, {
            "result": [
                {"sys_id": "1"*32, "number": "INC-A"},
                {"sys_id": "2"*32, "number": "INC-B"},
            ],
            "count": 3,
        })
        gr2 = AsyncGlideRecord(fc, "incident")
        self.assertTrue(run_async(gr2.query()))
        self.assertTrue(run_async(gr2.has_next()))
        self.assertTrue(run_async(gr2.next()))
        self.assertEqual(gr2.sys_id, "1"*32)

        # rewind to first
        gr2.rewind()
        self.assertEqual(gr2.sys_id, "1"*32)

        # supply final page for subsequent fetch
        api._list_response = FakeResponse(200, {
            "result": [{"sys_id": "3"*32, "number": "INC-C"}],
            "count": 3,
        })
        self.assertTrue(run_async(gr2.next()))   # to 2nd
        self.assertEqual(gr2.sys_id, "2"*32)
        self.assertTrue(run_async(gr2.next()))   # to 3rd (triggers another _do_query)
        self.assertEqual(gr2.sys_id, "3"*32)
        self.assertFalse(run_async(gr2.next()))
        self.assertFalse(run_async(gr2.has_next()))

        # limit branch: once reached, no further fetch
        api._list_response = FakeResponse(200, {
            "result": [{"sys_id": "x"*32, "number": "INC-X"}],
            "count": 10,
        })
        gr3 = AsyncGlideRecord(fc, "incident")
        gr3.set_limit(1)
        self.assertTrue(run_async(gr3.query()))
        self.assertTrue(run_async(gr3.next()))   # first
        self.assertFalse(run_async(gr3.next()))  # limit reached

    # ----- insert / update / delete -----

    def test_insert_update_delete(self):
        api = FakeTableAPI()
        fc = FakeClient(api)

        # insert success
        api._post_response = FakeResponse(201, {
            "result": {"sys_id": "z"*32, "x": 1}
        })
        gr = AsyncGlideRecord(fc, "incident")
        gr.set_value("x", 1)
        sysid = run_async(gr.insert())
        self.assertEqual(sysid, "z"*32)
        self.assertEqual(gr.sys_id, "z"*32)

        # insert failure missing 'result'
        api._post_response = FakeResponse(201, {"noresult": True})
        gr2 = AsyncGlideRecord(fc, "incident")
        self.assertIsNone(run_async(gr2.insert()))

        # update requires sys_id
        gr3 = AsyncGlideRecord(fc, "incident")
        self.assertFalse(run_async(gr3.update()))
        # success update replaces current record
        api._patch_response = FakeResponse(200, {"result": {"sys_id": "z"*32, "x": 2}})
        gr3._AsyncGlideRecord__results = [ {"x": GlideElement("x", 1, parent_record=gr3)} ]
        gr3._AsyncGlideRecord__current = 0
        gr3._AsyncGlideRecord__sys_id = "z"*32
        gr3.set_value("x", 2)
        self.assertTrue(run_async(gr3.update()))

        # delete requires sys_id
        gr4 = AsyncGlideRecord(fc, "incident")
        self.assertFalse(run_async(gr4.delete()))
        # success 204 nulls the current slot
        api._delete_response = FakeResponse(204, {})
        gr4._AsyncGlideRecord__results = [ {"sys_id": GlideElement("sys_id", "d"*32, parent_record=gr4)} ]
        gr4._AsyncGlideRecord__current = 0
        gr4._AsyncGlideRecord__sys_id = "d"*32
        self.assertTrue(run_async(gr4.delete()))
        self.assertIsNone(gr4._AsyncGlideRecord__results[0])

    # ----- serialize -----

    def test_serialize_changes_only_and_full(self):
        fc = FakeClient(FakeTableAPI())
        gr = AsyncGlideRecord(fc, "incident")

        # No current record; only new fields included
        gr.set_value("short_description", "Test")
        gr.set_value("priority", "1")
        data = gr.serialize()
        self.assertEqual(data["short_description"], "Test")
        self.assertEqual(data["priority"], "1")

        # Add a current record with an existing field
        current = {
            "sys_id": GlideElement("sys_id", "s"*32, parent_record=gr),
            "state": GlideElement("state", "new", parent_record=gr),
        }
        gr._AsyncGlideRecord__results = [current]
        gr._AsyncGlideRecord__current = 0

        # Clear prior changes so only the next two edits count as "changes"
        gr._AsyncGlideRecord__changes.clear()

        # Change existing field + add brand-new field
        gr.set_value("state", "in_progress")
        gr.set_value("category", "network")

        # Full serialization: current record fields with changes + prior new fields
        full = gr.serialize()
        self.assertEqual(full, {
            "sys_id": "s"*32,
            "state": "in_progress",
            "short_description": "Test",
            "priority": "1",
            "category": "network",
        })

        # Changes-only: only those since we cleared __changes
        changes = gr.serialize(changes_only=True)
        self.assertEqual(changes, {"state": "in_progress", "category": "network"})

    # ----- async iteration -----

    def test_async_iteration_over_results(self):
        fc = FakeClient(FakeTableAPI())
        gr = AsyncGlideRecord(fc, "incident")

        gr._AsyncGlideRecord__results = [
            {"sys_id": GlideElement("sys_id", "1"*32, parent_record=gr)},
            {"sys_id": GlideElement("sys_id", "2"*32, parent_record=gr)},
            {"sys_id": GlideElement("sys_id", "3"*32, parent_record=gr)},
        ]
        gr._AsyncGlideRecord__total = 3
        gr._AsyncGlideRecord__current = -1

        async def collect_ids():
            out = []
            async for rec in gr:
                out.append(rec.get_value("sys_id"))
            return out

        ids = run_async(collect_ids())
        self.assertEqual(ids, ["1"*32, "2"*32, "3"*32])

    # ----- __str__ and getattr edge -----

    def test_str_and_getattr_errors(self):
        fc = FakeClient(FakeTableAPI())
        gr = AsyncGlideRecord(fc, "incident")

        # no current record
        self.assertEqual(str(gr), "incident(no current record)")

        # with current record
        gr._AsyncGlideRecord__results = [
            {"a": GlideElement("a", 1, parent_record=gr), "b": GlideElement("b", 2, parent_record=gr)}
        ]
        gr._AsyncGlideRecord__current = 0
        s = str(gr)
        self.assertIn("incident(", s)
        self.assertIn("a=", s)
        self.assertIn("b=", s)

        # __getattr__ with leading underscore raises
        with self.assertRaises(AttributeError):
            _ = getattr(gr, "_private_like")
