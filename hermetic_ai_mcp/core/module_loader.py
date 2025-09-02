"""
Module Loader System - Dynamic module management for Hermetic AI Platform
Enables plugin-style extensibility with hot-reloading support
"""
import importlib
import importlib.util
import inspect
import json
from typing import Dict, Any, List, Optional, Type, Callable
from pathlib import Path
from dataclasses import dataclass, asdict
from datetime import datetime
from abc import ABC, abstractmethod
import logging

logger = logging.getLogger(__name__)


class ModuleInterface(ABC):
    """
    Base interface that all modules must implement
    """
    
    @abstractmethod
    def initialize(self, platform: Any) -> bool:
        """
        Initialize the module with platform reference
        
        Args:
            platform: Reference to HermeticAIPlatform instance
            
        Returns:
            Success status
        """
        pass
    
    @abstractmethod
    def get_tools(self) -> Dict[str, Callable]:
        """
        Get tools provided by this module
        
        Returns:
            Dictionary of tool_name -> tool_function
        """
        pass
    
    @abstractmethod
    def get_info(self) -> Dict[str, Any]:
        """
        Get module information
        
        Returns:
            Module metadata dictionary
        """
        pass
    
    @abstractmethod
    def shutdown(self) -> None:
        """Cleanup when module is unloaded"""
        pass


@dataclass
class ModuleConfig:
    """Configuration for a module"""
    name: str
    version: str
    author: str = ""
    description: str = ""
    enabled: bool = True
    dependencies: List[str] = None
    settings: Dict[str, Any] = None
    entry_point: str = ""  # Module entry point (file or class)
    module_type: str = "builtin"  # builtin, external, community
    
    def __post_init__(self):
        if self.dependencies is None:
            self.dependencies = []
        if self.settings is None:
            self.settings = {}


class ModuleRegistry:
    """Registry for managing available modules"""
    
    def __init__(self, registry_path: str = None):
        """
        Initialize module registry
        
        Args:
            registry_path: Path to registry file
        """
        if registry_path:
            path = Path(registry_path)
            # If it's a directory, append the filename
            if path.is_dir():
                self.registry_path = path / "module_registry.json"
            else:
                self.registry_path = path
        else:
            self.registry_path = Path.home() / ".hermetic-ai" / "module_registry.json"
        self.modules: Dict[str, ModuleConfig] = {}
        self._load_registry()
    
    def _load_registry(self):
        """Load registry from disk"""
        if self.registry_path.exists():
            try:
                with open(self.registry_path, 'r') as f:
                    data = json.load(f)
                    for name, config in data.items():
                        self.modules[name] = ModuleConfig(**config)
            except Exception as e:
                logger.error(f"Failed to load registry: {e}")
        else:
            # Initialize with default modules
            self._initialize_default_modules()
    
    def _initialize_default_modules(self):
        """Initialize registry with default built-in modules"""
        defaults = [
            ModuleConfig(
                name="sequential_thinking",
                version="1.0.0",
                description="Sequential thinking and problem-solving",
                entry_point="core.sequential_thinking.SequentialThinkingModule",
                module_type="builtin"
            ),
            ModuleConfig(
                name="lsp_integration",
                version="1.0.0",
                description="Language Server Protocol integration for code intelligence",
                entry_point="core.lsp_integration.LSPModule",
                dependencies=["pyls", "typescript-language-server"],
                module_type="builtin"
            ),
            ModuleConfig(
                name="verification",
                version="1.0.0",
                description="Code verification and quality assurance",
                entry_point="core.verification_engine.VerificationModule",
                module_type="builtin"
            ),
            ModuleConfig(
                name="memory",
                version="1.0.0",
                description="Dual-layer memory system",
                entry_point="core.memory_system.MemoryModule",
                module_type="builtin"
            )
        ]
        
        for config in defaults:
            self.modules[config.name] = config
        
        self._save_registry()
    
    def _save_registry(self):
        """Save registry to disk"""
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.registry_path, 'w') as f:
            data = {name: asdict(config) for name, config in self.modules.items()}
            json.dump(data, f, indent=2)
    
    def register(self, config: ModuleConfig):
        """Register a new module"""
        self.modules[config.name] = config
        self._save_registry()
        logger.info(f"Module registered: {config.name} v{config.version}")
    
    def unregister(self, name: str):
        """Unregister a module"""
        if name in self.modules:
            del self.modules[name]
            self._save_registry()
            logger.info(f"Module unregistered: {name}")
    
    def get_config(self, name: str) -> Optional[ModuleConfig]:
        """Get module configuration"""
        return self.modules.get(name)
    
    def list_modules(self, module_type: str = None, enabled_only: bool = False) -> List[ModuleConfig]:
        """List available modules"""
        modules = list(self.modules.values())
        
        if module_type:
            modules = [m for m in modules if m.module_type == module_type]
        
        if enabled_only:
            modules = [m for m in modules if m.enabled]
        
        return modules
    
    # Compatibility methods for tests
    def register_module(self, module: Any) -> bool:
        """Register a module (compatibility method)"""
        if hasattr(module, 'name') and hasattr(module, 'version'):
            config = ModuleConfig(
                name=module.name,
                version=module.version,
                description=getattr(module, 'description', ''),
                enabled=getattr(module, 'enabled', True)
            )
            self.register(config)
            # Store the actual module instance for retrieval
            if not hasattr(self, '_module_instances'):
                self._module_instances = {}
            self._module_instances[module.name] = module
            return True
        return False
    
    def unregister_module(self, name: str) -> bool:
        """Unregister a module (compatibility method)"""
        if name in self.modules:
            self.unregister(name)
            if hasattr(self, '_module_instances') and name in self._module_instances:
                del self._module_instances[name]
            return True
        return False
    
    def get_module(self, name: str) -> Any:
        """Get a module instance (compatibility method)"""
        if hasattr(self, '_module_instances'):
            return self._module_instances.get(name)
        return None
    
    @property
    def base_dir(self) -> Path:
        """Base directory (compatibility property)"""
        return self.registry_path.parent
    
    @property
    def builtin_modules(self) -> Dict:
        """Builtin modules (compatibility property)"""
        return {name: config for name, config in self.modules.items() 
                if config.module_type == "builtin"}
    
    @property
    def external_modules(self) -> Dict:
        """External modules (compatibility property)"""
        return {name: config for name, config in self.modules.items() 
                if config.module_type == "external"}


