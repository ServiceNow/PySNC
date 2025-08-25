import asyncio
from typing import Any, Dict, Optional
from unittest import TestCase

from pysnc.asyncio.attachment import AsyncAttachment

# ----------------------
# Test doubles / fakes
# ----------------------


class FakeResponse:
    def __init__(self, json_data: Dict[str, Any] | None = None, status_code: int = 200):
        self._json_data = json_data or {}
        self.status_code = status_code

    def json(self) -> Dict[str, Any]:
        return self._json_data


class FakeFileResponse:
    """Mimic an async streaming response returned by get_file()."""

    def __init__(self, content: bytes):
        self._content = content

    async def aread(self) -> bytes:
        return self._content


class FakeAttachmentAPI:
    def __init__(self):
        self._get_response: Optional[FakeResponse] = None
        self._get_file_content: Optional[bytes] = None
        self._upload_response: Optional[FakeResponse] = None
        self._delete_status: int = 204
        self._list_response: Optional[FakeResponse] = None

    async def get(self, sys_id: str):
        return self._get_response or FakeResponse({"result": {}}, status_code=200)

    async def get_file(self, sys_id: str, stream: bool = True):
        content = self._get_file_content if self._get_file_content is not None else b""
        return FakeFileResponse(content)

    async def upload_file(
        self,
        *,
        file_name: str,
        table_name: str,
        table_sys_id: str,
        file,
        content_type: Optional[str],
        encryption_context: Optional[str],
    ):
        return self._upload_response or FakeResponse({"result": {}}, status_code=201)

    async def delete(self, sys_id: str):
        return FakeResponse({}, status_code=self._delete_status)

    async def list(self, attachment_obj: AsyncAttachment):
        return self._list_response or FakeResponse({"result": []}, status_code=200)


class FakeClient:
    def __init__(self, api: FakeAttachmentAPI):
        self.attachment_api = api


# ----------------------
# TestCase (sync methods)
# ----------------------


