"""
LSP Integration Module - Reimplemented for Hermetic AI Platform
Based on Serena's LSP architecture, providing code intelligence
"""
import asyncio
import json
import subprocess
import hashlib
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
import logging
from .lsp_protocol import LSPProtocol, LSPMessage

logger = logging.getLogger(__name__)


class Language(Enum):
    """Supported programming languages with LSP"""
    PYTHON = "python"
    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"
    GO = "go"
    RUST = "rust"
    JAVA = "java"
    CSHARP = "csharp"
    PHP = "php"
    RUBY = "ruby"
    CPP = "cpp"
    SWIFT = "swift"
    KOTLIN = "kotlin"
    ELIXIR = "elixir"
    CLOJURE = "clojure"
    BASH = "bash"
    TERRAFORM = "terraform"


@dataclass
class Symbol:
    """Represents a code symbol"""
    name: str
    kind: str  # function, class, method, variable, etc.
    location: str  # file path
    line: int
    column: int
    container: Optional[str] = None  # parent symbol
    documentation: Optional[str] = None
    signature: Optional[str] = None


@dataclass
class LSPServerConfig:
    """Configuration for a language server"""
    language: Language
    command: List[str]
    initialization_options: Dict[str, Any] = None
    workspace_folders: List[str] = None
    
    def __post_init__(self):
        if self.initialization_options is None:
            self.initialization_options = {}
        if self.workspace_folders is None:
            self.workspace_folders = []


