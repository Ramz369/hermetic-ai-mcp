#!/usr/bin/env python3
"""
Hermetic AI Platform - Universal API Server
REST API for any LLM or platform to interact with Hermetic AI
Compatible with OpenAI API format for easy integration
"""
import os
import sys
import json
import logging
import asyncio
from pathlib import Path
from typing import Dict, Any, List, Optional, Union
from datetime import datetime
from contextlib import asynccontextmanager

# FastAPI imports
from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field
import uvicorn

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from hermetic_ai_mcp.core.platform import HermeticAIPlatform
from hermetic_ai_mcp.core.memory_system import MemoryType, MemoryScope
from hermetic_ai_mcp.core.verification_engine import CodeVerifier

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ==================== Pydantic Models ====================

class ThoughtRequest(BaseModel):
    """Sequential thinking request"""
    thought: str
    thought_number: int = Field(alias="thoughtNumber", default=1)
    total_thoughts: int = Field(alias="totalThoughts", default=1)
    next_thought_needed: bool = Field(alias="nextThoughtNeeded", default=False)
    is_revision: Optional[bool] = Field(alias="isRevision", default=False)
    revises_thought: Optional[int] = Field(alias="revisesThought", default=None)
    branch_from_thought: Optional[int] = Field(alias="branchFromThought", default=None)
    branch_id: Optional[str] = Field(alias="branchId", default=None)
    
    class Config:
        populate_by_name = True


class CodeVerificationRequest(BaseModel):
    """Code verification request"""
    code: str
    file_path: Optional[str] = None
    language: str = "python"
    strict_mode: bool = True


class MemorySearchRequest(BaseModel):
    """Memory search request"""
    query: str
    scope: str = "all"  # universal, project, all
    memory_type: Optional[str] = None
    limit: int = 10


class MemoryStoreRequest(BaseModel):
    """Memory storage request"""
    content: str
    memory_type: str  # pattern, error, command, architecture, thought, verification
    scope: str = "project"  # universal, project
    metadata: Optional[Dict[str, Any]] = {}


class ProjectDetectRequest(BaseModel):
    """Project detection request"""
    path: Optional[str] = None


# OpenAI-compatible models for universal LLM support
class Message(BaseModel):
    role: str  # system, user, assistant, function
    content: str
    name: Optional[str] = None
    function_call: Optional[Dict[str, Any]] = None


class ChatCompletionRequest(BaseModel):
    """OpenAI-compatible chat completion request"""
    model: str = "hermetic-ai"
    messages: List[Message]
    functions: Optional[List[Dict[str, Any]]] = None
    function_call: Optional[Union[str, Dict[str, str]]] = None
    temperature: float = 0.7
    max_tokens: Optional[int] = None
    stream: bool = False


class FunctionCall(BaseModel):
    """Function call in OpenAI format"""
    name: str
    arguments: str  # JSON string


class Choice(BaseModel):
    """Response choice"""
    index: int
    message: Message
    finish_reason: str


class ChatCompletionResponse(BaseModel):
    """OpenAI-compatible response"""
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: List[Choice]
    usage: Optional[Dict[str, int]] = None


# ==================== Application ====================

class HermeticAPIServer:
    """Universal API Server for Hermetic AI Platform"""
    
    def __init__(self):
        self.platform: Optional[HermeticAIPlatform] = None
        self.verifier: Optional[CodeVerifier] = None
        self.sessions: Dict[str, Any] = {}
        self.websocket_connections: List[WebSocket] = []
    
    async def startup(self):
        """Initialize platform on startup"""
        logger.info("Initializing Hermetic AI Platform...")
        self.platform = HermeticAIPlatform(auto_detect=True)
        self.verifier = CodeVerifier()
        
        # Auto-detect current project
        cwd = os.getcwd()
        session_id = self.platform.on_session_start(cwd)
        logger.info(f"Platform initialized with session: {session_id}")
    
    async def shutdown(self):
        """Cleanup on shutdown"""
        logger.info("Shutting down Hermetic AI Platform...")
        if self.platform:
            await self.platform.shutdown()
        
        # Close all websocket connections
        for ws in self.websocket_connections:
            await ws.close()


# Create server instance
server = HermeticAPIServer()

# Lifecycle management
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await server.startup()
    yield
    # Shutdown
    await server.shutdown()

