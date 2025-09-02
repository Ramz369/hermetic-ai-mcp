#!/usr/bin/env python3
"""
Hermetic AI Platform - MCP Server
Main entry point for Claude Desktop integration
"""
import os
import sys
import json
import logging
import asyncio
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from mcp.server import Server
from mcp import Resource, Tool
from mcp.server.stdio import stdio_server
from mcp.types import (
    TextContent,
    ImageContent,
    EmbeddedResource,
    CallToolResult
)

from hermetic_ai_mcp.core.platform import HermeticAIPlatform
from hermetic_ai_mcp.core.memory_system import MemoryType, MemoryScope
from hermetic_ai_mcp.core.verification_engine import CodeVerifier

# Configure logging - CRITICAL: Don't log to stderr in production as it interferes with MCP protocol
# Only enable logging if DEBUG environment variable is set
if os.environ.get('DEBUG_MCP'):
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        filename='/tmp/hermetic_mcp_debug.log'
    )
    logger = logging.getLogger(__name__)
else:
    # Disable all logging when running as MCP server
    logging.disable(logging.CRITICAL)
    logger = logging.getLogger(__name__)


class HermeticMCPServer:
    """MCP Server for Hermetic AI Platform"""
    
    def __init__(self):
        """Initialize the MCP server"""
        self.server = Server("hermetic-ai")
        self.platform: Optional[HermeticAIPlatform] = None
        self.verifier: Optional[CodeVerifier] = None
        self.session_id: Optional[str] = None
        
        # Register handlers
        self._register_handlers()
    
    def _register_handlers(self):
        """Register all MCP handlers"""
        
        @self.server.list_resources()
        async def handle_list_resources() -> List[Resource]:
            """List available resources"""
            resources = [
                Resource(
                    uri="hermetic://platform/status",
                    name="Platform Status",
                    description="Current platform status and session info",
                    mimeType="application/json"
                ),
                Resource(
                    uri="hermetic://memory/universal",
                    name="Universal Memory",
                    description="Access universal memory patterns",
                    mimeType="application/json"
                ),
                Resource(
                    uri="hermetic://memory/project",
                    name="Project Memory",
                    description="Access project-specific memory",
                    mimeType="application/json"
                ),
                Resource(
                    uri="hermetic://verification/history",
                    name="Verification History",
                    description="Code verification history",
                    mimeType="application/json"
                )
            ]
            return resources
        
        @self.server.read_resource()
        async def handle_read_resource(uri: str) -> str:
            """Read a specific resource"""
            if not self.platform:
                return json.dumps({"error": "Platform not initialized"})
            
            if uri == "hermetic://platform/status":
                return json.dumps(self.platform.get_platform_status(), indent=2)
            
            elif uri == "hermetic://memory/universal":
                if self.platform.memory_system:
                    memories = self.platform.memory_system.search(
                        query="*",
                        scope=MemoryScope.UNIVERSAL,
                        limit=50
                    )
                    return json.dumps({
                        "count": len(memories),
                        "memories": [
                            {
                                "id": m.id,
                                "type": m.type.value,
                                "content": m.content[:200],
                                "created": m.created_at,
                                "confidence": m.confidence_score
                            }
                            for m in memories
                        ]
                    }, indent=2)
                return json.dumps({"error": "Memory system not initialized"})
            
            elif uri == "hermetic://memory/project":
                if self.platform.memory_system:
                    memories = self.platform.memory_system.search(
                        query="*",
                        scope=MemoryScope.PROJECT,
                        limit=50
                    )
                    return json.dumps({
                        "count": len(memories),
                        "project": self.platform.current_project.project_hash if self.platform.current_project else None,
                        "memories": [
                            {
                                "id": m.id,
                                "type": m.type.value,
                                "content": m.content[:200],
                                "created": m.created_at
                            }
                            for m in memories
                        ]
                    }, indent=2)
                return json.dumps({"error": "Memory system not initialized"})
            
            elif uri == "hermetic://verification/history":
                if self.platform.memory_system:
                    verifications = self.platform.memory_system.search(
                        query="Verification",
                        memory_type=MemoryType.VERIFICATION,
                        limit=20
                    )
                    return json.dumps({
                        "count": len(verifications),
                        "verifications": [
                            {
                                "id": v.id,
                                "content": v.content,
                                "metadata": v.metadata,
                                "created": v.created_at
                            }
                            for v in verifications
                        ]
                    }, indent=2)
                return json.dumps({"error": "Memory system not initialized"})
            
            return json.dumps({"error": f"Unknown resource: {uri}"})
        
        @self.server.list_tools()
        async def handle_list_tools() -> List[Tool]:
            """List available tools"""
            return [
                Tool(
                    name="sequential_thinking",
                    description="Process a thought step in sequential thinking",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "thought": {"type": "string", "description": "The current thought"},
                            "thoughtNumber": {"type": "integer", "description": "Current thought number"},
                            "totalThoughts": {"type": "integer", "description": "Total expected thoughts"},
                            "nextThoughtNeeded": {"type": "boolean", "description": "Whether another thought is needed"},
                            "isRevision": {"type": "boolean", "description": "Whether this revises previous thinking"},
                            "revisesThought": {"type": "integer", "description": "Which thought is being revised"},
                            "branchFromThought": {"type": "integer", "description": "Branching point"},
                            "branchId": {"type": "string", "description": "Branch identifier"}
                        },
                        "required": ["thought", "thoughtNumber", "totalThoughts", "nextThoughtNeeded"]
                    }
                ),
                Tool(
                    name="verify_code",
                    description="Verify code for quality, security, and completeness",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "code": {"type": "string", "description": "Code to verify"},
                            "file_path": {"type": "string", "description": "Optional file path"},
                            "language": {"type": "string", "description": "Programming language", "default": "python"}
                        },
                        "required": ["code"]
                    }
                ),
                Tool(
                    name="verify_with_skepticism",
                    description="Run multiple verification passes with skepticism",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "code": {"type": "string", "description": "Code to verify"},
                            "runs": {"type": "integer", "description": "Number of verification runs", "default": 3}
                        },
                        "required": ["code"]
                    }
                ),
                Tool(
                    name="search_memory",
                    description="Search platform memory",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "Search query"},
                            "scope": {"type": "string", "enum": ["universal", "project", "all"], "default": "all"},
                            "memory_type": {"type": "string", "enum": ["pattern", "error", "command", "architecture", "thought", "verification"]},
                            "limit": {"type": "integer", "default": 10}
                        },
                        "required": ["query"]
                    }
                ),
                Tool(
                    name="store_memory",
                    description="Store information in memory",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "content": {"type": "string", "description": "Content to store"},
                            "memory_type": {"type": "string", "enum": ["pattern", "error", "command", "architecture", "thought", "verification"]},
                            "scope": {"type": "string", "enum": ["universal", "project"], "default": "project"},
                            "metadata": {"type": "object", "description": "Additional metadata"}
                        },
                        "required": ["content", "memory_type"]
                    }
                ),
                Tool(
                    name="detect_project",
                    description="Detect and analyze current project",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "path": {"type": "string", "description": "Project path (defaults to current directory)"}
                        }
                    }
                ),
                Tool(
                    name="get_platform_status",
                    description="Get current platform status",
                    inputSchema={
                        "type": "object",
                        "properties": {}
                    }
                ),
                Tool(
                    name="generate_forensic_report",
                    description="Generate detailed forensic analysis of code",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "code": {"type": "string", "description": "Code to analyze"}
                        },
                        "required": ["code"]
                    }
                )
            ]
        
        @self.server.call_tool()
        async def handle_call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
            """Handle tool calls"""
            try:
                if not self.platform:
                    # Initialize platform on first tool call
                    self.platform = HermeticAIPlatform(auto_detect=True)
                    self.verifier = CodeVerifier(memory_system=self.platform.memory_system)
                    
                    # Auto-detect project if in a project directory
                    cwd = os.getcwd()
                    self.session_id = self.platform.on_session_start(cwd)
                    # Platform initialized with session
                
                # Route tool calls
                if name == "sequential_thinking":
                    result = self.platform.sequential_thinking.process_thought(arguments)
                    return [TextContent(type="text", text=json.dumps(result, indent=2))]
                
                elif name == "verify_code":
                    result = self.verifier.verify_code(
                        code=arguments["code"],
                        file_path=arguments.get("file_path"),
                        language=arguments.get("language", "python")
                    )
                    return [TextContent(type="text", text=json.dumps(result, indent=2))]
                
                elif name == "verify_with_skepticism":
                    result = self.verifier.verify_with_skepticism(
                        code=arguments["code"],
                        runs=arguments.get("runs", 3)
                    )
                    return [TextContent(type="text", text=json.dumps(result, indent=2))]
                
                elif name == "search_memory":
                    if not self.platform.memory_system:
                        return [TextContent(type="text", text=json.dumps({"error": "Memory system not initialized"}))]
                    
                    scope_map = {
                        "universal": MemoryScope.UNIVERSAL,
                        "project": MemoryScope.PROJECT,
                        "all": MemoryScope.ALL
                    }
                    
                    type_map = {
                        "pattern": MemoryType.PATTERN,
                        "error": MemoryType.ERROR,
                        "command": MemoryType.COMMAND,
                        "architecture": MemoryType.ARCHITECTURE,
                        "thought": MemoryType.THOUGHT,
                        "verification": MemoryType.VERIFICATION
                    }
                    
                    memories = self.platform.memory_system.search(
                        query=arguments["query"],
                        scope=scope_map.get(arguments.get("scope", "all"), MemoryScope.ALL),
                        memory_type=type_map.get(arguments.get("memory_type")),
                        limit=arguments.get("limit", 10)
                    )
                    
                    result = {
                        "count": len(memories),
                        "memories": [
                            {
                                "id": m.id,
                                "scope": m.scope.value,
                                "type": m.type.value,
                                "content": m.content,
                                "metadata": m.metadata,
                                "created": m.created_at,
                                "confidence": m.confidence_score
                            }
                            for m in memories
                        ]
                    }
                    return [TextContent(type="text", text=json.dumps(result, indent=2))]
                
                elif name == "store_memory":
                    if not self.platform.memory_system:
                        return [TextContent(type="text", text=json.dumps({"error": "Memory system not initialized"}))]
                    
                    type_map = {
                        "pattern": MemoryType.PATTERN,
                        "error": MemoryType.ERROR,
                        "command": MemoryType.COMMAND,
                        "architecture": MemoryType.ARCHITECTURE,
                        "thought": MemoryType.THOUGHT,
                        "verification": MemoryType.VERIFICATION
                    }
                    
                    scope_map = {
                        "universal": MemoryScope.UNIVERSAL,
                        "project": MemoryScope.PROJECT
                    }
                    
                    entry = self.platform.memory_system.store(
                        content=arguments["content"],
                        memory_type=type_map[arguments["memory_type"]],
                        scope=scope_map.get(arguments.get("scope", "project"), MemoryScope.PROJECT),
                        metadata=arguments.get("metadata", {})
                    )
                    
                    return [TextContent(type="text", text=json.dumps({
                        "success": True,
                        "entry_id": entry.id,
                        "stored_at": entry.created_at
                    }, indent=2))]
                
                elif name == "detect_project":
                    path = arguments.get("path", os.getcwd())
                    context = self.platform.project_detector.detect_project(path)
                    
                    return [TextContent(type="text", text=json.dumps({
                        "project_hash": context.project_hash,
                        "project_path": context.project_path,
                        "project_type": context.project_type,
                        "is_new": context.is_new,
                        "created_at": context.created_at.isoformat(),
                        "last_accessed": context.last_accessed.isoformat()
                    }, indent=2))]
                
                elif name == "get_platform_status":
                    status = self.platform.get_platform_status()
                    return [TextContent(type="text", text=json.dumps(status, indent=2))]
                
                elif name == "generate_forensic_report":
                    result = self.verifier.generate_forensic_report(arguments["code"])
                    return [TextContent(type="text", text=json.dumps(result, indent=2))]
                
                else:
                    return [TextContent(type="text", text=json.dumps({"error": f"Unknown tool: {name}"}))]
                    
            except Exception as e:
                # Tool execution error - return error response
                return [TextContent(type="text", text=json.dumps({
                    "error": str(e),
                    "tool": name
                }))]
    
    async def run(self):
        """Run the MCP server"""
        # Starting Hermetic AI MCP Server
        
        # Initialize platform
        self.platform = HermeticAIPlatform(auto_detect=True)
        self.verifier = CodeVerifier()
        
        # Run the server
        options = self.server.create_initialization_options()
        async with stdio_server() as (read_stream, write_stream):
            await self.server.run(
                read_stream,
                write_stream,
                options,
                raise_exceptions=True
            )