class ModuleLoader:
    """
    Dynamic module loader for the platform
    """
    
    def __init__(self, modules_dir: str = None):
        """
        Initialize module loader
        
        Args:
            modules_dir: Directory containing modules
        """
        self.modules_dir = Path(modules_dir) if modules_dir else \
                         Path(__file__).parent.parent / "modules"
        self.modules_dir.mkdir(parents=True, exist_ok=True)
        
        self.registry = ModuleRegistry()
        self.loaded_modules: Dict[str, ModuleInterface] = {}
        self.module_instances: Dict[str, Any] = {}
        
        logger.info(f"Module loader initialized with directory: {self.modules_dir}")
    
    def load_module(self, name: str, platform: Any = None) -> Optional[ModuleInterface]:
        """
        Load a module by name
        
        Args:
            name: Module name
            platform: Platform instance to pass to module
            
        Returns:
            Loaded module instance or None
        """
        # Check if already loaded
        if name in self.loaded_modules:
            logger.info(f"Module '{name}' already loaded")
            return self.loaded_modules[name]
        
        # Get module config
        config = self.registry.get_config(name)
        if not config:
            logger.error(f"Module '{name}' not found in registry")
            return None
        
        if not config.enabled:
            logger.warning(f"Module '{name}' is disabled")
            return None
        
        # Check dependencies
        for dep in config.dependencies:
            if dep not in self.loaded_modules:
                logger.info(f"Loading dependency '{dep}' for module '{name}'")
                if not self.load_module(dep, platform):
                    logger.error(f"Failed to load dependency '{dep}'")
                    return None
        
        try:
            # Load the module
            if config.module_type == "builtin":
                module_instance = self._load_builtin_module(config, platform)
            elif config.module_type == "external":
                module_instance = self._load_external_module(config, platform)
            else:
                module_instance = self._load_community_module(config, platform)
            
            if module_instance:
                self.loaded_modules[name] = module_instance
                logger.info(f"Module '{name}' loaded successfully")
                return module_instance
            
        except Exception as e:
            logger.error(f"Failed to load module '{name}': {e}")
            return None
    
    def _load_builtin_module(self, config: ModuleConfig, platform: Any) -> Optional[ModuleInterface]:
        """Load a built-in module"""
        try:
            # Parse entry point (e.g., "core.sequential_thinking.SequentialThinkingModule")
            parts = config.entry_point.rsplit('.', 1)
            if len(parts) == 2:
                module_path, class_name = parts
            else:
                # Try to create a wrapper for existing modules
                return self._create_module_wrapper(config, platform)
            
            # Import the module
            module = importlib.import_module(module_path)
            
            # Get the class
            if hasattr(module, class_name):
                module_class = getattr(module, class_name)
                
                # Instantiate and initialize
                instance = module_class()
                if isinstance(instance, ModuleInterface):
                    if instance.initialize(platform):
                        return instance
            else:
                # Create wrapper if class doesn't exist
                return self._create_module_wrapper(config, platform)
                
        except ImportError as e:
            logger.error(f"Failed to import builtin module: {e}")
            # Try to create wrapper as fallback
            return self._create_module_wrapper(config, platform)
        
        return None
    
    def _create_module_wrapper(self, config: ModuleConfig, platform: Any) -> Optional[ModuleInterface]:
        """Create a wrapper for modules that don't implement ModuleInterface"""
        
        class ModuleWrapper(ModuleInterface):
            def __init__(self, config: ModuleConfig, platform: Any):
                self.config = config
                self.platform = platform
                self.wrapped_module = None
                
                # Try to import the actual module
                if config.name == "sequential_thinking":
                    from ..core.sequential_thinking import SequentialThinkingEngine
                    self.wrapped_module = SequentialThinkingEngine()
                elif config.name == "lsp_integration":
                    from ..core.lsp_integration import LSPClient, CodeIntelligence
                    if platform and platform.current_project:
                        self.wrapped_module = LSPClient(platform.current_project.project_path)
                        self.code_intelligence = CodeIntelligence(self.wrapped_module)
                elif config.name == "verification":
                    from ..core.verification_engine import CodeVerifier
                    self.wrapped_module = CodeVerifier(
                        memory_system=platform.memory_system if platform else None
                    )
                elif config.name == "memory":
                    from ..core.memory_system import DualLayerMemory
                    self.wrapped_module = DualLayerMemory()
            
            def initialize(self, platform: Any) -> bool:
                return self.wrapped_module is not None
            
            def get_tools(self) -> Dict[str, Callable]:
                tools = {}
                
                if self.config.name == "sequential_thinking":
                    tools["sequential_thinking"] = self.wrapped_module.process_thought
                    tools["get_thought_summary"] = self.wrapped_module.get_thought_summary
                elif self.config.name == "lsp_integration":
                    if self.wrapped_module:
                        tools["find_symbol"] = self.wrapped_module.find_symbol
                        tools["get_references"] = self.wrapped_module.get_references
                elif self.config.name == "verification":
                    tools["verify_code"] = self.wrapped_module.verify_code
                    tools["verify_with_skepticism"] = self.wrapped_module.verify_with_skepticism
                    tools["generate_forensic_report"] = self.wrapped_module.generate_forensic_report
                elif self.config.name == "memory":
                    tools["store_memory"] = self.wrapped_module.store
                    tools["search_memory"] = self.wrapped_module.search
                    tools["get_relevant_context"] = self.wrapped_module.get_relevant_context
                
                return tools
            
            def get_info(self) -> Dict[str, Any]:
                return asdict(self.config)
            
            def shutdown(self) -> None:
                if hasattr(self.wrapped_module, 'close'):
                    self.wrapped_module.close()
                elif hasattr(self.wrapped_module, 'shutdown'):
                    self.wrapped_module.shutdown()
        
        try:
            wrapper = ModuleWrapper(config, platform)
            if wrapper.initialize(platform):
                return wrapper
        except Exception as e:
            logger.error(f"Failed to create wrapper for {config.name}: {e}")
        
        return None
    
    def _load_external_module(self, config: ModuleConfig, platform: Any) -> Optional[ModuleInterface]:
        """Load an external module from file"""
        module_path = self.modules_dir / config.name / "__init__.py"
        
        if not module_path.exists():
            module_path = self.modules_dir / f"{config.name}.py"
        
        if not module_path.exists():
            logger.error(f"Module file not found: {module_path}")
            return None
        
        try:
            # Load module from file
            spec = importlib.util.spec_from_file_location(config.name, module_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            # Find ModuleInterface implementation
            for name, obj in inspect.getmembers(module):
                if inspect.isclass(obj) and issubclass(obj, ModuleInterface) and obj != ModuleInterface:
                    instance = obj()
                    if instance.initialize(platform):
                        return instance
            
        except Exception as e:
            logger.error(f"Failed to load external module: {e}")
        
        return None
    
    def _load_community_module(self, config: ModuleConfig, platform: Any) -> Optional[ModuleInterface]:
        """Load a community module (downloaded from marketplace)"""
        # Similar to external but with additional validation
        return self._load_external_module(config, platform)
    
    def unload_module(self, name: str):
        """Unload a module"""
        if name in self.loaded_modules:
            module = self.loaded_modules[name]
            module.shutdown()
            del self.loaded_modules[name]
            logger.info(f"Module '{name}' unloaded")
    
    def reload_module(self, name: str, platform: Any = None) -> Optional[ModuleInterface]:
        """Reload a module (useful for development)"""
        self.unload_module(name)
        return self.load_module(name, platform)
    
    def get_loaded_modules(self) -> Dict[str, ModuleInterface]:
        """Get all loaded modules"""
        return self.loaded_modules.copy()
    
    def get_module_tools(self, name: str) -> Dict[str, Callable]:
        """Get tools from a specific module"""
        if name in self.loaded_modules:
            return self.loaded_modules[name].get_tools()
        return {}
    
    def get_all_tools(self) -> Dict[str, Callable]:
        """Get all tools from all loaded modules"""
        all_tools = {}
        for name, module in self.loaded_modules.items():
            tools = module.get_tools()
            for tool_name, tool_func in tools.items():
                # Prefix with module name to avoid conflicts
                full_name = f"{name}.{tool_name}" if not tool_name.startswith(f"{name}.") else tool_name
                all_tools[full_name] = tool_func
        return all_tools
    
    # Compatibility methods for tests
    def discover_builtin_modules(self) -> List[str]:
        """Discover builtin modules (compatibility method)"""
        builtin_configs = self.registry.list_modules(module_type="builtin")
        return [config.name for config in builtin_configs]
    
    def load_external_module(self, name: str) -> bool:
        """Load an external module (compatibility method)"""
        config = self.registry.get_config(name)
        if config and config.module_type == "external":
            module = self._load_external_module(config, None)
            if module:
                self.loaded_modules[name] = module
                return True
        return False
    
    def validate_module_config(self, config: Dict[str, Any]) -> bool:
        """Validate module configuration (compatibility method)"""
        required_fields = ["name", "version", "main"]
        return all(field in config for field in required_fields)
    
    def enable_module(self, name: str) -> bool:
        """Enable a module (compatibility method)"""
        if name in self.loaded_modules:
            module = self.loaded_modules[name]
            if hasattr(module, 'enabled'):
                module.enabled = True
                return True
        # Also check registry's module instances
        if hasattr(self.registry, '_module_instances') and name in self.registry._module_instances:
            module = self.registry._module_instances[name]
            if hasattr(module, 'enabled'):
                module.enabled = True
                return True
        return False
    
    def disable_module(self, name: str) -> bool:
        """Disable a module (compatibility method)"""
        if name in self.loaded_modules:
            module = self.loaded_modules[name]
            if hasattr(module, 'enabled'):
                module.enabled = False
                return True
        # Also check registry's module instances
        if hasattr(self.registry, '_module_instances') and name in self.registry._module_instances:
            module = self.registry._module_instances[name]
            if hasattr(module, 'enabled'):
                module.enabled = False
                return True
        return False
    
    def get_module_info(self, name: str) -> Optional[Dict[str, Any]]:
        """Get module information (compatibility method)"""
        # Check loaded modules first
        if name in self.loaded_modules:
            module = self.loaded_modules[name]
            if hasattr(module, 'get_info'):
                return module.get_info()
        # Check registry's module instances
        if hasattr(self.registry, '_module_instances') and name in self.registry._module_instances:
            module = self.registry._module_instances[name]
            return {
                "name": getattr(module, 'name', name),
                "version": getattr(module, 'version', '1.0.0'),
                "description": getattr(module, 'description', ''),
                "enabled": getattr(module, 'enabled', True)
            }
        # Fall back to config
        config = self.registry.get_config(name)
        if config:
            return asdict(config)
        return None
    
    def list_available_modules(self) -> List[Dict[str, Any]]:
        """List available modules (compatibility method)"""
        modules = []
        # Add loaded modules
        for name in self.loaded_modules:
            info = self.get_module_info(name)
            if info:
                modules.append(info)
        # Add registered but not loaded modules
        for config in self.registry.list_modules():
            if config.name not in self.loaded_modules:
                modules.append({
                    "name": config.name,
                    "version": config.version,
                    "enabled": config.enabled
                })
        return modules