# Create FastAPI app
app = FastAPI(
    title="Hermetic AI Platform API",
    description="Universal API for LLM integration with Hermetic AI Platform",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware for browser access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==================== API Endpoints ====================

@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "name": "Hermetic AI Platform",
        "version": "1.0.0",
        "description": "Universal AI platform with memory, verification, and thinking capabilities",
        "endpoints": {
            "openai_compatible": "/v1/chat/completions",
            "native": {
                "thinking": "/api/thinking",
                "verification": "/api/verify",
                "memory": "/api/memory",
                "platform": "/api/platform"
            }
        }
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "platform_initialized": server.platform is not None,
        "timestamp": datetime.now().isoformat()
    }


# ==================== Native API Endpoints ====================

@app.post("/api/thinking")
async def process_thought(request: ThoughtRequest):
    """Process a sequential thinking step"""
    if not server.platform:
        raise HTTPException(status_code=503, detail="Platform not initialized")
    
    result = server.platform.sequential_thinking.process_thought({
        "thought": request.thought,
        "thoughtNumber": request.thought_number,
        "totalThoughts": request.total_thoughts,
        "nextThoughtNeeded": request.next_thought_needed,
        "isRevision": request.is_revision,
        "revisesThought": request.revises_thought,
        "branchFromThought": request.branch_from_thought,
        "branchId": request.branch_id
    })
    
    return JSONResponse(content=result)


@app.post("/api/verify")
async def verify_code(request: CodeVerificationRequest):
    """Verify code for quality and security"""
    if not server.verifier:
        raise HTTPException(status_code=503, detail="Verifier not initialized")
    
    result = server.verifier.verify_code(
        code=request.code,
        file_path=request.file_path,
        language=request.language
    )
    
    return JSONResponse(content=result)


@app.post("/api/verify/skeptical")
async def verify_with_skepticism(request: CodeVerificationRequest):
    """Run multiple verification passes with skepticism"""
    if not server.verifier:
        raise HTTPException(status_code=503, detail="Verifier not initialized")
    
    result = server.verifier.verify_with_skepticism(
        code=request.code,
        runs=3
    )
    
    return JSONResponse(content=result)


