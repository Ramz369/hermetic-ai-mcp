"""
Dynamic Module Loader System
Handles plugin discovery, loading, and lifecycle management
"""
import os
import importlib
import importlib.util
from pathlib import Path
from typing import Dict, Any, List, Optional, Type
from dataclasses import dataclass
import json
import logging
import inspect


@dataclass
class ModuleMetadata:
    """Module metadata"""
    name: str
    version: str
    description: str
    author: str
    dependencies: List[str]
    entry_point: str
    enabled: bool = True


class ModuleInterface:
    """Base interface for all modules"""
    
    def __init__(self, platform):
        self.platform = platform
        self.name = self.__class__.__name__
        self.version = "1.0.0"
        self.description = "Base module"
    
    def initialize(self) -> bool:
        """Initialize the module"""
        return True
    
    def shutdown(self) -> None:
        """Shutdown the module"""
        pass
    
    def get_tools(self) -> Dict[str, Any]:
        """Get tools provided by this module"""
        return {}
    
    def get_commands(self) -> Dict[str, Any]:
        """Get commands provided by this module"""
        return {}
    
    def on_event(self, event: str, data: Any) -> None:
        """Handle platform events"""
        pass


class ModuleLoader:
    """Dynamic module loader and manager"""
    
    def __init__(self, modules_dir: str = None):
        """
        Initialize the module loader
        
        Args:
            modules_dir: Directory containing modules
        """
        self.modules_dir = Path(modules_dir) if modules_dir else Path.home() / ".hermetic-ai" / "modules"
        self.modules_dir.mkdir(parents=True, exist_ok=True)
        
        self.loaded_modules: Dict[str, ModuleInterface] = {}
        self.module_metadata: Dict[str, ModuleMetadata] = {}
        self.module_errors: Dict[str, str] = {}
    
    def discover_modules(self) -> List[ModuleMetadata]:
        """
        Discover available modules
        
        Returns:
            List of discovered module metadata
        """
        discovered = []
        
        # Check modules directory
        for item in self.modules_dir.iterdir():
            if item.is_dir():
                metadata_file = item / "module.json"
                if metadata_file.exists():
                    try:
                        with open(metadata_file) as f:
                            metadata_dict = json.load(f)
                            metadata = ModuleMetadata(**metadata_dict)
                            discovered.append(metadata)
                            self.module_metadata[metadata.name] = metadata
                    except Exception as e:
                        self.module_errors[item.name] = f"Failed to load metadata: {e}"
        
        # Check built-in modules
        builtin_dir = Path(__file__).parent.parent / "modules"
        if builtin_dir.exists():
            for item in builtin_dir.iterdir():
                if item.is_file() and item.suffix == ".py" and item.stem != "__init__":
                    module_name = item.stem
                    if module_name not in self.module_metadata:
                        # Create default metadata for built-in modules
                        metadata = ModuleMetadata(
                            name=module_name,
                            version="1.0.0",
                            description=f"Built-in {module_name} module",
                            author="Hermetic AI",
                            dependencies=[],
                            entry_point=f"hermetic_ai_mcp.modules.{module_name}",
                            enabled=True
                        )
                        discovered.append(metadata)
                        self.module_metadata[module_name] = metadata
        
        return discovered
    
    def load_module(self, module_name: str, platform: Any = None) -> Optional[ModuleInterface]:
        """
        Load a specific module
        
        Args:
            module_name: Name of the module to load
            platform: Platform instance to pass to module
            
        Returns:
            Loaded module instance or None if failed
        """
        if module_name in self.loaded_modules:
            return self.loaded_modules[module_name]
        
        if module_name not in self.module_metadata:
            self.module_errors[module_name] = "Module not found"
            return None
        
        metadata = self.module_metadata[module_name]
        
        if not metadata.enabled:
            self.module_errors[module_name] = "Module is disabled"
            return None
        
        try:
            # Check dependencies
            for dep in metadata.dependencies:
                if dep not in self.loaded_modules:
                    # Try to load dependency first
                    if not self.load_module(dep, platform):
                        self.module_errors[module_name] = f"Dependency {dep} failed to load"
                        return None
            
            # Load the module
            if metadata.entry_point.startswith("hermetic_ai_mcp.modules"):
                # Built-in module
                module = importlib.import_module(metadata.entry_point)
            else:
                # External module
                module_path = self.modules_dir / module_name / "__init__.py"
                if not module_path.exists():
                    module_path = self.modules_dir / module_name / f"{module_name}.py"
                
                if not module_path.exists():
                    self.module_errors[module_name] = "Module file not found"
                    return None
                
                spec = importlib.util.spec_from_file_location(module_name, module_path)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
            
            # Find and instantiate the module class
            module_class = None
            for name, obj in inspect.getmembers(module):
                if inspect.isclass(obj) and issubclass(obj, ModuleInterface) and obj != ModuleInterface:
                    module_class = obj
                    break
            
            if not module_class:
                self.module_errors[module_name] = "No ModuleInterface subclass found"
                return None
            
            # Create instance
            instance = module_class(platform)
            
            # Initialize
            if not instance.initialize():
                self.module_errors[module_name] = "Module initialization failed"
                return None
            
            self.loaded_modules[module_name] = instance
            return instance
            
        except Exception as e:
            self.module_errors[module_name] = f"Failed to load: {e}"
            return None
    
    def unload_module(self, module_name: str) -> bool:
        """
        Unload a module
        
        Args:
            module_name: Name of the module to unload
            
        Returns:
            True if successful
        """
        if module_name not in self.loaded_modules:
            return False
        
        try:
            module = self.loaded_modules[module_name]
            module.shutdown()
            del self.loaded_modules[module_name]
            return True
        except Exception as e:
            self.module_errors[module_name] = f"Failed to unload: {e}"
            return False
    
    def reload_module(self, module_name: str, platform: Any = None) -> Optional[ModuleInterface]:
        """
        Reload a module
        
        Args:
            module_name: Name of the module to reload
            platform: Platform instance to pass to module
            
        Returns:
            Reloaded module instance or None if failed
        """
        self.unload_module(module_name)
        return self.load_module(module_name, platform)
    
    def get_all_tools(self) -> Dict[str, Any]:
        """
        Get all tools from loaded modules
        
        Returns:
            Combined tools dictionary
        """
        tools = {}
        for module in self.loaded_modules.values():
            tools.update(module.get_tools())
        return tools
    
    def get_all_commands(self) -> Dict[str, Any]:
        """
        Get all commands from loaded modules
        
        Returns:
            Combined commands dictionary
        """
        commands = {}
        for module in self.loaded_modules.values():
            commands.update(module.get_commands())
        return commands
    
    def broadcast_event(self, event: str, data: Any) -> None:
        """
        Broadcast an event to all loaded modules
        
        Args:
            event: Event name
            data: Event data
        """
        for module in self.loaded_modules.values():
            try:
                module.on_event(event, data)
            except Exception:
                # Silently ignore event handling errors
                pass
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get loader status
        
        Returns:
            Status dictionary
        """
        return {
            "modules_dir": str(self.modules_dir),
            "discovered": len(self.module_metadata),
            "loaded": len(self.loaded_modules),
            "errors": len(self.module_errors),
            "modules": {
                name: {
                    "loaded": name in self.loaded_modules,
                    "enabled": meta.enabled,
                    "version": meta.version,
                    "error": self.module_errors.get(name)
                }
                for name, meta in self.module_metadata.items()
            }
        }