class LSPClient:
    """
    Unified LSP client for multiple language servers
    Reimplemented from Serena's SolidLanguageServer
    """
    
    # Language server commands mapping
    LANGUAGE_SERVERS = {
        Language.PYTHON: ["pylsp"],  # python-lsp-server
        Language.JAVASCRIPT: ["typescript-language-server", "--stdio"],
        Language.TYPESCRIPT: ["typescript-language-server", "--stdio"],
        Language.GO: ["gopls"],
        Language.RUST: ["rust-analyzer"],
        Language.JAVA: ["jdtls"],
        Language.CSHARP: ["omnisharp", "-lsp"],
        Language.PHP: ["intelephense", "--stdio"],
        Language.RUBY: ["solargraph", "stdio"],
        Language.CPP: ["clangd"],
        Language.SWIFT: ["sourcekit-lsp"],
        Language.KOTLIN: ["kotlin-language-server"],
        Language.ELIXIR: ["elixir-ls"],
        Language.CLOJURE: ["clojure-lsp"],
        Language.BASH: ["bash-language-server", "start"],
        Language.TERRAFORM: ["terraform-ls", "serve"]
    }
    
    def __init__(self, project_path: str, cache_dir: str = None):
        """
        Initialize LSP client
        
        Args:
            project_path: Root path of the project
            cache_dir: Directory for caching LSP data
        """
        self.project_path = Path(project_path)
        self.cache_dir = Path(cache_dir) if cache_dir else Path.home() / ".hermetic-ai" / "lsp-cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        self.servers: Dict[Language, subprocess.Popen] = {}
        self.server_configs: Dict[Language, LSPServerConfig] = {}
        self.symbol_cache: Dict[str, List[Symbol]] = {}
        self.initialized_servers: set = set()
        
    async def start_server(self, language: Language) -> bool:
        """
        Start a language server for the specified language
        
        Args:
            language: Programming language
            
        Returns:
            Success status
        """
        if language in self.servers:
            return True  # Already running
        
        if language not in self.LANGUAGE_SERVERS:
            logger.warning(f"No language server configured for {language.value}")
            return False
        
        try:
            cmd = self.LANGUAGE_SERVERS[language]
            
            # Start the language server process
            self.servers[language] = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=str(self.project_path)
            )
            
            # Initialize the server
            await self._initialize_server(language)
            
            self.initialized_servers.add(language)
            logger.info(f"Started {language.value} language server")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start {language.value} server: {e}")
            return False
    
    async def _initialize_server(self, language: Language):
        """Initialize a language server with LSP protocol"""
        # Create LSP protocol handler for this server
        if language not in self.servers:
            logger.error(f"Server not started for {language.value}")
            return
        
        # Create protocol handler
        protocol = LSPProtocol(self.servers[language])
        await protocol.start()
        
        # Store protocol handler
        if not hasattr(self, 'protocols'):
            self.protocols = {}
        self.protocols[language] = protocol
        
        # Initialize with proper LSP handshake
        capabilities = {
            "textDocument": {
                "synchronization": {
                    "dynamicRegistration": False,
                    "didSave": True
                },
                "completion": {"dynamicRegistration": False},
                "hover": {"dynamicRegistration": False},
                "signatureHelp": {"dynamicRegistration": False},
                "definition": {"dynamicRegistration": False},
                "references": {"dynamicRegistration": False},
                "documentSymbol": {"dynamicRegistration": False},
                "formatting": {"dynamicRegistration": False},
                "rename": {"dynamicRegistration": False}
            },
            "workspace": {
                "symbol": {"dynamicRegistration": False}
            }
        }
        
        try:
            server_capabilities = await protocol.initialize(
                root_uri=f"file://{self.project_path}",
                capabilities=capabilities
            )
            logger.info(f"Initialized {language.value} server with capabilities: {server_capabilities}")
        except Exception as e:
            logger.error(f"Failed to initialize {language.value} server: {e}")
    
    async def find_symbol(self, symbol_name: str, language: Language = None) -> List[Symbol]:
        """
        Find symbols by name
        
        Args:
            symbol_name: Name of the symbol to find
            language: Optional language filter
            
        Returns:
            List of matching symbols
        """
        # Check cache first
        cache_key = f"{symbol_name}_{language.value if language else 'all'}"
        if cache_key in self.symbol_cache:
            return self.symbol_cache[cache_key]
        
        symbols = []
        
        # Determine which language servers to query
        languages = [language] if language else list(self.initialized_servers)
        
        for lang in languages:
            if lang not in self.servers:
                await self.start_server(lang)
            
            # Query language server for symbols
            # In real implementation, would use LSP workspace/symbol request
            lang_symbols = await self._query_symbols(lang, symbol_name)
            symbols.extend(lang_symbols)
        
        # Cache results
        self.symbol_cache[cache_key] = symbols
        return symbols
    
    async def _query_symbols(self, language: Language, query: str) -> List[Symbol]:
        """Query language server for symbols"""
        symbols = []
        
        # Get protocol handler
        if hasattr(self, 'protocols') and language in self.protocols:
            protocol = self.protocols[language]
            
            try:
                # Use LSP workspace/symbol request
                lsp_symbols = await protocol.workspace_symbol(query)
                
                # Convert LSP symbols to our Symbol format
                for lsp_symbol in lsp_symbols:
                    location = lsp_symbol.get('location', {})
                    uri = location.get('uri', '')
                    file_path = uri.replace('file://', '') if uri else ''
                    
                    position = location.get('range', {}).get('start', {})
                    
                    symbols.append(Symbol(
                        name=lsp_symbol.get('name', query),
                        kind=lsp_symbol.get('kind', 'unknown'),
                        location=file_path,
                        line=position.get('line', 0),
                        column=position.get('character', 0),
                        container=lsp_symbol.get('containerName')
                    ))
                
                return symbols
            except Exception as e:
                logger.warning(f"LSP symbol query failed: {e}, falling back to file search")
        
        # Fallback to file search if LSP not available
        symbols = []
        
        # Get file extensions for language
        extensions = {
            Language.PYTHON: [".py"],
            Language.JAVASCRIPT: [".js", ".jsx"],
            Language.TYPESCRIPT: [".ts", ".tsx"],
            Language.GO: [".go"],
            Language.RUST: [".rs"],
            Language.JAVA: [".java"],
            Language.CSHARP: [".cs"],
            Language.PHP: [".php"],
            Language.RUBY: [".rb"],
            Language.CPP: [".cpp", ".cc", ".h", ".hpp"],
        }.get(language, [])
        
        for ext in extensions:
            for file_path in self.project_path.rglob(f"*{ext}"):
                # Basic symbol extraction (would be replaced by LSP)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        for line_no, line in enumerate(f, 1):
                            if query in line:
                                # Detect symbol type (simplified)
                                kind = self._detect_symbol_kind(line, language)
                                if kind:
                                    symbols.append(Symbol(
                                        name=query,
                                        kind=kind,
                                        location=str(file_path),
                                        line=line_no,
                                        column=line.index(query)
                                    ))
                except Exception:
                    continue
        
        return symbols
    
    def _detect_symbol_kind(self, line: str, language: Language) -> Optional[str]:
        """Detect the kind of symbol from a line of code"""
        line = line.strip()
        
        if language == Language.PYTHON:
            if line.startswith("class "):
                return "class"
            elif line.startswith("def "):
                return "function"
            elif "=" in line and not line.startswith("#"):
                return "variable"
        elif language in [Language.JAVASCRIPT, Language.TYPESCRIPT]:
            if "class " in line:
                return "class"
            elif "function " in line or "const " in line or "let " in line:
                return "function" if "function" in line else "variable"
        elif language == Language.GO:
            if line.startswith("type ") and "struct" in line:
                return "struct"
            elif line.startswith("func "):
                return "function"
        
        return None
    
    async def get_references(self, symbol: Symbol) -> List[Symbol]:
        """
        Get all references to a symbol
        
        Args:
            symbol: The symbol to find references for
            
        Returns:
            List of reference locations
        """
        references = []
        
        # Detect language from file
        language = self._detect_language(symbol.location)
        if not language:
            return references
        
        # Get protocol handler
        if hasattr(self, 'protocols') and language in self.protocols:
            protocol = self.protocols[language]
            
            try:
                # Use LSP textDocument/references request
                file_uri = f"file://{symbol.location}"
                lsp_references = await protocol.text_document_references(
                    uri=file_uri,
                    line=symbol.line,
                    character=symbol.column
                )
                
                # Convert LSP references to our Symbol format
                for lsp_ref in lsp_references:
                    uri = lsp_ref.get('uri', '')
                    file_path = uri.replace('file://', '') if uri else ''
                    position = lsp_ref.get('range', {}).get('start', {})
                    
                    references.append(Symbol(
                        name=symbol.name,
                        kind="reference",
                        location=file_path,
                        line=position.get('line', 0),
                        column=position.get('character', 0)
                    ))
                
                return references
            except Exception as e:
                logger.warning(f"LSP references query failed: {e}, falling back to file search")
        
        # Fallback to file search
        references = []
        
        # Simplified: search for symbol name in all files
        for file_path in self.project_path.rglob("*"):
            if file_path.is_file():
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        for line_no, line in enumerate(f, 1):
                            if symbol.name in line:
                                references.append(Symbol(
                                    name=symbol.name,
                                    kind="reference",
                                    location=str(file_path),
                                    line=line_no,
                                    column=line.index(symbol.name)
                                ))
                except Exception:
                    continue
        
        return references
    
    async def get_definition(self, file_path: str, line: int, column: int) -> Optional[Symbol]:
        """
        Get definition of symbol at position
        
        Args:
            file_path: Path to the file
            line: Line number (1-indexed)
            column: Column number (0-indexed)
            
        Returns:
            Symbol definition or None
        """
        # Detect language from file extension
        language = self._detect_language(file_path)
        if not language:
            return None
        
        # Ensure server is running
        if language not in self.servers:
            await self.start_server(language)
        
        # Get protocol handler
        if hasattr(self, 'protocols') and language in self.protocols:
            protocol = self.protocols[language]
            
            try:
                # Use LSP textDocument/definition request
                file_uri = f"file://{file_path}"
                definitions = await protocol.text_document_definition(
                    uri=file_uri,
                    line=line - 1,  # LSP uses 0-based indexing
                    character=column
                )
                
                # Convert first definition to our Symbol format
                if definitions:
                    definition = definitions[0]
                    uri = definition.get('uri', '')
                    def_file = uri.replace('file://', '') if uri else ''
                    position = definition.get('range', {}).get('start', {})
                    
                    # Try to get symbol name from the file
                    return Symbol(
                        name="definition",
                        kind="definition",
                        location=def_file,
                        line=position.get('line', 0) + 1,  # Convert back to 1-based
                        column=position.get('character', 0)
                    )
            except Exception as e:
                logger.warning(f"LSP definition query failed: {e}")
        
        return None
    
    def _detect_language(self, file_path: str) -> Optional[Language]:
        """Detect language from file extension"""
        ext_to_lang = {
            ".py": Language.PYTHON,
            ".js": Language.JAVASCRIPT,
            ".jsx": Language.JAVASCRIPT,
            ".ts": Language.TYPESCRIPT,
            ".tsx": Language.TYPESCRIPT,
            ".go": Language.GO,
            ".rs": Language.RUST,
            ".java": Language.JAVA,
            ".cs": Language.CSHARP,
            ".php": Language.PHP,
            ".rb": Language.RUBY,
            ".cpp": Language.CPP,
            ".cc": Language.CPP,
            ".h": Language.CPP,
            ".hpp": Language.CPP,
            ".swift": Language.SWIFT,
            ".kt": Language.KOTLIN,
            ".ex": Language.ELIXIR,
            ".exs": Language.ELIXIR,
            ".clj": Language.CLOJURE,
            ".sh": Language.BASH,
            ".bash": Language.BASH,
            ".tf": Language.TERRAFORM
        }
        
        path = Path(file_path)
        return ext_to_lang.get(path.suffix)
    
    async def shutdown(self):
        """Shutdown all language servers"""
        # Shutdown protocol handlers first
        if hasattr(self, 'protocols'):
            for language, protocol in self.protocols.items():
                try:
                    await protocol.shutdown()
                    await protocol.stop()
                except Exception as e:
                    logger.error(f"Error shutting down protocol for {language.value}: {e}")
        
        # Then terminate processes
        for language, process in self.servers.items():
            try:
                process.terminate()
                process.wait(timeout=5)
            except:
                process.kill()
            logger.info(f"Shut down {language.value} language server")
        
        self.servers.clear()
        self.initialized_servers.clear()
        if hasattr(self, 'protocols'):
            self.protocols.clear()
    
    def clear_cache(self):
        """Clear symbol cache"""
        self.symbol_cache.clear()
    
    def _get_python_server_cmd(self) -> List[str]:
        """Get Python language server command (compatibility method)"""
        return ["pylsp"]
    
    def _get_javascript_server_cmd(self) -> List[str]:
        """Get JavaScript language server command (compatibility method)"""
        return ["typescript-language-server", "--stdio"]


