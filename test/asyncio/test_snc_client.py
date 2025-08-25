import asyncio
import os
from unittest import TestCase

import pytest
import httpx

from pysnc.asyncio import AsyncServiceNowClient
from ..constants import Constants


class TestAsyncServiceNowClient(TestCase):
    c = Constants()

    @pytest.mark.asyncio
    async def test_client_initialization(self):
        """Test that the client initializes correctly with different auth methods"""
        # Test with username/password tuple
        client = AsyncServiceNowClient(self.c.server, self.c.credentials)
        await client.init_client()
        self.assertIsNotNone(client.client)
        await client.close()
        
        # Test with proxy settings
        proxy = "http://proxy.example.com:8080"
        client = AsyncServiceNowClient(self.c.server, self.c.credentials, proxy=proxy)
        await client.init_client()
        self.assertIsNotNone(client.client)
        await client.close()

    @pytest.mark.asyncio
    async def test_client_instance(self):
        """Test that the instance URL is correctly formatted"""
        # Test with full URL
        client = AsyncServiceNowClient("https://dev12345.service-now.com", self.c.credentials)
        self.assertEqual(client.instance(), "https://dev12345.service-now.com")
        
        # Test with instance name only
        client = AsyncServiceNowClient("dev12345", self.c.credentials)
        self.assertEqual(client.instance(), "https://dev12345.service-now.com")

    @pytest.mark.asyncio
    async def test_glide_record_creation(self):
        """Test that GlideRecord objects are created correctly"""
        client = AsyncServiceNowClient(self.c.server, self.c.credentials)
        await client.init_client()
        
        # Create a GlideRecord
        gr = client.GlideRecord('problem')
        self.assertEqual(gr.table, 'problem')
        
        # Test with different batch size
        gr = client.GlideRecord('incident', batch_size=50)
        self.assertEqual(gr.table, 'incident')
        self.assertEqual(gr._batch_size, 50)
        
        await client.close()

    @pytest.mark.asyncio
    async def test_attachment_creation(self):
        """Test that Attachment objects are created correctly"""
        client = AsyncServiceNowClient(self.c.server, self.c.credentials)
        await client.init_client()
        
        # Create an Attachment
        attachment = await client.Attachment('problem')
        self.assertEqual(attachment.table, 'problem')
        
        await client.close()

    @pytest.mark.asyncio
    async def test_sys_id_detection(self):
        """Test the sys_id detection functionality"""
        # Valid sys_id format
        self.assertTrue(AsyncServiceNowClient.guess_is_sys_id("1234567890abcdef1234567890abcdef"))
        
        # Invalid sys_id formats
        self.assertFalse(AsyncServiceNowClient.guess_is_sys_id("not-a-sys-id"))
        self.assertFalse(AsyncServiceNowClient.guess_is_sys_id("12345"))
        self.assertFalse(AsyncServiceNowClient.guess_is_sys_id(""))

    @pytest.mark.asyncio
    async def test_client_close(self):
        """Test that the client closes correctly"""
        client = AsyncServiceNowClient(self.c.server, self.c.credentials)
        await client.init_client()
        self.assertIsNotNone(client.client)
        
        # Close the client
        await client.close()
        
        # Verify client is closed
        with self.assertRaises(RuntimeError):
            _ = client.client
