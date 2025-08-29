"""
Static assets for Context Cleaner
Contains JavaScript files for advanced visualizations and dashboard components.
"""

import os
from pathlib import Path

# Path to static assets directory
STATIC_DIR = Path(__file__).parent

# Path to JavaScript files
JS_DIR = STATIC_DIR / "js"

def get_static_path(filename: str) -> Path:
    """Get path to a static asset file."""
    return STATIC_DIR / filename

def get_js_path(filename: str) -> Path:
    """Get path to a JavaScript file."""
    return JS_DIR / filename

def list_js_files() -> list:
    """List all available JavaScript files."""
    if JS_DIR.exists():
        return [f.name for f in JS_DIR.glob("*.js")]
    return []

# Available JavaScript modules
AVAILABLE_JS_MODULES = [
    "interactive_heatmaps.js",
    "productivity_charts.js", 
    "trend_visualizations.js"
]