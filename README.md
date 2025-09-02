# Hermetic AI MCP Server

Hermetic AI Platform - MCP Server for Claude Code CLI and Claude Desktop.

## Features

- **Code Verification**: Verify code quality without mocking
- **Skeptical Analysis**: Multiple verification passes with skepticism
- **Forensic Reports**: Generate detailed code analysis
- **Memory System**: Store and search platform memory
- **Project Detection**: Automatic project context detection
- **Sequential Thinking**: Step-by-step problem solving

## Installation

### One-Command Installation

```bash
# Using pip (system Python)
pip install --user git+https://github.com/ramz/hermetic-ai-mcp.git --break-system-packages

# Or using pipx (recommended)
pipx install git+https://github.com/ramz/hermetic-ai-mcp.git

# Or using uv (if you have it)
uv pip install git+https://github.com/ramz/hermetic-ai-mcp.git
```

The installation automatically:
1. Installs the `hermetic-mcp` command
2. Adds it to your PATH
3. Makes it available for Claude configuration

## Configuration

After installation, configure Claude to use the MCP server:

### Automatic Configuration

```bash
hermetic-mcp --configure
```

This will automatically detect and update your Claude configuration file.

### Manual Configuration

#### For Claude Code CLI

Edit `~/.config/claude/config.json`:

```json
{
  "mcpServers": {
    "hermetic-ai": {
      "command": "hermetic-mcp",
      "args": [],
      "env": {
        "PYTHONUNBUFFERED": "1"
      }
    }
  }
}
```

#### For Claude Desktop

Edit `~/.config/claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "hermetic-ai": {
      "command": "hermetic-mcp",
      "args": [],
      "env": {
        "PYTHONUNBUFFERED": "1"
      }
    }
  }
}
```

## Verification

Test the installation:

```bash
# Test MCP protocol
echo '{"jsonrpc":"2.0","method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}},"id":1}' | hermetic-mcp

# Should return a JSON response with "hermetic-ai" server info
```

## Available Tools

Once configured, the following tools are available in Claude:

### Core Tools
- `verify_code`: Verify code for quality, security, and completeness
- `verify_with_skepticism`: Run multiple verification passes with skepticism
- `generate_forensic_report`: Generate detailed forensic analysis of code
- `sequential_thinking`: Process step-by-step thinking for complex problems

### Memory Tools
- `search_memory`: Search platform memory
- `store_memory`: Store information in memory
- `store_universal_learning`: Store universal patterns
- `store_project_memory`: Store project-specific information
- `search_all_memories`: Search across all memory layers
- `learn_from_error`: Learn from errors and store solutions

### Project Tools
- `detect_project`: Detect and analyze current project
- `set_current_project`: Set the current project context
- `get_platform_status`: Get current platform status
- `get_project_architecture`: Get project architecture graph
- `get_relevant_context`: Get relevant context for a query

### Documentation Tools
- `check_documentation`: Check if documentation exists
- `create_documentation`: Create project documentation

## Usage Examples

In Claude, you can use the tools like this:

```
Claude: Let me verify this code using the hermetic-ai tools.

[Uses verify_code tool]

The code verification shows...
```

## Development

To contribute or modify:

```bash
git clone https://github.com/ramz/hermetic-ai-mcp.git
cd hermetic-ai-mcp
pip install -e . --user --break-system-packages
```

## Uninstallation

```bash
# Remove the package
pip uninstall hermetic-ai-mcp

# Remove from Claude config manually
```

## Troubleshooting

### Command not found
If `hermetic-mcp` is not found after installation:
```bash
export PATH="$HOME/.local/bin:$PATH"
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
```

### MCP not showing in Claude
1. Restart Claude Code CLI after configuration
2. Check the config file location matches your Claude installation
3. Verify the command works: `hermetic-mcp --version`

## License

Proprietary - All rights reserved