async def async_main():
    """Async main entry point"""
    server = HermeticMCPServer()
    await server.run()


def configure_claude():
    """Configure Claude to use this MCP server"""
    import json
    from pathlib import Path
    
    config_paths = [
        Path.home() / ".config" / "claude" / "config.json",
        Path.home() / ".config" / "claude" / "claude_desktop_config.json",
    ]
    
    configured = False
    for config_path in config_paths:
        if config_path.exists():
            with open(config_path) as f:
                config = json.load(f)
            
            if "mcpServers" not in config:
                config["mcpServers"] = {}
            
            config["mcpServers"]["hermetic-ai"] = {
                "command": "hermetic-mcp",
                "args": [],
                "env": {
                    "PYTHONUNBUFFERED": "1"
                }
            }
            
            with open(config_path, 'w') as f:
                json.dump(config, f, indent=2)
            
            print(f"✓ Configured {config_path}")
            configured = True
    
    if configured:
        print("\n✅ Hermetic AI MCP configured successfully!")
        print("Restart Claude to use the new configuration.")
    else:
        print("❌ No Claude configuration files found.")
        print("Please install Claude Code CLI or Claude Desktop first.")
    
    return configured

def main():
    """Synchronous main entry point for console script"""
    # Check for configuration flag
    if len(sys.argv) > 1 and sys.argv[1] == "--configure":
        sys.exit(0 if configure_claude() else 1)
    
    if len(sys.argv) > 1 and sys.argv[1] == "--version":
        print("Hermetic AI MCP Server v1.0.0")
        sys.exit(0)
    
    try:
        asyncio.run(async_main())
    except KeyboardInterrupt:
        # Server shutdown requested
        pass
    except Exception as e:
        # Server error occurred
        sys.exit(1)


if __name__ == "__main__":
    main()