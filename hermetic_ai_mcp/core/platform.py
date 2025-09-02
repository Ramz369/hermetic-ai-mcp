"""
Hermetic AI Platform - Core Platform Module
Universal MCP with auto-project detection and modular architecture
"""
import os
import json
import hashlib
import asyncio
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass, asdict
import logging

from .sequential_thinking import SequentialThinkingEngine
from .lsp_integration import LSPClient, CodeIntelligence, Language

# Disable logging for MCP compatibility
if not os.environ.get('DEBUG_MCP'):
    logging.disable(logging.CRITICAL)
logger = logging.getLogger(__name__)


@dataclass
class ProjectContext:
    """Represents a detected project and its context"""
    project_hash: str
    project_path: str
    project_type: str  # python, javascript, mixed, etc.
    created_at: datetime
    last_accessed: datetime
    config: Dict[str, Any] = None
    memory_path: str = None
    is_new: bool = False
    
    def __post_init__(self):
        if self.config is None:
            self.config = {}
        if self.memory_path is None:
            self.memory_path = f"~/.hermetic-ai/projects/{self.project_hash}"


class ProjectDetector:
    """
    Automatically detects and manages project contexts
    """
    
    PROJECT_INDICATORS = {
        'python': ['pyproject.toml', 'setup.py', 'requirements.txt', 'Pipfile'],
        'javascript': ['package.json', 'yarn.lock', 'pnpm-lock.yaml'],
        'typescript': ['tsconfig.json'],
        'rust': ['Cargo.toml'],
        'go': ['go.mod'],
        'java': ['pom.xml', 'build.gradle'],
        'csharp': ['*.csproj', '*.sln'],
        'ruby': ['Gemfile'],
        'php': ['composer.json'],
        'elixir': ['mix.exs']
    }
    
    def __init__(self, base_dir: str = None):
        """
        Initialize project detector
        
        Args:
            base_dir: Base directory for project storage
        """
        self.base_dir = Path(base_dir) if base_dir else Path.home() / ".hermetic-ai"
        self.projects_dir = self.base_dir / "projects"
        self.projects_dir.mkdir(parents=True, exist_ok=True)
        
        self.project_registry = self._load_registry()
    
    def _load_registry(self) -> Dict[str, Dict]:
        """Load the project registry from disk"""
        registry_file = self.base_dir / "project_registry.json"
        if registry_file.exists():
            try:
                with open(registry_file, 'r') as f:
                    return json.load(f)
            except:
                return {}
        return {}
    
    def _save_registry(self):
        """Save the project registry to disk"""
        registry_file = self.base_dir / "project_registry.json"
        with open(registry_file, 'w') as f:
            json.dump(self.project_registry, f, indent=2, default=str)
    
    def generate_project_hash(self, project_path: str) -> str:
        """
        Generate a unique hash for a project based on its path
        
        Args:
            project_path: Path to the project
            
        Returns:
            Unique project hash
        """
        # Use absolute path for consistent hashing
        abs_path = os.path.abspath(project_path)
        return hashlib.sha256(abs_path.encode()).hexdigest()[:16]
    
    def detect_project_type(self, project_path: str) -> str:
        """
        Detect the type of project based on files present
        
        Args:
            project_path: Path to the project
            
        Returns:
            Project type (python, javascript, mixed, etc.)
        """
        path = Path(project_path)
        detected_types = []
        
        for lang, indicators in self.PROJECT_INDICATORS.items():
            for indicator in indicators:
                if "*" in indicator:
                    # Handle glob patterns
                    if list(path.glob(indicator)):
                        detected_types.append(lang)
                        break
                else:
                    # Check for specific file
                    if (path / indicator).exists():
                        detected_types.append(lang)
                        break
        
        if not detected_types:
            return "unknown"
        elif len(detected_types) == 1:
            return detected_types[0]
        else:
            # Multiple types detected
            if 'typescript' in detected_types and 'javascript' in detected_types:
                return 'typescript'  # TypeScript is superset
            return "mixed"
    
    def detect_project(self, cwd: str) -> ProjectContext:
        """
        Detect and load/create project context
        
        Args:
            cwd: Current working directory
            
        Returns:
            ProjectContext object
        """
        project_hash = self.generate_project_hash(cwd)
        
        # Check if project already exists
        if project_hash in self.project_registry:
            # Load existing project
            project_info = self.project_registry[project_hash]
            
            # Update last accessed time
            project_info['last_accessed'] = datetime.now()
            self._save_registry()
            
            return ProjectContext(
                project_hash=project_hash,
                project_path=cwd,
                project_type=project_info['type'],
                created_at=datetime.fromisoformat(project_info['created']),
                last_accessed=project_info['last_accessed'],
                config=project_info.get('config', {}),
                is_new=False
            )
        else:
            # New project - create context
            project_type = self.detect_project_type(cwd)
            now = datetime.now()
            
            project_context = ProjectContext(
                project_hash=project_hash,
                project_path=cwd,
                project_type=project_type,
                created_at=now,
                last_accessed=now,
                is_new=True
            )
            
            # Create project directory
            project_dir = self.projects_dir / project_hash
            project_dir.mkdir(exist_ok=True)
            
            # Save to registry
            self.project_registry[project_hash] = {
                'path': cwd,
                'type': project_type,
                'created': now.isoformat(),
                'last_accessed': now.isoformat(),
                'config': {}
            }
            self._save_registry()
            
            return project_context
    
    def get_project_by_name(self, name: str) -> Optional[ProjectContext]:
        """Get project by name or hash"""
        # First check if it's a hash
        if name in self.project_registry:
            info = self.project_registry[name]
            return ProjectContext(
                project_hash=name,
                project_path=info['path'],
                project_type=info['type'],
                created_at=datetime.fromisoformat(info['created']),
                last_accessed=datetime.fromisoformat(info['last_accessed']),
                config=info.get('config', {}),
                is_new=False
            )
        
        # Check if it's a path
        for hash_id, info in self.project_registry.items():
            if info['path'].endswith(name) or name in info['path']:
                return ProjectContext(
                    project_hash=hash_id,
                    project_path=info['path'],
                    project_type=info['type'],
                    created_at=datetime.fromisoformat(info['created']),
                    last_accessed=datetime.fromisoformat(info['last_accessed']),
                    config=info.get('config', {}),
                    is_new=False
                )
        
        return None


