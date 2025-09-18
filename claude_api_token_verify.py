#!/usr/bin/env python3
"""
Claude API Token Verification using Claude Code's authentication
Directly compares our counts against Anthropic's API using the same credentials
"""

import json
import requests
import asyncio
import aiohttp
from pathlib import Path
from typing import Dict, List, Any
import sys
import os
from datetime import datetime

# Add the project to path so we can import Claude Code modules
sys.path.insert(0, '/Users/markelmore/_code/context-cleaner/src')

def create_script_error(message: str, error_code: str = "SCRIPT_ERROR") -> dict:
    """Create standardized error dict for script usage"""
    return {
        "error": message,
        "error_code": error_code,
        "timestamp": datetime.now().isoformat()
    }

def create_script_no_data_error(data_type: str) -> dict:
    """Create standardized no data error for script usage"""
    return create_script_error(f"No {data_type} available", "NO_DATA_AVAILABLE")

def get_claude_api_credentials():
    """Get API credentials the same way Claude Code does"""
    try:
        # Check environment variables first
        api_key = os.environ.get('ANTHROPIC_API_KEY')
        if api_key:
            return api_key
        
        # Try to get from Claude Code configuration
        # This mimics how Claude Code gets its API key
        from pathlib import Path
        
        # Check common Claude Code config locations
        config_paths = [
            Path.home() / '.claude' / 'config.json',
            Path.home() / '.anthropic' / 'config.json',
            Path('/usr/local/etc/claude/config.json')
        ]
        
        for config_path in config_paths:
            if config_path.exists():
                try:
                    with open(config_path, 'r') as f:
                        config = json.load(f)
                        if 'api_key' in config:
                            return config['api_key']
                        if 'anthropic_api_key' in config:
                            return config['anthropic_api_key']
                except Exception as e:
                    continue
        
        print("⚠️  No explicit API key found - will try requests without authentication")
        print("   (This may work if Claude Code handles authentication transparently)")
        return None
        
    except Exception as e:
        print(f"❌ Could not get API credentials: {e}")
        return None

