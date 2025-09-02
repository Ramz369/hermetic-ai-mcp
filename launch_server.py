#!/usr/bin/env python3
"""
Launch script for Hermetic AI MCP Server
This script ensures clean stdio communication for MCP protocol
"""
import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# CRITICAL: Suppress all output to stderr to avoid MCP protocol interference
import warnings
warnings.filterwarnings("ignore")

# Disable any print statements from imported modules
import builtins
_original_print = builtins.print
def silent_print(*args, **kwargs):
    # Only allow printing to stdout, never to stderr
    if kwargs.get('file') != sys.stderr:
        _original_print(*args, **kwargs)
builtins.print = silent_print

from hermetic_ai_mcp.server import HermeticMCPServer
import asyncio

def main():
    """Main entry point for the MCP server"""
    # Ensure no debug output
    os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
    
    # Create and run server
    server = HermeticMCPServer()
    
    try:
        # Run the async server
        asyncio.run(server.run())
    except KeyboardInterrupt:
        # Silent shutdown
        pass
    except Exception:
        # Silent error handling - MCP protocol requires clean stdio
        sys.exit(1)

if __name__ == "__main__":
    main()