class CodeIntelligence:
    """
    High-level code intelligence features
    Built on top of LSP integration
    """
    
    def __init__(self, lsp_client: LSPClient):
        """
        Initialize code intelligence
        
        Args:
            lsp_client: LSP client instance
        """
        self.lsp = lsp_client
        
    async def find_implementations(self, interface_name: str) -> List[Symbol]:
        """Find all implementations of an interface/abstract class"""
        # First find the interface definition
        interfaces = await self.lsp.find_symbol(interface_name)
        
        implementations = []
        for interface in interfaces:
            if interface.kind in ["interface", "abstract_class", "trait"]:
                # Find classes that implement/extend this interface
                refs = await self.lsp.get_references(interface)
                for ref in refs:
                    # Check if reference is an implementation
                    # (simplified logic)
                    implementations.append(ref)
        
        return implementations
    
    async def find_usages(self, symbol_name: str) -> Dict[str, List[Symbol]]:
        """
        Find all usages of a symbol, categorized by type
        
        Returns:
            Dictionary with categories: definitions, references, imports, etc.
        """
        symbols = await self.lsp.find_symbol(symbol_name)
        
        usages = {
            "definitions": [],
            "references": [],
            "imports": [],
            "exports": []
        }
        
        for symbol in symbols:
            if symbol.kind in ["class", "function", "variable"]:
                usages["definitions"].append(symbol)
            
            refs = await self.lsp.get_references(symbol)
            for ref in refs:
                # Categorize reference type
                # (simplified logic - real implementation would analyze context)
                if "import" in ref.location or "require" in ref.location:
                    usages["imports"].append(ref)
                else:
                    usages["references"].append(ref)
        
        return usages
    
    async def analyze_dependencies(self, file_path: str) -> Dict[str, Any]:
        """
        Analyze dependencies of a file
        
        Returns:
            Dictionary with imports, exports, and dependency graph
        """
        language = self.lsp._detect_language(file_path)
        if not language:
            return {"error": "Unknown language"}
        
        dependencies = {
            "imports": [],
            "exports": [],
            "internal_deps": [],
            "external_deps": []
        }
        
        # Parse file for imports/exports
        # (simplified - real implementation would use LSP or AST)
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    
                    # Detect imports (simplified for common patterns)
                    if any(keyword in line for keyword in ["import", "require", "use", "include"]):
                        dependencies["imports"].append(line)
                    
                    # Detect exports
                    if any(keyword in line for keyword in ["export", "module.exports", "pub fn", "public class"]):
                        dependencies["exports"].append(line)
        except Exception as e:
            return {"error": str(e)}
        
        return dependencies