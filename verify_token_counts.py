#!/usr/bin/env python3
"""
Direct Claude API Token Count Verification Tool
Compares our internal counts against Anthropic's actual count-tokens API
"""

import json
import os
import sys
import requests
from pathlib import Path
from typing import Dict, List, Any, Tuple
from datetime import datetime

PROJECT_ROOT = Path(os.environ.get("CLAUDE_PROJECT_ROOT", Path.home() / ".claude" / "projects")).expanduser()

def create_script_error(message: str, error_code: str = "SCRIPT_ERROR") -> dict:
    """Create standardized error dict for script usage"""
    return {
        "error": message,
        "error_code": error_code,
        "timestamp": datetime.now().isoformat()
    }

def create_script_no_data_error(data_type: str) -> dict:
    """Create standardized no data error for script usage"""
    return create_script_error(f"No {data_type} found", "NO_DATA_AVAILABLE")

def get_anthropic_api_key() -> str:
    """Get Anthropic API key from environment"""
    api_key = os.environ.get('ANTHROPIC_API_KEY')
    if not api_key:
        print("❌ ANTHROPIC_API_KEY not found in environment")
        print("Please set: export ANTHROPIC_API_KEY=your_key_here")
        sys.exit(1)
    return api_key

def call_anthropic_count_tokens(messages: List[Dict], model: str = "claude-3-5-sonnet-20241022") -> Dict:
    """Call Anthropic's count-tokens API directly"""
    api_key = get_anthropic_api_key()
    
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json"
    }
    
    payload = {
        "model": model,
        "messages": messages
    }
    
    try:
        response = requests.post(
            "https://api.anthropic.com/v1/messages/count_tokens",
            headers=headers,
            json=payload,
            timeout=30
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"❌ API Error: {e}")
        return create_script_error(str(e), "API_REQUEST_ERROR")

def parse_jsonl_conversation(file_path: str, max_messages: int = 10) -> List[Dict]:
    """Parse JSONL file and extract conversation messages for API verification"""
    messages = []
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f):
                if line_num >= max_messages * 2:  # Rough limit to avoid huge API calls
                    break
                    
                try:
                    entry = json.loads(line.strip())
                    entry_type = entry.get("type", "")
                    
                    if entry_type == "user":
                        # User message
                        content = entry.get("message", {}).get("content", "")
                        if isinstance(content, list) and content:
                            # Handle structured content
                            text_parts = []
                            for item in content:
                                if isinstance(item, dict) and item.get("type") == "text":
                                    text_parts.append(item.get("text", ""))
                            content = " ".join(text_parts)
                        elif isinstance(content, str):
                            pass  # Already string
                        else:
                            content = str(content)
                        
                        if content.strip():
                            messages.append({
                                "role": "user",
                                "content": content[:2000]  # Truncate very long messages
                            })
                    
                    elif entry_type == "assistant":
                        # Assistant message
                        content = entry.get("message", {}).get("content", "")
                        if isinstance(content, list) and content:
                            text_parts = []
                            for item in content:
                                if isinstance(item, dict) and item.get("type") == "text":
                                    text_parts.append(item.get("text", ""))
                            content = " ".join(text_parts)
                        elif isinstance(content, str):
                            pass
                        else:
                            content = str(content)
                        
                        if content.strip():
                            messages.append({
                                "role": "assistant", 
                                "content": content[:2000]  # Truncate very long messages
                            })
                    
                    # Stop when we have enough messages for a good sample
                    if len(messages) >= max_messages:
                        break
                        
                except json.JSONDecodeError:
                    continue
    except Exception as e:
        print(f"❌ Error reading {file_path}: {e}")
        return []
    
    return messages

def analyze_jsonl_file_tokens(file_path: str) -> Dict[str, Any]:
    """Analyze token counts from JSONL file entries (our current method)"""
    total_input = 0
    total_output = 0
    total_cache_creation = 0
    total_cache_read = 0
    message_count = 0
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    entry = json.loads(line.strip())
                    
                    # Look for usage data in different places
                    usage = None
                    if entry.get("type") == "assistant":
                        usage = entry.get("message", {}).get("usage", {})
                    elif "usage" in entry:
                        usage = entry["usage"]
                    
                    if usage:
                        total_input += usage.get("input_tokens", 0)
                        total_output += usage.get("output_tokens", 0) 
                        total_cache_creation += usage.get("cache_creation_input_tokens", 0)
                        total_cache_read += usage.get("cache_read_input_tokens", 0)
                        message_count += 1
                        
                except json.JSONDecodeError:
                    continue
    except Exception as e:
        return create_script_error(str(e), "API_REQUEST_ERROR")
    
    return {
        "our_method": {
            "input_tokens": total_input,
            "output_tokens": total_output,
            "cache_creation_tokens": total_cache_creation,
            "cache_read_tokens": total_cache_read,
            "total_tokens": total_input + total_output + total_cache_creation + total_cache_read,
            "message_count": message_count
        }
    }