class TestAsyncAttachment(TestCase):

    def run_async(self, coro):
        return asyncio.get_event_loop().run_until_complete(coro)

    # ---- property coverage ----
    def test_properties_roundtrip(self):
        api = FakeAttachmentAPI()
        client = FakeClient(api)
        att = AsyncAttachment(client, table="problem")

        att.table_sys_id = "abc123"
        att.sys_id = "def456"
        att.file_name = "file.txt"
        att.content_type = "text/plain"
        att.size_bytes = 42
        att.download_link = "https://example/download"

        self.assertEqual(att.table, "problem")
        self.assertEqual(att.table_sys_id, "abc123")
        self.assertEqual(att.sys_id, "def456")
        self.assertEqual(att.file_name, "file.txt")
        self.assertEqual(att.content_type, "text/plain")
        self.assertEqual(att.size_bytes, 42)
        self.assertEqual(att.download_link, "https://example/download")

    # ---- get() branches ----
    def test_get_returns_false_on_empty_sys_id(self):
        api = FakeAttachmentAPI()
        client = FakeClient(api)
        att = AsyncAttachment(client, table="problem")

        self.assertFalse(self.run_async(att.get("")))

    def test_get_missing_result_key_returns_false(self):
        api = FakeAttachmentAPI()
        api._get_response = FakeResponse({"no_result": {}}, status_code=200)
        client = FakeClient(api)
        att = AsyncAttachment(client, table="problem")

        self.assertFalse(self.run_async(att.get("sysid1")))

    def test_get_empty_result_returns_false(self):
        api = FakeAttachmentAPI()
        api._get_response = FakeResponse({"result": {}}, status_code=200)
        client = FakeClient(api)
        att = AsyncAttachment(client, table="problem")

        self.assertFalse(self.run_async(att.get("sysid1")))

    def test_get_success_sets_fields_and_parses_ints(self):
        payload = {
            "result": {
                "file_name": "doc.pdf",
                "content_type": "application/pdf",
                "size_bytes": "12345",
                "download_link": "https://x/y",
                "table_name": "problem",
                "table_sys_id": "tbl-123",
            }
        }
        api = FakeAttachmentAPI()
        api._get_response = FakeResponse(payload, status_code=200)
        client = FakeClient(api)
        att = AsyncAttachment(client, table="ignored")

        ok = self.run_async(att.get("sysid-get"))
        self.assertTrue(ok)
        self.assertEqual(att.sys_id, "sysid-get")
        self.assertEqual(att.file_name, "doc.pdf")
        self.assertEqual(att.content_type, "application/pdf")
        self.assertEqual(att.size_bytes, 12345)
        self.assertEqual(att.download_link, "https://x/y")
        self.assertEqual(att.table, "problem")
        self.assertEqual(att.table_sys_id, "tbl-123")

    # ---- get_file() branches ----
    def test_get_file_raises_when_no_sys_id(self):
        api = FakeAttachmentAPI()
        client = FakeClient(api)
        att = AsyncAttachment(client, table="problem")
        with self.assertRaisesRegex(ValueError, "No sys_id specified"):
            self.run_async(att.get_file())

    def test_get_file_uses_current_sys_id_and_stream_flag(self):
        api = FakeAttachmentAPI()
        api._get_file_content = b"hello world"
        client = FakeClient(api)
        att = AsyncAttachment(client, table="problem")
        att.sys_id = "abc"

        resp = self.run_async(att.get_file(stream=True))
        data = self.run_async(resp.aread())
        self.assertEqual(data, b"hello world")

    # ---- upload() branches ----
    def test_upload_raises_if_table_sys_id_missing(self):
        api = FakeAttachmentAPI()
        client = FakeClient(api)
        att = AsyncAttachment(client, table="problem")
        with self.assertRaisesRegex(ValueError, "table_sys_id must be set before uploading"):
            self.run_async(att.upload("f.txt", file_obj=b"bytes", content_type="text/plain"))

    def test_upload_returns_none_if_no_result(self):
        api = FakeAttachmentAPI()
        api._upload_response = FakeResponse({"no_result": {}}, status_code=201)
        client = FakeClient(api)
        att = AsyncAttachment(client, table="problem")
        att.table_sys_id = "tbl-1"

        sysid = self.run_async(att.upload("f.txt", file_obj=b"abc", content_type="text/plain"))
        self.assertIsNone(sysid)

    def test_upload_returns_none_if_empty_result(self):
        api = FakeAttachmentAPI()
        api._upload_response = FakeResponse({"result": {}}, status_code=201)
        client = FakeClient(api)
        att = AsyncAttachment(client, table="problem")
        att.table_sys_id = "tbl-1"

        sysid = self.run_async(att.upload("f.txt", file_obj=b"abc", content_type="text/plain"))
        self.assertIsNone(sysid)

    def test_upload_success_sets_fields_and_returns_sys_id(self):
        api = FakeAttachmentAPI()
        api._upload_response = FakeResponse(
            {
                "result": {
                    "sys_id": "new-sys",
                    "file_name": "f.txt",
                    "content_type": "text/plain",
                    "size_bytes": "999",
                    "download_link": "https://dl/f.txt",
                }
            },
            status_code=201,
        )
        client = FakeClient(api)
        att = AsyncAttachment(client, table="problem")
        att.table_sys_id = "tbl-1"

        sysid = self.run_async(att.upload("f.txt", file_obj=b"DATA", content_type="text/plain"))
        self.assertEqual(sysid, "new-sys")
        self.assertEqual(att.sys_id, "new-sys")
        self.assertEqual(att.file_name, "f.txt")
        self.assertEqual(att.content_type, "text/plain")
        self.assertEqual(att.size_bytes, 999)
        self.assertEqual(att.download_link, "https://dl/f.txt")

    # ---- delete() branches ----
    def test_delete_raises_when_no_sys_id(self):
        api = FakeAttachmentAPI()
        client = FakeClient(api)
        att = AsyncAttachment(client, table="problem")
        with self.assertRaisesRegex(ValueError, "No sys_id specified"):
            self.run_async(att.delete())

    def test_delete_returns_false_when_not_204(self):
        api = FakeAttachmentAPI()
        api._delete_status = 400
        client = FakeClient(api)
        att = AsyncAttachment(client, table="problem")
        att.sys_id = "to-del"

        ok = self.run_async(att.delete())
        self.assertFalse(ok)
        self.assertEqual(att.sys_id, "to-del")  # state unchanged

    def test_delete_204_resets_state_when_current_attachment(self):
        api = FakeAttachmentAPI()
        api._delete_status = 204
        client = FakeClient(api)
        att = AsyncAttachment(client, table="problem")
        att.sys_id = "to-del"
        att.file_name = "f.txt"
        att.content_type = "text/plain"
        att.size_bytes = 123
        att.download_link = "https://dl/f.txt"

        ok = self.run_async(att.delete())
        self.assertTrue(ok)
        self.assertIsNone(att.sys_id)
        self.assertIsNone(att.file_name)
        self.assertIsNone(att.content_type)
        self.assertIsNone(att.size_bytes)
        self.assertIsNone(att.download_link)

    def test_delete_204_different_sys_id_does_not_reset_state(self):
        api = FakeAttachmentAPI()
        api._delete_status = 204
        client = FakeClient(api)
        att = AsyncAttachment(client, table="problem")
        att.sys_id = "keep-me"

        ok = self.run_async(att.delete(sys_id="some-other"))
        self.assertTrue(ok)
        self.assertEqual(att.sys_id, "keep-me")

    # ---- list() branches ----
    def test_list_raises_without_table_sys_id(self):
        api = FakeAttachmentAPI()
        client = FakeClient(api)
        att = AsyncAttachment(client, table="problem")

        with self.assertRaisesRegex(ValueError, "table_sys_id must be set before listing attachments"):
            self.run_async(att.list())

    def test_list_missing_result_returns_empty_list(self):
        api = FakeAttachmentAPI()
        api._list_response = FakeResponse({"no_result": []}, status_code=200)
        client = FakeClient(api)
        att = AsyncAttachment(client, table="problem")
        att.table_sys_id = "tbl-xyz"

        out = self.run_async(att.list())
        self.assertEqual(out, [])

    def test_list_success(self):
        api = FakeAttachmentAPI()
        api._list_response = FakeResponse({"result": [{"sys_id": "1"}, {"sys_id": "2"}]}, status_code=200)
        client = FakeClient(api)
        att = AsyncAttachment(client, table="problem")
        att.table_sys_id = "tbl-xyz"

        out = self.run_async(att.list())
        self.assertIsInstance(out, list)
        self.assertEqual({x["sys_id"] for x in out}, {"1", "2"})

    # ---- __str__() ----
    def test_str_no_current_attachment(self):
        api = FakeAttachmentAPI()
        client = FakeClient(api)
        att = AsyncAttachment(client, table="problem")
        self.assertEqual(str(att), "Attachment(no current attachment)")

    def test_str_with_current_attachment(self):
        api = FakeAttachmentAPI()
        client = FakeClient(api)
        att = AsyncAttachment(client, table="problem")
        att.sys_id = "abc"
        att.file_name = "f.txt"
        att.size_bytes = 10
        self.assertEqual(str(att), "Attachment(sys_id=abc, file_name=f.txt, size=10)")
