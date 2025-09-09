#!/usr/bin/env python3
"""
Local Token Analysis - Analyze JSONL files for token counts without API calls
"""

import json
import glob
from pathlib import Path
from typing import Dict, List, Any

def analyze_jsonl_file_detailed(file_path: str) -> Dict[str, Any]:
    """Analyze token counts from JSONL file entries with detailed breakdown"""
    results = {
        "file_path": file_path,
        "file_size_mb": round(Path(file_path).stat().st_size / (1024 * 1024), 2),
        "total_lines": 0,
        "processed_lines": 0,
        "tokens": {
            "input_tokens": 0,
            "output_tokens": 0,
            "cache_creation_tokens": 0,
            "cache_read_tokens": 0,
        },
        "message_types": {
            "user": 0,
            "assistant": 0,
            "system": 0,
            "tool": 0,
            "other": 0
        },
        "usage_entries_found": 0,
        "recent_entries": []
    }
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f):
                results["total_lines"] += 1
                
                # Show progress for large files
                if line_num > 0 and line_num % 1000 == 0:
                    print(f"   Processing line {line_num}...")
                
                try:
                    entry = json.loads(line.strip())
                    results["processed_lines"] += 1
                    
                    # Track message types
                    entry_type = entry.get("type", "other")
                    if entry_type in results["message_types"]:
                        results["message_types"][entry_type] += 1
                    else:
                        results["message_types"]["other"] += 1
                    
                    # Look for usage data
                    usage = None
                    if entry.get("type") == "assistant":
                        usage = entry.get("message", {}).get("usage", {})
                    elif "usage" in entry:
                        usage = entry["usage"]
                    
                    if usage and any(usage.get(key, 0) > 0 for key in ["input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"]):
                        results["usage_entries_found"] += 1
                        
                        # Accumulate tokens
                        results["tokens"]["input_tokens"] += usage.get("input_tokens", 0)
                        results["tokens"]["output_tokens"] += usage.get("output_tokens", 0) 
                        results["tokens"]["cache_creation_tokens"] += usage.get("cache_creation_input_tokens", 0)
                        results["tokens"]["cache_read_tokens"] += usage.get("cache_read_input_tokens", 0)
                        
                        # Store recent usage entries for inspection
                        if len(results["recent_entries"]) < 5:
                            results["recent_entries"].append({
                                "line": line_num + 1,
                                "type": entry_type,
                                "usage": usage,
                                "timestamp": entry.get("timestamp", "unknown")
                            })
                        
                except json.JSONDecodeError:
                    continue
                except Exception as e:
                    print(f"   Error on line {line_num + 1}: {e}")
                    continue
                    
    except Exception as e:
        results["error"] = str(e)
    
    # Calculate totals
    tokens = results["tokens"]
    results["total_tokens"] = sum(tokens.values())
    
    return results