class HermeticAIPlatform:
    """
    Main platform class - orchestrates all components
    """
    
    def __init__(self, base_dir: str = None, auto_detect: bool = True):
        """
        Initialize the Hermetic AI Platform
        
        Args:
            base_dir: Base directory for platform data
            auto_detect: Whether to auto-detect projects
        """
        self.base_dir = Path(base_dir) if base_dir else Path.home() / ".hermetic-ai"
        self.base_dir.mkdir(parents=True, exist_ok=True)
        
        self.auto_detect = auto_detect
        
        # Initialize core components
        self.project_detector = ProjectDetector(str(self.base_dir))
        self.current_project: Optional[ProjectContext] = None
        # Initialize memory system with base directory
        from .memory_system import DualLayerMemorySystem
        self.memory_system = DualLayerMemorySystem(str(self.base_dir / "memory"))
        self.sequential_thinking = SequentialThinkingEngine()
        self.lsp_client: Optional[LSPClient] = None
        self.code_intelligence: Optional[CodeIntelligence] = None
        
        # Module registry
        self.modules: Dict[str, Any] = {}
        self.tools: Dict[str, Any] = {}
        
        # Session tracking
        self.session_id: Optional[str] = None
        self.session_start: Optional[datetime] = None
        
        pass  # Platform initialized
    
    def on_session_start(self, cwd: str = None) -> str:
        """
        Called when a new session starts (Claude Desktop connection)
        
        Args:
            cwd: Current working directory
            
        Returns:
            Session ID
        """
        # Generate session ID
        self.session_id = hashlib.sha256(
            f"{datetime.now().isoformat()}_{cwd}".encode()
        ).hexdigest()[:16]
        self.session_start = datetime.now()
        
        pass  # Session started
        
        # Auto-detect project if enabled
        if self.auto_detect and cwd:
            self.current_project = self.project_detector.detect_project(cwd)
            
            if self.current_project.is_new:
                pass  # New project detected
                # Could trigger setup wizard here
            else:
                pass  # Existing project loaded
            
            # Initialize LSP for the project
            self.lsp_client = LSPClient(self.current_project.project_path)
            self.code_intelligence = CodeIntelligence(self.lsp_client)
            
            # Load project memory
            self._load_project_memory()
        
        return self.session_id
    
    def _load_project_memory(self):
        """Load memory for current project"""
        if not self.current_project:
            return
        
        # Initialize memory system if not already done
        if not self.memory_system:
            from .memory_system import DualLayerMemory
            self.memory_system = DualLayerMemory(str(self.base_dir))
        
        # Set the project in memory system
        self.memory_system.set_project(self.current_project.project_hash)
        
        # Import MemoryScope locally
        from .memory_system import MemoryScope
        
        # Load recent memories for context
        recent_memories = self.memory_system.search(
            query="*",  # Get all recent memories
            scope=MemoryScope.PROJECT,
            limit=20
        )
        
        pass  # Memories loaded
        
        # Attach memory system to other components
        if self.sequential_thinking:
            self.sequential_thinking.memory_system = self.memory_system
    
    async def process_tool_call(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a tool call from Claude
        
        Args:
            tool_name: Name of the tool to call
            arguments: Tool arguments
            
        Returns:
            Tool execution result
        """
        # Route to appropriate handler
        if tool_name == "sequential_thinking":
            return self.sequential_thinking.process_thought(arguments)
        
        elif tool_name == "find_symbol":
            if not self.code_intelligence:
                return {"error": "No project loaded"}
            symbols = await self.code_intelligence.lsp.find_symbol(
                arguments.get("symbol_name"),
                arguments.get("language")
            )
            return {
                "success": True,
                "symbols": [asdict(s) for s in symbols]
            }
        
        elif tool_name == "verify_code":
            # Route to verification engine (from Hermetic)
            return await self._verify_code(arguments.get("code"))
        
        elif tool_name in self.tools:
            # Call registered tool
            return await self.tools[tool_name](arguments)
        
        else:
            return {"error": f"Unknown tool: {tool_name}"}
    
    async def _verify_code(self, code: str, file_path: str = None, language: str = "python") -> Dict[str, Any]:
        """Verify code using Hermetic verification engine"""
        # Initialize verification engine if needed
        if not hasattr(self, 'verification_engine'):
            from .verification_engine import CodeVerifier
            self.verification_engine = CodeVerifier(
                memory_system=self.memory_system,
                strict_mode=True
            )
        
        # Perform verification
        result = self.verification_engine.verify_code(
            code=code,
            file_path=file_path,
            language=language
        )
        
        # Store verification result in memory if available
        if self.memory_system and result:
            from .memory_system import MemoryType, MemoryScope
            self.memory_system.store(
                content=f"Verification result: {result['passed']}",
                memory_type=MemoryType.VERIFICATION,
                scope=MemoryScope.PROJECT,
                metadata={
                    'code_hash': result.get('code_hash'),
                    'passed': result['passed'],
                    'has_mocks': result.get('has_mocks', False),
                    'violations': result.get('violations', []),
                    'confidence': result.get('confidence', 0)
                }
            )
        
        return result
    
    def register_module(self, name: str, module: Any):
        """
        Register a module with the platform
        
        Args:
            name: Module name
            module: Module instance
        """
        self.modules[name] = module
        pass  # Module registered
        
        # Register module tools
        if hasattr(module, 'get_tools'):
            tools = module.get_tools()
            for tool_name, tool_func in tools.items():
                self.register_tool(f"{name}.{tool_name}", tool_func)
    
    def register_tool(self, name: str, handler: Any):
        """
        Register a tool handler
        
        Args:
            name: Tool name
            handler: Tool handler function
        """
        self.tools[name] = handler
        pass  # Tool registered
    
    def get_platform_status(self) -> Dict[str, Any]:
        """Get current platform status"""
        return {
            "session_id": self.session_id,
            "session_duration": (
                (datetime.now() - self.session_start).total_seconds()
                if self.session_start else 0
            ),
            "current_project": {
                "hash": self.current_project.project_hash,
                "path": self.current_project.project_path,
                "type": self.current_project.project_type
            } if self.current_project else None,
            "modules_loaded": list(self.modules.keys()),
            "tools_available": list(self.tools.keys()),
            "thinking_summary": self.sequential_thinking.get_thought_summary(),
            "lsp_servers": (
                list(self.lsp_client.initialized_servers)
                if self.lsp_client else []
            )
        }
    
    async def shutdown(self):
        """Shutdown the platform cleanly"""
        pass  # Shutting down
        
        # Shutdown LSP servers
        if self.lsp_client:
            await self.lsp_client.shutdown()
        
        # Save session data
        if self.session_id:
            session_data = {
                "session_id": self.session_id,
                "start": self.session_start.isoformat(),
                "end": datetime.now().isoformat(),
                "project": self.current_project.project_hash if self.current_project else None,
                "thinking_session": self.sequential_thinking.export_session()
            }
            
            # Save to session history
            session_file = self.base_dir / "sessions" / f"{self.session_id}.json"
            session_file.parent.mkdir(exist_ok=True)
            with open(session_file, 'w') as f:
                json.dump(session_data, f, indent=2)
        
        pass  # Shutdown complete