async def call_anthropic_count_tokens_async(messages: List[Dict], model: str = "claude-3-5-sonnet-20241022") -> Dict:
    """Call Anthropic's count-tokens API using async requests"""
    api_key = get_claude_api_credentials()
    if not api_key:
        return create_script_error("No API credentials available - need ANTHROPIC_API_KEY environment variable", "NO_CREDENTIALS")
    
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
        "User-Agent": "Claude-Code-Token-Verification/1.0"
    }
    
    payload = {
        "model": model,
        "messages": messages
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://api.anthropic.com/v1/messages/count_tokens",
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    error_text = await response.text()
                    return create_script_error(f"API error {response.status}: {error_text}", "API_ERROR")
    except Exception as e:
        return create_script_error(f"Request failed: {str(e)}", "REQUEST_FAILED")

def call_anthropic_count_tokens_sync(messages: List[Dict], model: str = "claude-3-5-sonnet-20241022") -> Dict:
    """Synchronous wrapper for the async API call"""
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(call_anthropic_count_tokens_async(messages, model))
        loop.close()
        return result
    except Exception as e:
        return create_script_error(f"Async call failed: {str(e)}", "ASYNC_FAILED")

def parse_recent_jsonl_messages(file_path: str, max_messages: int = 5) -> List[Dict]:
    """Parse recent messages from JSONL file for API verification"""
    messages = []
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            
        # Process from the end backwards to get recent messages
        for line in reversed(lines[-100:]):  # Look at last 100 lines
            if len(messages) >= max_messages:
                break
                
            try:
                entry = json.loads(line.strip())
                entry_type = entry.get("type", "")
                
                if entry_type in ["user", "assistant"]:
                    content = entry.get("message", {}).get("content", "")
                    
                    # Handle structured content
                    if isinstance(content, list) and content:
                        text_parts = []
                        for item in content:
                            if isinstance(item, dict) and item.get("type") == "text":
                                text_parts.append(item.get("text", ""))
                        content = " ".join(text_parts)
                    elif not isinstance(content, str):
                        content = str(content)
                    
                    if content.strip():
                        messages.insert(0, {  # Insert at beginning to maintain order
                            "role": "assistant" if entry_type == "assistant" else "user",
                            "content": content[:1500]  # Truncate to avoid huge API calls
                        })
                        
            except json.JSONDecodeError:
                continue
                
    except Exception as e:
        print(f"❌ Error reading {file_path}: {e}")
        return []
    
    return messages

def verify_single_file(file_path: str) -> Dict[str, Any]:
    """Verify token counts for a single JSONL file"""
    print(f"🔍 Verifying: {Path(file_path).name}")
    
    # Get recent messages for API verification
    sample_messages = parse_recent_jsonl_messages(file_path, 5)
    if not sample_messages:
        return create_script_no_data_error("valid messages")
    
    print(f"📝 Testing with {len(sample_messages)} recent messages")
    
    # Call Anthropic API
    api_result = call_anthropic_count_tokens_sync(sample_messages)
    
    if "error" in api_result:
        print(f"❌ API Error: {api_result['error']}")
        return create_script_error(api_result['error'], "API_VALIDATION_ERROR")
    
    # Show sample messages (first few words)
    print("📋 Sample messages tested:")
    for i, msg in enumerate(sample_messages[:3], 1):
        preview = msg["content"][:50] + "..." if len(msg["content"]) > 50 else msg["content"]
        print(f"   {i}. {msg['role']}: {preview}")
    
    return {
        "file": Path(file_path).name,
        "sample_count": len(sample_messages),
        "api_result": api_result
    }

def main():
    """Test token counting with real API calls"""
    print("🚀 Claude API Token Verification")
    print("Using Claude Code's authentication to verify token counts")
    print("=" * 70)
    
    # Test with recent FowlData file
    test_files = [
        "/Users/markelmore/.claude/projects/-Users-markelmore--code-fowldata/6559d7c1-f76b-4c92-8da5-79e1cd00a621.jsonl"
    ]
    
    # Add context-cleaner files if they exist
    import glob
    context_files = glob.glob("/Users/markelmore/.claude/projects/*context*cleaner*/*.jsonl")
    if context_files:
        test_files.extend(context_files[:1])  # Add one context-cleaner file
    
    print(f"📂 Testing {len(test_files)} files with live API calls...")
    
    for file_path in test_files:
        if not Path(file_path).exists():
            print(f"⚠️  File not found: {file_path}")
            continue
        
        print(f"\n{'-' * 50}")
        result = verify_single_file(file_path)
        
        if "error" in result:
            print(f"❌ Verification failed: {result['error']}")
            continue
        
        api_data = result["api_result"]
        
        if "input_tokens" in api_data:
            print(f"✅ API Response:")
            print(f"   📊 Input tokens: {api_data.get('input_tokens', 0):,}")
            if "output_tokens" in api_data:
                print(f"   📊 Output tokens: {api_data.get('output_tokens', 0):,}")
            
            # Calculate rough extrapolation
            sample_tokens = api_data.get('input_tokens', 0)
            if sample_tokens > 0:
                # Get file size for rough estimate
                file_size_mb = Path(file_path).stat().st_size / (1024 * 1024)
                print(f"   📁 File size: {file_size_mb:.1f} MB")
                
                # Very rough extrapolation based on sample
                lines_in_sample = result["sample_count"] * 2  # Rough estimate
                with open(file_path, 'r') as f:
                    total_lines = sum(1 for _ in f)
                
                if lines_in_sample > 0:
                    extrapolation = (sample_tokens * total_lines) // lines_in_sample
                    print(f"   🔢 Rough extrapolation: ~{extrapolation:,} tokens for full file")
                    print(f"   📏 Sample ratio: {lines_in_sample}/{total_lines} lines")
        else:
            print(f"📋 Full API Response: {api_data}")
    
    print(f"\n{'=' * 70}")
    print("💡 This verification shows what Anthropic's API actually counts")
    print("   for recent conversation samples. Compare with your dashboard")
    print("   numbers to identify discrepancies.")
    
    print(f"\n🎯 NEXT STEPS:")
    print(f"   1. Compare API results with dashboard totals")  
    print(f"   2. If API shows higher counts, investigate data collection")
    print(f"   3. Consider checking Anthropic Console for usage history")
    print(f"   4. Verify all JSONL files are being processed by dashboard")

if __name__ == "__main__":
    main()