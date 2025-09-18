"""Process complete JSONL content for database storage."""
import asyncio
from typing import List, Dict, Any
import logging

from .full_content_parser import FullContentJsonlParser
from .content_security import ContentSecurityManager
from context_cleaner.telemetry.clients.clickhouse_client import ClickHouseClient

logger = logging.getLogger(__name__)

class FullContentBatchProcessor:
    """Process complete JSONL content for database storage."""
    
    def __init__(self, clickhouse_client: ClickHouseClient, privacy_level: str = 'standard'):
        self.clickhouse = clickhouse_client
        self.privacy_level = privacy_level
        self.parser = FullContentJsonlParser()
        self.security_manager = ContentSecurityManager()
    
    async def process_jsonl_entries(self, entries: List[Dict[str, Any]]) -> Dict[str, int]:
        """Process JSONL entries and store complete content."""
        stats = {
            'messages_processed': 0,
            'files_processed': 0,
            'tools_processed': 0,
            'errors': 0
        }
        
        message_batch = []
        file_batch = []
        tool_batch = []
        
        for entry in entries:
            try:
                # Extract message content
                message_data = self.parser.extract_message_content(entry)
                if message_data:
                    # Sanitize content before storage
                    message_data['message_content'] = self.security_manager.sanitize_content(
                        message_data['message_content'], 
                        self.privacy_level
                    )
                    message_batch.append(message_data)
                
                # Extract file content
                file_data = self.parser.extract_file_content(entry)
                if file_data:
                    # Sanitize file content
                    file_data['file_content'] = self.security_manager.sanitize_content(
                        file_data['file_content'],
                        self.privacy_level
                    )
                    file_batch.append(file_data)
                
                # Extract tool results
                tool_data = self.parser.extract_tool_results(entry)
                if tool_data:
                    # Sanitize tool outputs
                    tool_data['tool_output'] = self.security_manager.sanitize_content(
                        tool_data['tool_output'],
                        self.privacy_level
                    )
                    if tool_data['tool_error']:
                        tool_data['tool_error'] = self.security_manager.sanitize_content(
                            tool_data['tool_error'],
                            self.privacy_level
                        )
                    tool_batch.append(tool_data)
                
            except Exception as e:
                logger.error(f"Error processing JSONL entry: {e}")
                stats['errors'] += 1
        
        # Batch insert into respective tables
        try:
            if message_batch:
                await self.clickhouse.bulk_insert('claude_message_content', message_batch)
                stats['messages_processed'] = len(message_batch)
            
            if file_batch:
                await self.clickhouse.bulk_insert('claude_file_content', file_batch)
                stats['files_processed'] = len(file_batch)
            
            if tool_batch:
                await self.clickhouse.bulk_insert('claude_tool_results', tool_batch)
                stats['tools_processed'] = len(tool_batch)
        
        except Exception as e:
            logger.error(f"Error during batch insert: {e}")
            stats['errors'] += 1
        
        return stats