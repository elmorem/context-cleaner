#!/usr/bin/env python3
"""
Context Cleaner - Claude Code Integration Installer

This script sets up Context Cleaner to work seamlessly with Claude Code,
providing productivity tracking and context optimization capabilities.
"""

import os
import sys
import json
import shutil
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any

class ClaudeIntegrationInstaller:
    """Installer for Context Cleaner integration with Claude Code."""
    
    def __init__(self):
        self.home_dir = Path.home()
        self.claude_dir = self.home_dir / ".claude"
        self.hooks_dir = self.claude_dir / "hooks"
        self.commands_dir = self.claude_dir / "commands"
        self.context_cleaner_dir = self.claude_dir / "context_cleaner"
        
    def check_claude_code_installation(self) -> bool:
        """Check if Claude Code is installed and configured."""
        print("🔍 Checking Claude Code installation...")
        
        # Check if .claude directory exists
        if not self.claude_dir.exists():
            print("❌ Claude Code not found. Please install Claude Code first.")
            print("   Visit: https://claude.ai/code for installation instructions")
            return False
            
        print("✅ Claude Code installation found")
        return True
    
    def check_context_cleaner_installation(self) -> bool:
        """Check if Context Cleaner is properly installed."""
        print("🔍 Checking Context Cleaner installation...")
        
        try:
            result = subprocess.run(['context-cleaner', '--help'], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                print("✅ Context Cleaner is installed and accessible")
                return True
            else:
                print("⚠️ Context Cleaner command not found in PATH")
                return False
        except FileNotFoundError:
            print("❌ Context Cleaner not installed. Please install with:")
            print("   pip install context-cleaner")
            return False
    
    def create_hooks_integration(self):
        """Create hooks for productivity tracking."""
        print("🔧 Setting up productivity tracking hooks...")
        
        # Create hooks directory if it doesn't exist
        self.hooks_dir.mkdir(parents=True, exist_ok=True)
        utils_dir = self.hooks_dir / "utils"
        utils_dir.mkdir(exist_ok=True)
        
        # Create advanced session tracking hook with circuit breaker protection
        session_hook = utils_dir / "context_cleaner_session_tracker.py"
        session_hook_content = '''#!/usr/bin/env python3
"""
Context Cleaner Advanced Session Tracker Hook

Integrates with Context Cleaner's HookIntegrationManager for comprehensive
productivity tracking with circuit breaker protection and encrypted storage.
"""

import sys
import json
import time
from datetime import datetime
from pathlib import Path

def get_hook_manager():
    """Get Context Cleaner hook manager with error handling."""
    try:
        # Import Context Cleaner components
        from context_cleaner.hooks import get_hook_manager
        return get_hook_manager()
    except ImportError:
        # Context Cleaner not installed or not in path
        return None
    except Exception:
        # Other errors - fail silently to never block Claude Code
        return None

def handle_session_start(hook_data: dict):
    """Handle session start event with circuit breaker protection."""
    try:
        hook_manager = get_hook_manager()
        if hook_manager:
            hook_manager.handle_session_start(hook_data)
    except Exception:
        # Never let hook failures affect Claude Code
        pass

def handle_session_end(hook_data: dict):
    """Handle session end event with circuit breaker protection."""
    try:
        hook_manager = get_hook_manager()
        if hook_manager:
            hook_manager.handle_session_end(hook_data)
    except Exception:
        # Never let hook failures affect Claude Code
        pass

def handle_context_change(hook_data: dict):
    """Handle context change event with circuit breaker protection."""
    try:
        hook_manager = get_hook_manager()
        if hook_manager:
            hook_manager.handle_context_change(hook_data)
    except Exception:
        # Never let hook failures affect Claude Code
        pass

def parse_hook_data(args):
    """Parse hook data from command line arguments."""
    try:
        # Hook data is typically passed as JSON in arguments
        for arg in args:
            if arg.startswith('{') and arg.endswith('}'):
                return json.loads(arg)
        
        # Fallback: create basic hook data
        return {
            'timestamp': datetime.now().isoformat(),
            'args': args,
            'hook_type': 'context_cleaner_session'
        }
    except Exception:
        return {}

def main():
    """Main hook execution with advanced session tracking."""
    try:
        # Parse hook data from arguments
        hook_data = parse_hook_data(sys.argv[1:])
        
        # Determine hook type from script name or arguments
        if 'session_start' in str(sys.argv) or hook_data.get('event_type') == 'session_start':
            handle_session_start(hook_data)
        elif 'session_end' in str(sys.argv) or hook_data.get('event_type') == 'session_end':
            handle_session_end(hook_data)
        else:
            # Default to context change tracking
            handle_context_change(hook_data)
        
        # Always exit successfully - never block Claude Code
        sys.exit(0)
        
    except Exception:
        # Never fail - always exit successfully to never interfere with Claude Code
        sys.exit(0)

if __name__ == "__main__":
    main()
'''
        session_hook.write_text(session_hook_content)
        session_hook.chmod(0o755)
        
        print("✅ Session tracking hook installed")
    
    def create_commands_integration(self):
        """Create command aliases for Context Cleaner functionality."""
        print("🔧 Setting up command integration...")
        
        # Create commands directory if it doesn't exist
        self.commands_dir.mkdir(parents=True, exist_ok=True)
        
        # Create optimize command wrapper
        optimize_cmd = self.commands_dir / "clean-context.py"
        optimize_cmd_content = '''#!/usr/bin/env python3
"""
Clean Context Command - Context Cleaner Integration

Provides /clean-context functionality through Context Cleaner.
"""

import sys
import subprocess
import argparse

def main():
    """Main command execution."""
    parser = argparse.ArgumentParser(description='Context optimization and health analysis')
    parser.add_argument('--dashboard', action='store_true', help='Show context health dashboard')
    parser.add_argument('--quick', action='store_true', help='Fast cleanup with safe defaults')
    parser.add_argument('--preview', action='store_true', help='Show proposed changes without applying')
    parser.add_argument('--aggressive', action='store_true', help='Maximum optimization')
    parser.add_argument('--focus', action='store_true', help='Reorder priorities without removing content')
    parser.add_argument('--format', choices=['text', 'json'], default='text', help='Output format')
    
    args = parser.parse_args()
    
    # Build Context Cleaner command
    cmd = ['context-cleaner', 'optimize']
    
    if args.dashboard:
        cmd.append('--dashboard')
    if args.quick:
        cmd.append('--quick') 
    if args.preview:
        cmd.append('--preview')
    if args.aggressive:
        cmd.append('--aggressive')
    if args.focus:
        cmd.append('--focus')
    if args.format:
        cmd.extend(['--format', args.format])
    
    try:
        # Execute Context Cleaner optimize command
        result = subprocess.run(cmd, capture_output=False)
        sys.exit(result.returncode)
    except Exception as e:
        print(f"❌ Context optimization failed: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
'''
        optimize_cmd.write_text(optimize_cmd_content)
        optimize_cmd.chmod(0o755)
        
        print("✅ Command integration installed")
    
    def create_config_integration(self):
        """Create Context Cleaner configuration for Claude Code integration."""
        print("🔧 Setting up configuration...")
        
        # Create Context Cleaner config directory
        self.context_cleaner_dir.mkdir(parents=True, exist_ok=True)
        
        config_file = self.context_cleaner_dir / "claude_integration.json"
        config_data = {
            "integration": {
                "claude_code_enabled": True,
                "hook_integration": True,
                "command_aliases": True,
                "productivity_tracking": True
            },
            "tracking": {
                "session_monitoring": True,
                "optimization_events": True,
                "productivity_analysis": True
            },
            "privacy": {
                "local_only": True,
                "encrypted_storage": True,
                "data_retention_days": 90
            }
        }
        
        with open(config_file, 'w') as f:
            json.dump(config_data, f, indent=2)
        
        print("✅ Configuration created")
    
    def add_track_session_command(self):
        """Add track-session command to Context Cleaner CLI."""
        print("🔧 Note: The 'track-session' command will be available in the next version")
        print("   Current integration uses existing commands for tracking")
    
    def run_installation(self) -> bool:
        """Run the complete installation process."""
        print("🚀 Context Cleaner - Claude Code Integration Installer")
        print("=" * 55)
        
        # Check prerequisites
        if not self.check_claude_code_installation():
            return False
            
        if not self.check_context_cleaner_installation():
            return False
        
        # Create integration components
        try:
            self.create_hooks_integration()
            self.create_commands_integration()
            self.create_config_integration()
            self.add_track_session_command()
            
            print()
            print("✅ Integration installation completed successfully!")
            print()
            print("🎯 Available Commands:")
            print("   context-cleaner optimize           # Full context optimization")
            print("   context-cleaner optimize --dashboard  # Context health dashboard")
            print("   context-cleaner optimize --quick      # Fast cleanup")
            print("   context-cleaner optimize --preview    # Preview changes")
            print("   context-cleaner run                 # Full orchestration + dashboard")
            print("   context-cleaner analyze            # Productivity analysis")
            print()
            print("📊 Productivity tracking is now active!")
            print("   Your development sessions will be automatically tracked")
            print("   Run 'context-cleaner run' to view insights")
            print()
            print("🔒 Privacy: All data stays on your machine, fully encrypted")
            
            return True
            
        except Exception as e:
            print(f"❌ Installation failed: {e}")
            return False

def main():
    """Main installer entry point."""
    installer = ClaudeIntegrationInstaller()
    
    if len(sys.argv) > 1 and sys.argv[1] in ['--help', '-h']:
        print("Context Cleaner - Claude Code Integration Installer")
        print()
        print("This script integrates Context Cleaner with Claude Code to provide:")
        print("• Automatic productivity tracking")  
        print("• Context optimization commands")
        print("• Development insights and analytics")
        print("• Privacy-first local data processing")
        print()
        print("Usage: python install_claude_integration.py")
        return
    
    success = installer.run_installation()
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
