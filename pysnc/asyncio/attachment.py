"""
Asynchronous implementation of Attachment for ServiceNow.
"""

import logging
from typing import Optional, Dict, Any, List, Union, TYPE_CHECKING, BinaryIO

if TYPE_CHECKING:
    from .client import AsyncServiceNowClient


class AsyncAttachment:
    """
    Asynchronous implementation of Attachment for ServiceNow.
    
    This class provides an async interface for working with ServiceNow attachments.
    """
    
    def __init__(self, client: 'AsyncServiceNowClient', table: str):
        """
        Initialize a new AsyncAttachment
        
        :param client: The AsyncServiceNowClient instance
        :param table: The table name the attachment belongs to
        """
        self._log = logging.getLogger(__name__)
        self.__client = client
        self.__table = table
        self.__table_sys_id = None
        self.__sys_id = None
        self.__file_name = None
        self.__content_type = None
        self.__size_bytes = None
        self.__download_link = None
    
    @property
    def table(self) -> str:
        """Get the table name"""
        return self.__table
    
    @property
    def table_sys_id(self) -> Optional[str]:
        """Get the table record sys_id"""
        return self.__table_sys_id
    
    @table_sys_id.setter
    def table_sys_id(self, value: str) -> None:
        """Set the table record sys_id"""
        self.__table_sys_id = value
    
    @property
    def sys_id(self) -> Optional[str]:
        """Get the attachment sys_id"""
        return self.__sys_id
    
    @sys_id.setter
    def sys_id(self, value: str) -> None:
        """Set the attachment sys_id"""
        self.__sys_id = value
    
    @property
    def file_name(self) -> Optional[str]:
        """Get the file name"""
        return self.__file_name
    
    @file_name.setter
    def file_name(self, value: str) -> None:
        """Set the file name"""
        self.__file_name = value
    
    @property
    def content_type(self) -> Optional[str]:
        """Get the content type"""
        return self.__content_type
    
    @content_type.setter
    def content_type(self, value: str) -> None:
        """Set the content type"""
        self.__content_type = value
    
    @property
    def size_bytes(self) -> Optional[int]:
        """Get the file size in bytes"""
        return self.__size_bytes
    
    @size_bytes.setter
    def size_bytes(self, value: int) -> None:
        """Set the file size in bytes"""
        self.__size_bytes = value
    
    @property
    def download_link(self) -> Optional[str]:
        """Get the download link"""
        return self.__download_link
    
    @download_link.setter
    def download_link(self, value: str) -> None:
        """Set the download link"""
        self.__download_link = value
    
    async def get(self, sys_id: str) -> bool:
        """
        Get an attachment by sys_id
        
        :param sys_id: The sys_id of the attachment to retrieve
        :return: True if attachment was found, False otherwise
        """
        if not sys_id:
            return False
        
        response = await self.__client.attachment_api.get(sys_id)
        data = response.json()
        
        if 'result' not in data:
            return False
        
        result = data['result']
        if not result:
            return False
        
        self.__sys_id = sys_id
        self.__file_name = result.get('file_name')
        self.__content_type = result.get('content_type')
        self.__size_bytes = int(result.get('size_bytes', 0))
        self.__download_link = result.get('download_link')
        self.__table = result.get('table_name')
        self.__table_sys_id = result.get('table_sys_id')
        
        return True
    
    async def get_file(self, sys_id: Optional[str] = None, stream: bool = True):
        """
        Get the file content of an attachment
        
        :param sys_id: The sys_id of the attachment (uses current sys_id if None)
        :param stream: Whether to stream the response
        :return: Response object with the file content
        """
        sys_id = sys_id or self.__sys_id
        if not sys_id:
            raise ValueError("No sys_id specified")
        
        return await self.__client.attachment_api.get_file(sys_id, stream=stream)
    
    async def upload(self, file_name: str, file_obj: BinaryIO, content_type: Optional[str] = None, encryption_context: Optional[str] = None) -> Optional[str]:
        """
        Upload a file as an attachment
        
        :param file_name: Name of the file
        :param file_obj: File object or bytes
        :param content_type: MIME type of the file
        :param encryption_context: Encryption context
        :return: sys_id of the created attachment, or None if upload failed
        """
        if not self.__table_sys_id:
            raise ValueError("table_sys_id must be set before uploading")
        
        response = await self.__client.attachment_api.upload_file(
            file_name=file_name,
            table_name=self.__table,
            table_sys_id=self.__table_sys_id,
            file=file_obj,
            content_type=content_type,
            encryption_context=encryption_context
        )
        
        data = response.json()
        
        if 'result' not in data:
            return None
        
        result = data['result']
        if not result:
            return None
        
        self.__sys_id = result.get('sys_id')
        self.__file_name = result.get('file_name', file_name)
        self.__content_type = result.get('content_type', content_type)
        self.__size_bytes = int(result.get('size_bytes', 0))
        self.__download_link = result.get('download_link')
        
        return self.__sys_id
    
    async def delete(self, sys_id: Optional[str] = None) -> bool:
        """
        Delete an attachment
        
        :param sys_id: The sys_id of the attachment to delete (uses current sys_id if None)
        :return: True if delete was successful, False otherwise
        """
        sys_id = sys_id or self.__sys_id
        if not sys_id:
            raise ValueError("No sys_id specified")
        
        response = await self.__client.attachment_api.delete(sys_id)
        
        if response.status_code == 204:
            if sys_id == self.__sys_id:
                self.__sys_id = None
                self.__file_name = None
                self.__content_type = None
                self.__size_bytes = None
                self.__download_link = None
            return True
        return False
    
    async def list(self) -> List[Dict[str, Any]]:
        """
        List all attachments for the current table and record
        
        :return: List of attachment metadata dictionaries
        """
        if not self.__table_sys_id:
            raise ValueError("table_sys_id must be set before listing attachments")
        
        response = await self.__client.attachment_api.list(self)
        data = response.json()
        
        if 'result' not in data:
            return []
        
        return data['result']
    
    def __str__(self) -> str:
        """String representation"""
        if self.__sys_id:
            return f"Attachment(sys_id={self.__sys_id}, file_name={self.__file_name}, size={self.__size_bytes})"
        return "Attachment(no current attachment)"
