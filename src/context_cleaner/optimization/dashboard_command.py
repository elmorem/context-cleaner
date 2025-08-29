#!/usr/bin/env python3
"""
Dashboard Command Integration
Provides dashboard functionality for the /clean-context --dashboard command
"""

import sys
import argparse
from pathlib import Path

# Add visualization module to path
current_file = Path(__file__).resolve()
visualization_dir = current_file.parent.parent / 'visualization'
sys.path.insert(0, str(visualization_dir))

from basic_dashboard import BasicDashboard


def parse_arguments():
    """Parse command line arguments for dashboard."""
    parser = argparse.ArgumentParser(description='Context Health Dashboard')
    
    parser.add_argument('--format', 
                       choices=['text', 'json'], 
                       default='text',
                       help='Output format (default: text)')
    
    parser.add_argument('--data-dir',
                       type=str,
                       help='Custom data directory path')
    
    parser.add_argument('--cache',
                       action='store_true',
                       help='Force use of cached results if available')
    
    return parser.parse_args()


def get_dashboard_data_dir(custom_path: str = None) -> Path:
    """Get the dashboard data directory."""
    if custom_path:
        return Path(custom_path)
    
    # Default path relative to this script
    current_file = Path(__file__).resolve()
    project_root = current_file.parent.parent.parent
    return project_root / '.context_visualizer' / 'data' / 'sessions'


def main():
    """Main dashboard command interface."""
    try:
        args = parse_arguments()
        
        # Get data directory
        data_dir = get_dashboard_data_dir(args.data_dir)
        
        # Create dashboard instance
        dashboard = BasicDashboard(data_dir)
        
        # Generate output based on format
        if args.format == 'json':
            import json
            data = dashboard.get_json_output()
            print(json.dumps(data, indent=2))
        else:
            # Text format (default)
            output = dashboard.get_formatted_output()
            print(output)
        
        return 0
        
    except KeyboardInterrupt:
        print("\n❌ Dashboard generation interrupted by user", file=sys.stderr)
        return 1
        
    except Exception as e:
        print(f"❌ Dashboard generation failed: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)