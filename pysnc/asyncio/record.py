"""
Asynchronous implementation of GlideRecord for ServiceNow.
"""

import logging
import copy
import traceback
from collections import OrderedDict
from datetime import datetime, timezone
from typing import Any, Union, List, Optional, Dict, TYPE_CHECKING, Callable

from ..query import *
from ..exceptions import *
from ..record import GlideElement, TIMESTAMP_FORMAT

if TYPE_CHECKING:
    from .client import AsyncServiceNowClient
    from .attachment import AsyncAttachment


class AsyncGlideRecord:
    """
    Asynchronous implementation of GlideRecord for ServiceNow.
    
    This class provides an async interface for querying and manipulating ServiceNow records.
    """
    
    def __init__(self, client: 'AsyncServiceNowClient', table: str, batch_size=100, rewindable=True):
        """
        Initialize a new AsyncGlideRecord
        
        :param client: The AsyncServiceNowClient instance
        :param table: The table name to query
        :param batch_size: Number of records to fetch per request
        :param rewindable: Whether the record set can be rewound
        """
        self._log = logging.getLogger(__name__)
        self.__client = client
        self.__table = table
        self.__batch_size = batch_size
        self.__rewindable = rewindable
        
        # Query parameters
        self.__query = []
        self.__encoded_query = None
        self.__fields = []
        self.__limit = None
        self.__offset = 0
        self.__display_value = None
        self.__exclude_reference_link = None
        
        # Results
        self.__results = []
        self.__current = -1
        self.__total = None
        self.__is_iter = False
        
        # Current record state
        self.__new_record = {}
        self.__changes = {}
        self.__sys_id = None
    
    @property
    def table(self) -> str:
        """Get the table name"""
        return self.__table
    
    @property
    def sys_id(self) -> Optional[str]:
        """Get the current record's sys_id"""
        return self.__sys_id
    
    @property
    def encoded_query(self) -> Optional[str]:
        """Get the encoded query string"""
        return self.__encoded_query
    
    @property
    def fields(self) -> List[str]:
        """Get the list of fields to query"""
        return self.__fields
    
    @property
    def display_value(self) -> Optional[str]:
        """Get the display value parameter"""
        return self.__display_value
    
    @property
    def exclude_reference_link(self) -> Optional[bool]:
        """Get the exclude reference link parameter"""
        return self.__exclude_reference_link
    
    @property
    def limit(self) -> Optional[int]:
        """Get the query limit"""
        return self.__limit
    
    @property
    def offset(self) -> int:
        """Get the query offset"""
        return self.__offset
    
    def add_query(self, field: str, operator: str = None, value: Any = None) -> None:
        """
        Add a query condition
        
        :param field: Field name or encoded query string
        :param operator: Operator (=, !=, >, <, etc.)
        :param value: Value to compare against
        """
        if operator is None and value is None:
            # Encoded query
            self.__encoded_query = field
        else:
            # Field query
            if operator is None:
                operator = '='
            self.__query.append(QueryCondition(field, operator, value))
    
    def add_encoded_query(self, query: str) -> None:
        """
        Add an encoded query string
        
        :param query: The encoded query string
        """
        self.__encoded_query = query
    
    def add_query_or(self) -> None:
        """Add an OR condition to the query"""
        self.__query.append(QueryConditionOr())
    
    def add_active_query(self) -> None:
        """Add a query condition for active records"""
        self.add_query('active', '=', 'true')
    
    def add_not_null_query(self, field: str) -> None:
        """
        Add a query condition for non-null field
        
        :param field: Field name
        """
        self.add_query(field, 'ISNOTEMPTY')
    
    def add_null_query(self, field: str) -> None:
        """
        Add a query condition for null field
        
        :param field: Field name
        """
        self.add_query(field, 'ISEMPTY')
    
    def set_limit(self, limit: int) -> None:
        """
        Set the query limit
        
        :param limit: Maximum number of records to return
        """
        self.__limit = limit
    
    def set_display_value(self, value: Union[bool, str]) -> None:
        """
        Set whether to include display values
        
        :param value: True, False, or 'all'
        """
        self.__display_value = value
    
    def set_exclude_reference_link(self, value: bool) -> None:
        """
        Set whether to exclude reference links
        
        :param value: True or False
        """
        self.__exclude_reference_link = value
    
    def add_fields(self, *fields: str) -> None:
        """
        Add fields to query
        
        :param fields: Field names to include
        """
        for field in fields:
            if field not in self.__fields:
                self.__fields.append(field)
    
    def initialize(self) -> None:
        """Initialize a new record"""
        self.__new_record = {}
        self.__changes = {}
        self.__sys_id = None
    
    def get_element(self, field: str) -> GlideElement:
        """
        Get a field as a GlideElement
        
        :param field: Field name
        :return: GlideElement instance
        """
        obj = self._current()
        if obj and field in obj:
            return obj[field]
        
        # If we're creating a new record or the field doesn't exist
        if field not in self.__new_record:
            self.__new_record[field] = GlideElement(field, None, parent_record=self)
        return self.__new_record[field]
    
    def get_value(self, field: str) -> Any:
        """
        Get a field value
        
        :param field: Field name
        :return: Field value
        """
        return self.get_element(field).get_value()
    
    def get_display_value(self, field: str) -> Any:
        """
        Get a field's display value
        
        :param field: Field name
        :return: Field display value
        """
        return self.get_element(field).get_display_value()
    
    def set_value(self, field: str, value: Any) -> None:
        """
        Set a field value
        
        :param field: Field name
        :param value: Value to set
        """
        if field not in self.__new_record:
            self.__new_record[field] = GlideElement(field, None, parent_record=self)
        self.__new_record[field].set_value(value)
        self.__changes[field] = self.__new_record[field]
    
    def set_display_value(self, field: str, value: Any) -> None:
        """
        Set a field's display value
        
        :param field: Field name
        :param value: Display value to set
        """
        if field not in self.__new_record:
            self.__new_record[field] = GlideElement(field, None, parent_record=self)
        self.__new_record[field].set_display_value(value)
        self.__changes[field] = self.__new_record[field]
    
    def _current(self) -> Optional[Dict[str, GlideElement]]:
        """Get the current record"""
        if self.__current >= 0 and self.__current < len(self.__results) and self.__results[self.__current] is not None:
            return self.__results[self.__current]
        return None
    
    def _transform_result(self, result: Dict[str, Any]) -> Dict[str, GlideElement]:
        """
        Transform a raw result into GlideElements
        
        :param result: Raw result dictionary
        :return: Dictionary of GlideElements
        """
        for key, value in result.items():
            result[key] = GlideElement(key, value, parent_record=self)
        return result
    
    async def _do_query(self) -> None:
        """Execute the query and fetch results"""
        if self.__encoded_query is None and self.__query:
            self.__encoded_query = str(QueryBuilder(self.__query))
        
        response = await self.__client.table_api.list(self)
        data = response.json()

        if 'result' not in data:
            self._log.warning(f"No results found in response: {data}")
            return
        
        results = data['result']
        
        if isinstance(results, dict):
            # Single result
            self.__results.append(self._transform_result(results))
        elif isinstance(results, list):
            # Multiple results
            for result in results:
                self.__results.append(self._transform_result(result))

        # Update total count if available
        if 'count' in data:
            self.__total = int(data['count'])
        else:
            self.__total = len(results)
        
        # Update offset for pagination
        self.__offset += len(results)
    
    async def get(self, sys_id: str) -> bool:
        """
        Get a record by sys_id
        
        :param sys_id: The sys_id of the record to retrieve
        :return: True if record was found, False otherwise
        """
        if not sys_id:
            return False
        
        response = await self.__client.table_api.get(self, sys_id)
        data = response.json()
        
        if 'result' not in data:
            return False
        
        result = data['result']
        if not result:
            return False
        
        self.__results = [self._transform_result(result)]
        self.__current = 0
        self.__sys_id = sys_id
        return True
    
    async def query(self) -> bool:
        """
        Execute the query and position at the first result
        
        :return: True if records were found, False otherwise
        """
        self.__results = []
        self.__current = -1
        self.__total = None
        
        await self._do_query()
        
        if len(self.__results) > 0:
            return True
        return False
    
    def rewind(self) -> None:
        """Rewind to the beginning of the result set"""
        if len(self.__results) > 0:
            self.__current = 0
            self.__sys_id = self.get_value('sys_id')
    
    async def next(self) -> bool:
        """
        Move to the next record
        
        :return: True if moved to next record, False if no more records
        """
        l = len(self.__results)
        if l > 0 and self.__current + 1 < l:
            self.__current = self.__current + 1
            self.__sys_id = self.get_value('sys_id')
            return True
        
        if self.__total and self.__total > 0 and \
                (self.__current + 1) < self.__total and \
                self.__total > len(self.__results):
            if self.__limit:
                if self.__current + 1 < self.__limit:
                    await self._do_query()
                    return await self.next()
            else:
                await self._do_query()
                return await self.next()
        
        return False
    
    async def has_next(self) -> bool:
        """
        Check if there are more records
        
        :return: True if more records exist, False otherwise
        """
        l = len(self.__results)
        if l > 0 and self.__current + 1 < l:
            return True
        
        # Check if we need to fetch more records
        if self.__total and self.__total > 0 and \
                (self.__current + 1) < self.__total and \
                self.__total > len(self.__results):
            return True
        
        return False
    
    async def insert(self) -> Optional[str]:
        """
        Insert a new record
        
        :return: sys_id of the inserted record, or None if insert failed
        """
        response = await self.__client.table_api.post(self)
        data = response.json()
        
        if 'result' not in data:
            return None
        
        result = data['result']
        if not result:
            return None
        
        self.__results = [self._transform_result(result)]
        self.__current = 0
        self.__sys_id = result.get('sys_id')
        return self.__sys_id
    
    async def update(self) -> bool:
        """
        Update the current record
        
        :return: True if update was successful, False otherwise
        """
        if not self.__sys_id:
            return False
        
        response = await self.__client.table_api.patch(self)
        data = response.json()
        
        if 'result' not in data:
            return False
        
        result = data['result']
        if not result:
            return False
        
        self.__results[self.__current] = self._transform_result(result)
        return True
    
    async def delete(self) -> bool:
        """
        Delete the current record
        
        :return: True if delete was successful, False otherwise
        """
        if not self.__sys_id:
            return False
        
        response = await self.__client.table_api.delete(self)
        
        if response.status_code == 204:
            # Successfully deleted
            if self.__current < len(self.__results):
                self.__results[self.__current] = None
            return True
        return False
    
    def serialize(self, changes_only=False) -> Dict[str, Any]:
        """
        Serialize the record for API requests
        
        :param changes_only: Whether to include only changed fields
        :return: Dictionary of serialized fields
        """
        if changes_only:
            return {k: v.get_value() for k, v in self.__changes.items()}
        
        result = {}
        current = self._current()
        
        if current:
            # Include all fields from current record
            for k, v in current.items():
                if k in self.__changes:
                    # Use changed value
                    result[k] = self.__changes[k].get_value()
                else:
                    # Use original value
                    result[k] = v.get_value()
        
        # Add any new fields
        for k, v in self.__new_record.items():
            if k not in result:
                result[k] = v.get_value()
        
        return result
    

    def __aiter__(self):
        """Return the async iterator object (no awaits here)."""
        return self
    
    async def __anext__(self):
        """Advance and return the current record each iteration."""
        # if not self.__started:
        #     # Prime on first iteration
        #     self.__started = True
        #     await self._do_query()
        #     if not self.__results:
        #         # nothing to iterate
        #         raise StopAsyncIteration
        #     self.__current = 0
        #     self.__sys_id = self.get_value('sys_id')
        #     return self  # yield first record (position 0)

        # Subsequent iterations: move to next record
        has_next = await self.next()   # must advance internal cursor to next record
        if not has_next:
            # we've already yielded the final record on the previous call
            raise StopAsyncIteration

        return self  # yield the newly-current record
    
    def __str__(self):
        """String representation"""
        current = self._current()
        if current:
            fields = ", ".join(f"{k}={v}" for k, v in current.items())
            return f"{self.__table}({fields})"
        return f"{self.__table}(no current record)"
    
    def __getattr__(self, item):
        """Get attribute or field value"""
        if item.startswith('_'):
            raise AttributeError(f"No such attribute: {item}")
        
        return self.get_element(item)
    
    def __setattr__(self, key, value):
        """Set attribute or field value"""
        if key.startswith('_'):
            # Internal attribute
            super(AsyncGlideRecord, self).__setattr__(key, value)
        else:
            # Field value
            self.set_value(key, value)

    def __len__(self):
        return self.get_row_count()

    def get_row_count(self) -> int:
        """
        Glide compatable method.

        :return: the total
        """
        return self.__total if self.__total is not None else 0