def verify_file_token_counts(file_path: str, sample_size: int = 5) -> Dict[str, Any]:
    """Compare our token counting against Anthropic's API for a specific file"""
    print(f"🔍 Analyzing file: {Path(file_path).name}")
    
    # Get our current method's count for the entire file
    our_analysis = analyze_jsonl_file_tokens(file_path)
    if "error" in our_analysis:
        return create_script_error(f"Failed to analyze file: {our_analysis['error']}", "FILE_ANALYSIS_ERROR")
    
    # Get a sample conversation for API verification
    sample_messages = parse_jsonl_conversation(file_path, sample_size)
    if not sample_messages:
        return create_script_no_data_error("valid messages for API verification")
    
    print(f"📝 Sample conversation: {len(sample_messages)} messages")
    
    # Call Anthropic API for verification
    api_result = call_anthropic_count_tokens(sample_messages)
    if "error" in api_result:
        return create_script_error(f"API call failed: {api_result['error']}", "API_CALL_FAILED")
    
    return {
        "file_path": file_path,
        "our_analysis": our_analysis["our_method"],
        "api_verification": {
            "sample_size": len(sample_messages),
            "api_response": api_result
        }
    }

def main():
    """Run verification against multiple files"""
    print("🚀 Claude API Token Count Verification")
    print("=" * 60)
    
    # Test files
    import glob
    fowldata_glob = str(PROJECT_ROOT / "*fowldata*" / "*.jsonl")
    context_cleaner_glob = str(PROJECT_ROOT / "*context*cleaner*" / "*.jsonl")

    test_files = []
    fowldata_files = glob.glob(fowldata_glob)
    if fowldata_files:
        test_files.append(fowldata_files[0])

    context_files = glob.glob(context_cleaner_glob)
    if context_files:
        test_files.extend(context_files[:2])  # Add up to two context-cleaner files
    
    total_our_tokens = 0
    total_api_verified = 0
    
    for file_path in test_files:
        if not Path(file_path).exists():
            print(f"⚠️  File not found: {file_path}")
            continue
            
        result = verify_file_token_counts(file_path, sample_size=8)
        
        if "error" in result:
            print(f"❌ {result['error']}")
            continue
        
        our_total = result["our_analysis"]["total_tokens"]
        api_sample = result["api_verification"]["api_response"]
        
        total_our_tokens += our_total
        
        print(f"\n📊 Results for {Path(file_path).name}:")
        print(f"   Our Method Total: {our_total:,} tokens")
        print(f"   - Input: {result['our_analysis']['input_tokens']:,}")
        print(f"   - Output: {result['our_analysis']['output_tokens']:,}")
        print(f"   - Cache Creation: {result['our_analysis']['cache_creation_tokens']:,}")
        print(f"   - Cache Read: {result['our_analysis']['cache_read_tokens']:,}")
        print(f"   - Messages Counted: {result['our_analysis']['message_count']}")
        
        if "input_tokens" in api_sample:
            sample_total = api_sample.get("input_tokens", 0)
            total_api_verified += sample_total
            print(f"\n   API Verification (sample):")
            print(f"   - Sample Input Tokens: {sample_total:,}")
            print(f"   - Sample Messages: {result['api_verification']['sample_size']}")
            
            if sample_total > 0:
                ratio = our_total / sample_total if sample_total > 0 else 0
                print(f"   - Extrapolation Ratio: {ratio:.2f}x")
        else:
            print(f"   API Response: {api_sample}")
    
    print(f"\n{'='*60}")
    print(f"📈 SUMMARY:")
    print(f"   Total Our Method: {total_our_tokens:,} tokens")
    print(f"   API Verified Sample: {total_api_verified:,} tokens")
    
    if total_api_verified > 0:
        overall_ratio = total_our_tokens / total_api_verified
        print(f"   Overall Ratio: {overall_ratio:.2f}x")
        
        if overall_ratio < 0.5:
            print(f"   ⚠️  POTENTIAL UNDERCOUNT: Our method is significantly lower than API")
        elif overall_ratio > 2.0:
            print(f"   ⚠️  POTENTIAL OVERCOUNT: Our method is significantly higher than API")
        else:
            print(f"   ✅ Counts appear reasonable relative to API verification")

if __name__ == "__main__":
    main()