def main():
    """Analyze token counts from local JSONL files"""
    print("🔍 Local JSONL Token Analysis")
    print("=" * 70)
    
    # Find all JSONL files
    patterns = [
        "/Users/markelmore/.claude/projects/*fowldata*/*.jsonl",
        "/Users/markelmore/.claude/projects/*context*cleaner*/*.jsonl"
    ]
    
    all_files = []
    for pattern in patterns:
        all_files.extend(glob.glob(pattern))
    
    if not all_files:
        print("❌ No JSONL files found!")
        return
    
    print(f"📁 Found {len(all_files)} JSONL files")
    
    grand_totals = {
        "input_tokens": 0,
        "output_tokens": 0,
        "cache_creation_tokens": 0,
        "cache_read_tokens": 0,
        "total_files": 0,
        "total_usage_entries": 0,
        "total_file_size_mb": 0
    }
    
    for file_path in all_files:
        print(f"\n📄 Analyzing: {Path(file_path).name}")
        
        result = analyze_jsonl_file_detailed(file_path)
        
        if "error" in result:
            print(f"   ❌ Error: {result['error']}")
            continue
        
        # Display results
        print(f"   📊 File Stats:")
        print(f"      Size: {result['file_size_mb']} MB")
        print(f"      Lines: {result['total_lines']:,} total, {result['processed_lines']:,} processed")
        print(f"      Usage entries: {result['usage_entries_found']}")
        
        print(f"   🗂️  Message Types:")
        for msg_type, count in result['message_types'].items():
            if count > 0:
                print(f"      {msg_type}: {count:,}")
        
        print(f"   🎯 Token Counts:")
        tokens = result["tokens"]
        print(f"      Input: {tokens['input_tokens']:,}")
        print(f"      Output: {tokens['output_tokens']:,}")
        print(f"      Cache Creation: {tokens['cache_creation_tokens']:,}")
        print(f"      Cache Read: {tokens['cache_read_tokens']:,}")
        print(f"      TOTAL: {result['total_tokens']:,}")
        
        # Show recent entries
        if result["recent_entries"]:
            print(f"   📝 Recent Usage Entries:")
            for i, entry in enumerate(result["recent_entries"][:3], 1):
                usage = entry["usage"]
                print(f"      {i}. Line {entry['line']} ({entry['type']}): {usage.get('input_tokens', 0):,}+{usage.get('output_tokens', 0):,} tokens")
        
        # Add to grand totals
        grand_totals["input_tokens"] += tokens["input_tokens"]
        grand_totals["output_tokens"] += tokens["output_tokens"]
        grand_totals["cache_creation_tokens"] += tokens["cache_creation_tokens"]
        grand_totals["cache_read_tokens"] += tokens["cache_read_tokens"]
        grand_totals["total_usage_entries"] += result["usage_entries_found"]
        grand_totals["total_file_size_mb"] += result["file_size_mb"]
        grand_totals["total_files"] += 1
    
    # Grand total summary
    total_all_tokens = sum([
        grand_totals["input_tokens"],
        grand_totals["output_tokens"], 
        grand_totals["cache_creation_tokens"],
        grand_totals["cache_read_tokens"]
    ])
    
    print(f"\n{'=' * 70}")
    print(f"🎯 GRAND TOTALS ACROSS ALL FILES:")
    print(f"   Files Analyzed: {grand_totals['total_files']}")
    print(f"   Total File Size: {grand_totals['total_file_size_mb']:.1f} MB")
    print(f"   Usage Entries Found: {grand_totals['total_usage_entries']:,}")
    print(f"   ")
    print(f"   📊 TOKEN BREAKDOWN:")
    print(f"      Input Tokens: {grand_totals['input_tokens']:,}")
    print(f"      Output Tokens: {grand_totals['output_tokens']:,}")
    print(f"      Cache Creation: {grand_totals['cache_creation_tokens']:,}")
    print(f"      Cache Read: {grand_totals['cache_read_tokens']:,}")
    print(f"      ")
    print(f"   🚀 TOTAL TOKENS: {total_all_tokens:,}")
    
    # Analysis
    if total_all_tokens > 0:
        print(f"\n🔍 ANALYSIS:")
        
        if total_all_tokens < 10_000_000:  # Less than 10M tokens
            print(f"   ⚠️  SIGNIFICANTLY LOW: Only {total_all_tokens:,} tokens found")
            print(f"   This suggests major undercount if you processed 44.5M tokens recently")
            print(f"   Possible issues:")
            print(f"   - JSONL files don't contain complete usage data")
            print(f"   - Usage data is stored elsewhere (telemetry, logs)")
            print(f"   - Token counting method is missing data sources")
        
        elif total_all_tokens < 30_000_000:  # Less than 30M
            print(f"   ⚠️  MODERATE UNDERCOUNT: {total_all_tokens:,} tokens found")
            print(f"   Still significantly less than expected 44.5M")
            
        else:
            print(f"   ✅ REASONABLE COUNT: {total_all_tokens:,} tokens found")
            print(f"   This is closer to expected usage levels")
        
        # Check data sources
        cache_tokens = grand_totals["cache_creation_tokens"] + grand_totals["cache_read_tokens"]
        if cache_tokens > total_all_tokens * 0.5:
            print(f"   📈 Cache tokens represent {(cache_tokens/total_all_tokens)*100:.1f}% of total")
            print(f"   This suggests heavy prompt caching usage")
        
        print(f"\n💡 RECOMMENDATIONS:")
        print(f"   1. Check if telemetry/logs contain additional token data")
        print(f"   2. Verify JSONL files contain all conversation sessions")
        print(f"   3. Look for token usage in tool calls and system messages")
        print(f"   4. Consider checking Anthropic Console for actual usage")

if __name__ == "__main__":
    main()