@app.post("/api/memory/search")
async def search_memory(request: MemorySearchRequest):
    """Search platform memory"""
    if not server.platform or not server.platform.memory_system:
        raise HTTPException(status_code=503, detail="Memory system not initialized")
    
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
    
    memories = server.platform.memory_system.search(
        query=request.query,
        scope=scope_map.get(request.scope, MemoryScope.ALL),
        memory_type=type_map.get(request.memory_type) if request.memory_type else None,
        limit=request.limit
    )
    
    return {
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


@app.post("/api/memory/store")
async def store_memory(request: MemoryStoreRequest):
    """Store information in memory"""
    if not server.platform or not server.platform.memory_system:
        raise HTTPException(status_code=503, detail="Memory system not initialized")
    
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
    
    entry = server.platform.memory_system.store(
        content=request.content,
        memory_type=type_map[request.memory_type],
        scope=scope_map.get(request.scope, MemoryScope.PROJECT),
        metadata=request.metadata
    )
    
    return {
        "success": True,
        "entry_id": entry.id,
        "stored_at": entry.created_at
    }


@app.post("/api/platform/detect-project")
async def detect_project(request: ProjectDetectRequest):
    """Detect and analyze project"""
    if not server.platform:
        raise HTTPException(status_code=503, detail="Platform not initialized")
    
    path = request.path or os.getcwd()
    context = server.platform.project_detector.detect_project(path)
    
    return {
        "project_hash": context.project_hash,
        "project_path": context.project_path,
        "project_type": context.project_type,
        "is_new": context.is_new,
        "created_at": context.created_at.isoformat(),
        "last_accessed": context.last_accessed.isoformat()
    }


@app.get("/api/platform/status")
async def get_platform_status():
    """Get platform status"""
    if not server.platform:
        raise HTTPException(status_code=503, detail="Platform not initialized")
    
    return server.platform.get_platform_status()


# ==================== OpenAI-Compatible Endpoints ====================

@app.post("/v1/chat/completions")
async def chat_completions(request: ChatCompletionRequest):
    """OpenAI-compatible chat completions endpoint"""
    if not server.platform:
        raise HTTPException(status_code=503, detail="Platform not initialized")
    
    # Process function calls if present
    last_message = request.messages[-1] if request.messages else None
    
    if last_message and last_message.role == "user":
        # Check if the message contains a function call request
        content = last_message.content.lower()
        
        response_content = ""
        function_name = None
        function_args = {}
        
        # Simple pattern matching for function detection
        if "verify" in content and "code" in content:
            # Extract code block if present
            if "```" in last_message.content:
                code = last_message.content.split("```")[1].split("```")[0]
                result = server.verifier.verify_code(code)
                response_content = json.dumps(result, indent=2)
                function_name = "verify_code"
                function_args = {"code": code}
                
        elif "think" in content or "thought" in content:
            # Process as thinking request
            result = server.platform.sequential_thinking.process_thought({
                "thought": last_message.content,
                "thoughtNumber": 1,
                "totalThoughts": 1,
                "nextThoughtNeeded": False
            })
            response_content = json.dumps(result, indent=2)
            function_name = "sequential_thinking"
            function_args = {"thought": last_message.content}
            
        elif "search" in content and "memory" in content:
            # Search memory
            query = last_message.content.replace("search", "").replace("memory", "").strip()
            memories = server.platform.memory_system.search(query, limit=5)
            response_content = f"Found {len(memories)} memories:\n"
            for m in memories:
                response_content += f"- {m.type.value}: {m.content[:100]}...\n"
            function_name = "search_memory"
            function_args = {"query": query}
            
        else:
            # General response
            response_content = "Hermetic AI Platform is ready. Available functions: verify_code, sequential_thinking, search_memory, store_memory, detect_project"
        
        # Build OpenAI-compatible response
        message = Message(
            role="assistant",
            content=response_content
        )
        
        if function_name:
            message.function_call = {
                "name": function_name,
                "arguments": json.dumps(function_args)
            }
        
        response = ChatCompletionResponse(
            id=f"chatcmpl-{datetime.now().timestamp()}",
            created=int(datetime.now().timestamp()),
            model=request.model,
            choices=[
                Choice(
                    index=0,
                    message=message,
                    finish_reason="function_call" if function_name else "stop"
                )
            ],
            usage={
                "prompt_tokens": len(str(request.messages)),
                "completion_tokens": len(response_content),
                "total_tokens": len(str(request.messages)) + len(response_content)
            }
        )
        
        return response
    
    # Default response
    return ChatCompletionResponse(
        id=f"chatcmpl-{datetime.now().timestamp()}",
        created=int(datetime.now().timestamp()),
        model=request.model,
        choices=[
            Choice(
                index=0,
                message=Message(
                    role="assistant",
                    content="Hermetic AI Platform ready for interaction"
                ),
                finish_reason="stop"
            )
        ]
    )


# ==================== WebSocket for Real-time ====================

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket for real-time communication"""
    await websocket.accept()
    server.websocket_connections.append(websocket)
    
    try:
        while True:
            # Receive message
            data = await websocket.receive_json()
            
            # Process based on message type
            if data.get("type") == "thinking":
                result = server.platform.sequential_thinking.process_thought(data.get("payload", {}))
                await websocket.send_json({"type": "thinking_result", "data": result})
                
            elif data.get("type") == "verify":
                result = server.verifier.verify_code(data.get("code", ""))
                await websocket.send_json({"type": "verification_result", "data": result})
                
            elif data.get("type") == "status":
                status = server.platform.get_platform_status()
                await websocket.send_json({"type": "status", "data": status})
                
            else:
                await websocket.send_json({"type": "error", "message": "Unknown message type"})
                
    except WebSocketDisconnect:
        server.websocket_connections.remove(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        server.websocket_connections.remove(websocket)


# ==================== Main Entry Point ====================

def main():
    """Run the API server"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Hermetic AI Platform Universal API Server")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind to")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload")
    
    args = parser.parse_args()
    
    logger.info(f"Starting Hermetic AI API Server on {args.host}:{args.port}")
    logger.info("API Documentation: http://localhost:8000/docs")
    logger.info("OpenAI-compatible endpoint: http://localhost:8000/v1/chat/completions")
    
    uvicorn.run(
        "api_server:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="info"
    )


if __name__ == "__main__":
    main()