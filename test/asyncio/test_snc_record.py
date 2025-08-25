import asyncio
import os
from unittest import TestCase, mock

import pytest
import httpx

from pysnc.asyncio import AsyncServiceNowClient, AsyncGlideRecord
from ..constants import Constants


class TestAsyncGlideRecord(TestCase):
    c = Constants()

    @pytest.mark.asyncio
    async def test_glide_record_initialization(self):
        """Test initialization of AsyncGlideRecord"""
        client = AsyncServiceNowClient(self.c.server, self.c.credentials)
        await client.init_client()
        
        gr = client.GlideRecord('incident')
        self.assertEqual(gr.table, 'incident')
        self.assertEqual(gr._batch_size, 100)  # Default batch size
        
        gr = client.GlideRecord('problem', batch_size=50)
        self.assertEqual(gr.table, 'problem')
        self.assertEqual(gr._batch_size, 50)
        
        await client.close()

    @pytest.mark.asyncio
    async def test_query_building(self):
        """Test building queries with AsyncGlideRecord"""
        client = AsyncServiceNowClient(self.c.server, self.c.credentials)
        await client.init_client()
        
        gr = client.GlideRecord('incident')
        gr.add_query('priority', '1')
        gr.add_query('state', '!=', 'closed')
        
        # Check the encoded query
        self.assertEqual(gr._encoded_query, 'priority=1^state!=closed')
        
        # Test OR condition
        gr = client.GlideRecord('incident')
        gr.add_query('priority', '1')
        gr.add_or_query('priority', '2')
        
        self.assertEqual(gr._encoded_query, 'priority=1^ORpriority=2')
        
        # Test add_null_query
        gr = client.GlideRecord('incident')
        gr.add_null_query('assigned_to')
        
        self.assertEqual(gr._encoded_query, 'assigned_toISEMPTY')
        
        # Test add_not_null_query
        gr = client.GlideRecord('incident')
        gr.add_not_null_query('assigned_to')
        
        self.assertEqual(gr._encoded_query, 'assigned_toISNOTEMPTY')
        
        await client.close()

    @pytest.mark.asyncio
    async def test_query_execution(self):
        """Test executing queries with AsyncGlideRecord"""
        # Create a mock response for query
        mock_response = httpx.Response(
            status_code=200,
            json={
                "result": [
                    {"sys_id": "1234", "number": "INC0001", "short_description": "Test Incident"},
                    {"sys_id": "5678", "number": "INC0002", "short_description": "Another Test"}
                ]
            }
        )
        
        client = AsyncServiceNowClient(self.c.server, self.c.credentials)
        await client.init_client()
        
        gr = client.GlideRecord('incident')
        gr.add_query('priority', '1')
        
        # Mock the API call
        with mock.patch.object(client.table_api, 'list', return_value=mock_response):
            await gr.query()
            
            # Check that we got the expected number of records
            self.assertEqual(gr._result_set_size, 2)
            
            # Test iteration
            records = []
            async for record in gr:
                records.append(record)
            
            self.assertEqual(len(records), 2)
            self.assertEqual(records[0]['sys_id'], '1234')
            self.assertEqual(records[1]['sys_id'], '5678')
            
            # Test rewind
            await gr.rewind()
            self.assertTrue(await gr.next())
            self.assertEqual(gr.sys_id, '1234')
            
        await client.close()

    @pytest.mark.asyncio
    async def test_record_operations(self):
        """Test record operations (get, insert, update, delete)"""
        # Mock responses for different operations
        mock_get_response = httpx.Response(
            status_code=200,
            json={
                "result": {
                    "sys_id": "1234",
                    "number": "INC0001",
                    "short_description": "Test Incident"
                }
            }
        )
        
        mock_insert_response = httpx.Response(
            status_code=201,
            json={
                "result": {
                    "sys_id": "5678",
                    "number": "INC0002",
                    "short_description": "New Incident"
                }
            }
        )
        
        mock_update_response = httpx.Response(
            status_code=200,
            json={
                "result": {
                    "sys_id": "1234",
                    "number": "INC0001",
                    "short_description": "Updated Incident"
                }
            }
        )
        
        mock_delete_response = httpx.Response(
            status_code=204
        )
        
        client = AsyncServiceNowClient(self.c.server, self.c.credentials)
        await client.init_client()
        
        # Test get
        gr = client.GlideRecord('incident')
        with mock.patch.object(client.table_api, 'get', return_value=mock_get_response):
            result = await gr.get('1234')
            self.assertTrue(result)
            self.assertEqual(gr.sys_id, '1234')
            self.assertEqual(gr.number, 'INC0001')
            self.assertEqual(gr.short_description, 'Test Incident')
        
        # Test insert
        gr = client.GlideRecord('incident')
        gr.short_description = 'New Incident'
        gr.priority = '2'
        
        with mock.patch.object(client.table_api, 'post', return_value=mock_insert_response):
            sys_id = await gr.insert()
            self.assertEqual(sys_id, '5678')
            self.assertEqual(gr.number, 'INC0002')
        
        # Test update
        gr = client.GlideRecord('incident')
        await gr.get('1234')  # This is mocked above
        gr.short_description = 'Updated Incident'
        
        with mock.patch.object(client.table_api, 'patch', return_value=mock_update_response):
            result = await gr.update()
            self.assertTrue(result)
            self.assertEqual(gr.short_description, 'Updated Incident')
        
        # Test delete
        gr = client.GlideRecord('incident')
        gr.sys_id = '1234'
        
        with mock.patch.object(client.table_api, 'delete', return_value=mock_delete_response):
            result = await gr.delete()
            self.assertTrue(result)
        
        await client.close()

    @pytest.mark.asyncio
    async def test_get_attachments(self):
        """Test getting attachments for a record"""
        # Mock response for attachments
        mock_attachments_response = httpx.Response(
            status_code=200,
            json={
                "result": [
                    {
                        "sys_id": "att1234",
                        "file_name": "test.txt",
                        "content_type": "text/plain",
                        "size_bytes": "100"
                    }
                ]
            }
        )
        
        client = AsyncServiceNowClient(self.c.server, self.c.credentials)
        await client.init_client()
        
        gr = client.GlideRecord('incident')
        gr.sys_id = '1234'
        
        with mock.patch.object(client.attachment_api, 'list', return_value=mock_attachments_response):
            attachments = await gr.get_attachments()
            self.assertEqual(len(attachments), 1)
            self.assertEqual(attachments[0]['sys_id'], 'att1234')
            self.assertEqual(attachments[0]['file_name'], 'test.txt')
        
        await client.close()

    @pytest.mark.asyncio
    async def test_serialization(self):
        """Test serialization of AsyncGlideRecord"""
        client = AsyncServiceNowClient(self.c.server, self.c.credentials)
        await client.init_client()
        
        gr = client.GlideRecord('incident')
        gr.short_description = 'Test Incident'
        gr.priority = '1'
        gr.state = 'new'
        
        # Test full serialization
        serialized = gr.serialize()
        self.assertEqual(serialized['short_description'], 'Test Incident')
        self.assertEqual(serialized['priority'], '1')
        self.assertEqual(serialized['state'], 'new')
        
        # Test changes-only serialization
        gr._changes = {'short_description': 'Test Incident'}
        serialized = gr.serialize(changes_only=True)
        self.assertEqual(serialized, {'short_description': 'Test Incident'})
        
        await client.close()

    @pytest.mark.asyncio
    async def test_display_value(self):
        """Test display value functionality"""
        # Mock response with display values
        mock_response = httpx.Response(
            status_code=200,
            json={
                "result": {
                    "sys_id": "1234",
                    "priority": {
                        "value": "1",
                        "display_value": "Critical"
                    },
                    "state": {
                        "value": "new",
                        "display_value": "New"
                    }
                }
            }
        )
        
        client = AsyncServiceNowClient(self.c.server, self.c.credentials)
        await client.init_client()
        
        gr = client.GlideRecord('incident')
        
        with mock.patch.object(client.table_api, 'get', return_value=mock_response):
            await gr.get('1234', display_value=True)
            self.assertEqual(gr.priority.get_value(), "1")
            self.assertEqual(gr.priority.get_display_value(), "Critical")
            self.assertEqual(gr.state.get_value(), "new")
            self.assertEqual(gr.state.get_display_value(), "New")
        
        await client.close()
