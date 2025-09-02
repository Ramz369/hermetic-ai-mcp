# 📡 Hermetic AI Platform - API Specifications

## Table of Contents

1. [Overview](#overview)
2. [MCP Tool APIs](#mcp-tool-apis)
3. [REST API Endpoints](#rest-api-endpoints)
4. [WebSocket API](#websocket-api)
5. [Authentication](#authentication)
6. [Error Handling](#error-handling)
7. [Rate Limiting](#rate-limiting)
8. [Data Models](#data-models)

## Overview

The Hermetic AI Platform exposes three types of APIs:

1. **MCP Tool APIs**: For Claude Desktop integration via Model Context Protocol
2. **REST APIs**: For dashboard and external integrations
3. **WebSocket APIs**: For real-time updates and monitoring

### Base URLs

```
MCP Server:  stdio/sse (local)
REST API:    http://localhost:8080/api/v1
WebSocket:   ws://localhost:8080/ws
Dashboard:   http://localhost:8080
```

## MCP Tool APIs

### Tool Registration Format

All tools follow the MCP standard registration format:

```python
@server.tool()
async def tool_name(
    param1: str,
    param2: Optional[int] = None
) -> Dict[str, Any]:
    """Tool description for Claude"""
    return result
```

### Core Platform Tools

#### 1. Sequential Thinking

**Tool Name**: `sequential_thinking`

**Parameters**:
```typescript
{
  thought: string          // Current thinking step
  thoughtNumber: number    // Current thought number (1-based)
  totalThoughts: number    // Estimated total thoughts
  nextThoughtNeeded: boolean // Whether more thinking needed
  isRevision?: boolean     // If revising previous thought
  revisesThought?: number  // Which thought being revised
  branchFromThought?: number // Branching point
  branchId?: string       // Branch identifier
}
```

**Response**:
```typescript
{
  success: boolean
  thoughtNumber: number
  totalThoughts: number
  nextThoughtNeeded: boolean
  thoughtType: string
  branches: string[]
  thoughtHistoryLength: number
}
```

#### 2. Code Verification

**Tool Name**: `verify_code`

**Parameters**:
```typescript
{
  code: string              // Code to verify
  file_path?: string        // Optional file context
  language?: string         // Programming language
  strict_mode?: boolean     // Use strict verification
}
```

**Response**:
```typescript
{
  passed: boolean
  has_mocks: boolean
  violations: string[]
  security_issues: string[]
  pattern_violations: Array<{
    line: number
    pattern: string
    content: string
    message: string
  }>
  confidence: number
  code_hash: string
}
```

#### 3. Symbol Search

**Tool Name**: `find_symbol`

**Parameters**:
```typescript
{
  symbol_name: string       // Symbol to find
  language?: string         // Optional language filter
  project_path?: string     // Optional project scope
}
```

**Response**:
```typescript
{
  success: boolean
  symbols: Array<{
    name: string
    kind: string           // function, class, variable, etc.
    location: string       // file path
    line: number
    column: number
    container?: string     // parent symbol
    documentation?: string
  }>
}
```

#### 4. Memory Operations

**Tool Name**: `store_memory`

**Parameters**:
```typescript
{
  content: string
  memory_type: "pattern" | "error" | "solution" | "command" | "architecture"
  scope: "universal" | "project" | "session"
  metadata?: object
}
```

**Response**:
```typescript
{
  success: boolean
  memory_id: string
  scope: string
  timestamp: string
}
```

**Tool Name**: `search_memory`

**Parameters**:
```typescript
{
  query: string
  scope?: "universal" | "project" | "all"
  memory_type?: string
  limit?: number
}
```

**Response**:
```typescript
{
  success: boolean
  results: Array<{
    id: string
    content: string
    type: string
    scope: string
    metadata: object
    confidence_score: number
  }>
  total_found: number
}
```

## REST API Endpoints

### Authentication Endpoints

#### POST /api/v1/auth/login
**Request**:
```json
{
  "username": "string",
  "password": "string"
}
```

**Response**:
```json
{
  "access_token": "string",
  "refresh_token": "string",
  "token_type": "bearer",
  "expires_in": 3600
}
```

### Module Management

#### GET /api/v1/modules
Get list of available modules

**Query Parameters**:
- `type`: Filter by module type (builtin, external, community)
- `enabled`: Filter by enabled status
- `page`: Page number (default: 1)
- `limit`: Items per page (default: 20)

**Response**:
```json
{
  "modules": [
    {
      "name": "sequential_thinking",
      "version": "1.0.0",
      "description": "Sequential thinking and problem-solving",
      "author": "Hermetic AI",
      "enabled": true,
      "module_type": "builtin",
      "dependencies": [],
      "settings": {}
    }
  ],
  "total": 10,
  "page": 1,
  "pages": 1
}
```

#### POST /api/v1/modules/install
Install a new module

**Request**:
```json
{
  "name": "string",
  "source": "marketplace" | "file" | "url",
  "location": "string"
}
```

**Response**:
```json
{
  "success": true,
  "module": {
    "name": "string",
    "version": "string",
    "installed_at": "2024-01-01T00:00:00Z"
  }
}
```

#### DELETE /api/v1/modules/{module_name}
Uninstall a module

**Response**:
```json
{
  "success": true,
  "message": "Module uninstalled successfully"
}
```

#### PUT /api/v1/modules/{module_name}/config
Update module configuration

**Request**:
```json
{
  "enabled": true,
  "settings": {
    "key": "value"
  }
}
```

### Project Management

#### GET /api/v1/projects
List detected projects

**Response**:
```json
{
  "projects": [
    {
      "hash": "a1b2c3d4",
      "path": "/home/user/project",
      "type": "python",
      "created_at": "2024-01-01T00:00:00Z",
      "last_accessed": "2024-01-02T00:00:00Z",
      "memory_size": 1048576
    }
  ],
  "total": 5
}
```

#### POST /api/v1/projects/activate
Activate a project

**Request**:
```json
{
  "project_hash": "string",
  "project_path": "string"
}
```

**Response**:
```json
{
  "success": true,
  "project": {
    "hash": "string",
    "path": "string",
    "type": "string",
    "is_new": false
  }
}
```

### Memory API

#### GET /api/v1/memory/search
Search memory

**Query Parameters**:
- `query`: Search query (required)
- `scope`: universal, project, or all
- `type`: Memory type filter
- `limit`: Maximum results

**Response**:
```json
{
  "results": [
    {
      "id": "string",
      "content": "string",
      "type": "pattern",
      "scope": "universal",
      "metadata": {},
      "confidence_score": 0.95,
      "created_at": "2024-01-01T00:00:00Z"
    }
  ],
  "total_found": 42,
  "search_time_ms": 15
}
```

#### POST /api/v1/memory/store
Store new memory

**Request**:
```json
{
  "content": "string",
  "type": "pattern",
  "scope": "project",
  "metadata": {
    "file_path": "/src/main.py",
    "language": "python"
  }
}
```

#### POST /api/v1/memory/promote
Promote project memory to universal

**Request**:
```json
{
  "memory_id": "string",
  "pattern_type": "string"
}
```

### Tool Execution

#### POST /api/v1/tools/execute
Execute a tool

**Request**:
```json
{
  "tool_name": "verify_code",
  "parameters": {
    "code": "def hello(): pass",
    "language": "python"
  }
}
```

**Response**:
```json
{
  "success": true,
  "result": {},
  "execution_time_ms": 45,
  "tool_version": "1.0.0"
}
```

#### GET /api/v1/tools
List available tools

**Response**:
```json
{
  "tools": [
    {
      "name": "verify_code",
      "module": "verification",
      "description": "Verify code quality",
      "parameters": {
        "code": "string",
        "language": "string"
      }
    }
  ],
  "total": 15
}
```

### Monitoring & Metrics

#### GET /api/v1/metrics
Get platform metrics

**Response**:
```json
{
  "platform": {
    "uptime_seconds": 3600,
    "memory_usage_mb": 256,
    "cpu_usage_percent": 15
  },
  "modules": {
    "loaded": 5,
    "total": 10
  },
  "tools": {
    "executions_total": 1500,
    "executions_per_minute": 25,
    "average_latency_ms": 35
  },
  "memory_system": {
    "universal_entries": 5000,
    "project_entries": 2000,
    "cache_hit_rate": 0.85
  }
}
```

## WebSocket API

### Connection

```javascript
const ws = new WebSocket('ws://localhost:8080/ws');
ws.send(JSON.stringify({
  type: 'auth',
  token: 'bearer_token'
}));
```

### Event Types

#### Tool Execution Events

**Event**: `tool.execution.start`
```json
{
  "type": "tool.execution.start",
  "data": {
    "tool_name": "verify_code",
    "request_id": "uuid",
    "timestamp": "2024-01-01T00:00:00Z"
  }
}
```

**Event**: `tool.execution.complete`
```json
{
  "type": "tool.execution.complete",
  "data": {
    "tool_name": "verify_code",
    "request_id": "uuid",
    "success": true,
    "duration_ms": 45
  }
}
```

#### Module Events

**Event**: `module.status.change`
```json
{
  "type": "module.status.change",
  "data": {
    "module_name": "sequential_thinking",
    "old_status": "inactive",
    "new_status": "active"
  }
}
```

#### Memory Events

**Event**: `memory.update`
```json
{
  "type": "memory.update",
  "data": {
    "action": "store",
    "memory_id": "string",
    "scope": "project"
  }
}
```

#### Metrics Events

**Event**: `metrics.update`
```json
{
  "type": "metrics.update",
  "data": {
    "cpu_percent": 15,
    "memory_mb": 256,
    "active_tools": 3
  }
}
```

### Subscriptions

```json
{
  "type": "subscribe",
  "channels": ["tools", "metrics", "memory"]
}
```

## Authentication

### API Key Authentication

```http
Authorization: Bearer YOUR_API_KEY
```

### JWT Authentication

```http
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

### Session Authentication

```http
Cookie: session=abc123def456...
```

## Error Handling

### Error Response Format

```json
{
  "error": {
    "code": "MODULE_NOT_FOUND",
    "message": "Module 'unknown' not found",
    "details": {
      "requested_module": "unknown",
      "available_modules": ["sequential_thinking", "verification"]
    }
  },
  "request_id": "uuid",
  "timestamp": "2024-01-01T00:00:00Z"
}
```

### HTTP Status Codes

| Status | Meaning |
|--------|---------|
| 200 | Success |
| 201 | Created |
| 204 | No Content |
| 400 | Bad Request |
| 401 | Unauthorized |
| 403 | Forbidden |
| 404 | Not Found |
| 409 | Conflict |
| 422 | Unprocessable Entity |
| 429 | Too Many Requests |
| 500 | Internal Server Error |
| 503 | Service Unavailable |

### Error Codes

| Code | Description |
|------|-------------|
| `INVALID_PARAMETERS` | Request parameters are invalid |
| `MODULE_NOT_FOUND` | Requested module doesn't exist |
| `TOOL_NOT_FOUND` | Requested tool doesn't exist |
| `PROJECT_NOT_FOUND` | Project not in registry |
| `MEMORY_ERROR` | Memory operation failed |
| `EXECUTION_TIMEOUT` | Tool execution timed out |
| `RATE_LIMIT_EXCEEDED` | Too many requests |
| `AUTHENTICATION_FAILED` | Invalid credentials |
| `PERMISSION_DENIED` | Insufficient permissions |

## Rate Limiting

### Default Limits

| Endpoint | Limit |
|----------|-------|
| Tool Execution | 100/minute |
| Memory Search | 200/minute |
| Memory Store | 50/minute |
| Module Install | 10/hour |
| Metrics | 600/minute |

### Rate Limit Headers

```http
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1640995200
```

## Data Models

### Module

```typescript
interface Module {
  name: string
  version: string
  author?: string
  description?: string
  enabled: boolean
  dependencies: string[]
  settings: Record<string, any>
  entry_point: string
  module_type: "builtin" | "external" | "community"
}
```

### Project

```typescript
interface Project {
  project_hash: string
  project_path: string
  project_type: string
  created_at: string
  last_accessed: string
  config: Record<string, any>
  memory_path: string
  is_new: boolean
}
```

### Memory Entry

```typescript
interface MemoryEntry {
  id: string
  scope: "universal" | "project" | "session"
  type: "pattern" | "error" | "solution" | "command" | "architecture"
  content: string
  metadata: Record<string, any>
  embedding?: number[]
  created_at: number
  accessed_count: number
  confidence_score: number
  project_hash?: string
}
```

### Tool Definition

```typescript
interface Tool {
  name: string
  module: string
  description: string
  parameters: Record<string, ParameterDef>
  returns: ReturnDef
}

interface ParameterDef {
  type: string
  required: boolean
  description: string
  default?: any
}

interface ReturnDef {
  type: string
  description: string
}
```

## SDK Examples

### Python Client

```python
import requests

class HermeticClient:
    def __init__(self, base_url="http://localhost:8080/api/v1"):
        self.base_url = base_url
        self.session = requests.Session()
    
    def execute_tool(self, tool_name: str, parameters: dict):
        response = self.session.post(
            f"{self.base_url}/tools/execute",
            json={
                "tool_name": tool_name,
                "parameters": parameters
            }
        )
        return response.json()
    
    def search_memory(self, query: str, scope: str = "all"):
        response = self.session.get(
            f"{self.base_url}/memory/search",
            params={"query": query, "scope": scope}
        )
        return response.json()
```

### JavaScript Client

```javascript
class HermeticClient {
  constructor(baseUrl = 'http://localhost:8080/api/v1') {
    this.baseUrl = baseUrl;
  }
  
  async executeTool(toolName, parameters) {
    const response = await fetch(`${this.baseUrl}/tools/execute`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        tool_name: toolName,
        parameters: parameters
      })
    });
    return response.json();
  }
  
  async searchMemory(query, scope = 'all') {
    const params = new URLSearchParams({ query, scope });
    const response = await fetch(
      `${this.baseUrl}/memory/search?${params}`
    );
    return response.json();
  }
}
```

### WebSocket Client

```javascript
class HermeticWebSocket {
  constructor(url = 'ws://localhost:8080/ws') {
    this.ws = new WebSocket(url);
    this.handlers = {};
    
    this.ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      const handler = this.handlers[data.type];
      if (handler) handler(data.data);
    };
  }
  
  on(eventType, handler) {
    this.handlers[eventType] = handler;
  }
  
  subscribe(channels) {
    this.ws.send(JSON.stringify({
      type: 'subscribe',
      channels: channels
    }));
  }
}

// Usage
const ws = new HermeticWebSocket();
ws.on('tool.execution.complete', (data) => {
  console.log('Tool completed:', data);
});
ws.subscribe(['tools', 'metrics']);
```

## API Versioning

The API uses URL versioning:
- Current version: `/api/v1`
- Beta features: `/api/v2-beta`
- Deprecated: `/api/v0` (sunset date: 2024-12-31)

### Version Migration

When upgrading API versions:
1. New versions maintain backward compatibility for 6 months
2. Deprecation notices sent via `X-API-Deprecated` header
3. Migration guides provided in documentation

## Testing

### Test Endpoints

```
GET /api/v1/health       # Health check
GET /api/v1/ping        # Simple ping
POST /api/v1/echo       # Echo request body
```

### Sandbox Environment

```
Base URL: http://sandbox.hermetic.ai/api/v1
Rate Limits: 10x higher than production
Data Persistence: 24 hours
```

---
*API Version: 1.0.0*
*Last Updated: 2024*
*OpenAPI Spec: /api/v1/openapi.json*