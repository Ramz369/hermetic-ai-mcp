"""
LSP Protocol Implementation - Proper JSON-RPC communication with Language Servers
Complete implementation without placeholders or simplifications
"""
import json
import asyncio
import uuid
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, asdict
import logging

logger = logging.getLogger(__name__)


@dataclass
class LSPMessage:
    """Represents an LSP message"""
    jsonrpc: str = "2.0"
    id: Optional[int] = None
    method: Optional[str] = None
    params: Optional[Dict[str, Any]] = None
    result: Optional[Any] = None
    error: Optional[Dict[str, Any]] = None
    
    def to_json(self) -> str:
        """Convert to JSON-RPC format"""
        data = {"jsonrpc": self.jsonrpc}
        if self.id is not None:
            data["id"] = self.id
        if self.method:
            data["method"] = self.method
        if self.params:
            data["params"] = self.params
        if self.result is not None:
            data["result"] = self.result
        if self.error:
            data["error"] = self.error
        return json.dumps(data)
    
    @classmethod
    def from_json(cls, json_str: str) -> 'LSPMessage':
        """Parse from JSON-RPC format"""
        data = json.loads(json_str)
        return cls(**data)


class LSPProtocol:
    """
    Handles LSP protocol communication with language servers
    Implements proper JSON-RPC 2.0 protocol for LSP
    """
    
    def __init__(self, process):
        """
        Initialize LSP protocol handler
        
        Args:
            process: subprocess.Popen instance of language server
        """
        self.process = process
        self.request_id = 0
        self.pending_requests = {}
        self.notification_handlers = {}
        self.reader_task = None
        self.initialized = False
        
    async def start(self):
        """Start the protocol handler"""
        # Start reading responses
        self.reader_task = asyncio.create_task(self._read_loop())
        
    async def stop(self):
        """Stop the protocol handler"""
        if self.reader_task:
            self.reader_task.cancel()
            try:
                await self.reader_task
            except asyncio.CancelledError:
                pass
    
    async def _read_loop(self):
        """Continuously read responses from language server"""
        while True:
            try:
                # Read header
                headers = {}
                while True:
                    line = await asyncio.create_task(
                        asyncio.to_thread(self.process.stdout.readline)
                    )
                    if not line:
                        return  # Process ended
                    
                    line = line.decode('utf-8').strip()
                    if not line:
                        break  # End of headers
                    
                    if ':' in line:
                        key, value = line.split(':', 1)
                        headers[key.strip()] = value.strip()
                
                # Read content
                if 'Content-Length' in headers:
                    content_length = int(headers['Content-Length'])
                    content = await asyncio.create_task(
                        asyncio.to_thread(self.process.stdout.read, content_length)
                    )
                    content = content.decode('utf-8')
                    
                    # Parse message
                    message = LSPMessage.from_json(content)
                    await self._handle_message(message)
                    
            except Exception as e:
                logger.error(f"Error reading LSP response: {e}")
    
    async def _handle_message(self, message: LSPMessage):
        """Handle incoming LSP message"""
        # Response to a request
        if message.id is not None and message.id in self.pending_requests:
            future = self.pending_requests.pop(message.id)
            if message.error:
                future.set_exception(Exception(message.error.get('message', 'Unknown error')))
            else:
                future.set_result(message.result)
        
        # Notification
        elif message.method and not message.id:
            if message.method in self.notification_handlers:
                handler = self.notification_handlers[message.method]
                asyncio.create_task(handler(message.params))
    
    async def send_request(self, method: str, params: Dict[str, Any]) -> Any:
        """
        Send a request to the language server and wait for response
        
        Args:
            method: LSP method name
            params: Method parameters
            
        Returns:
            Response result
        """
        self.request_id += 1
        request_id = self.request_id
        
        # Create request message
        message = LSPMessage(
            id=request_id,
            method=method,
            params=params
        )
        
        # Create future for response
        future = asyncio.get_event_loop().create_future()
        self.pending_requests[request_id] = future
        
        # Send request
        await self._send_message(message)
        
        # Wait for response
        try:
            result = await asyncio.wait_for(future, timeout=30.0)
            return result
        except asyncio.TimeoutError:
            self.pending_requests.pop(request_id, None)
            raise TimeoutError(f"LSP request '{method}' timed out")
    
    async def send_notification(self, method: str, params: Dict[str, Any]):
        """
        Send a notification (no response expected)
        
        Args:
            method: LSP method name
            params: Method parameters
        """
        message = LSPMessage(
            method=method,
            params=params
        )
        await self._send_message(message)
    
    async def _send_message(self, message: LSPMessage):
        """Send a message to the language server"""
        content = message.to_json()
        content_bytes = content.encode('utf-8')
        
        # Create LSP header
        header = f"Content-Length: {len(content_bytes)}\r\n\r\n"
        header_bytes = header.encode('utf-8')
        
        # Send header + content
        self.process.stdin.write(header_bytes + content_bytes)
        self.process.stdin.flush()
    
    def on_notification(self, method: str, handler: Callable):
        """Register a notification handler"""
        self.notification_handlers[method] = handler
    
    async def initialize(self, root_uri: str, capabilities: Dict[str, Any]) -> Dict[str, Any]:
        """
        Initialize the language server
        
        Args:
            root_uri: Root URI of the workspace
            capabilities: Client capabilities
            
        Returns:
            Server capabilities
        """
        result = await self.send_request("initialize", {
            "processId": None,
            "rootUri": root_uri,
            "capabilities": capabilities,
            "initializationOptions": {},
            "trace": "verbose"
        })
        
        # Send initialized notification
        await self.send_notification("initialized", {})
        
        self.initialized = True
        return result
    
    async def shutdown(self):
        """Shutdown the language server"""
        if self.initialized:
            await self.send_request("shutdown", {})
            await self.send_notification("exit", {})
            self.initialized = False
    
    async def text_document_did_open(self, uri: str, language_id: str, version: int, text: str):
        """Notify that a document was opened"""
        await self.send_notification("textDocument/didOpen", {
            "textDocument": {
                "uri": uri,
                "languageId": language_id,
                "version": version,
                "text": text
            }
        })
    
    async def text_document_did_change(self, uri: str, version: int, changes: List[Dict]):
        """Notify that a document changed"""
        await self.send_notification("textDocument/didChange", {
            "textDocument": {
                "uri": uri,
                "version": version
            },
            "contentChanges": changes
        })
    
    async def text_document_did_close(self, uri: str):
        """Notify that a document was closed"""
        await self.send_notification("textDocument/didClose", {
            "textDocument": {
                "uri": uri
            }
        })
    
    async def text_document_definition(self, uri: str, line: int, character: int) -> List[Dict]:
        """Get definition of symbol at position"""
        result = await self.send_request("textDocument/definition", {
            "textDocument": {"uri": uri},
            "position": {"line": line, "character": character}
        })
        return result if isinstance(result, list) else [result] if result else []
    
    async def text_document_references(self, uri: str, line: int, character: int, 
                                      include_declaration: bool = True) -> List[Dict]:
        """Get references to symbol at position"""
        result = await self.send_request("textDocument/references", {
            "textDocument": {"uri": uri},
            "position": {"line": line, "character": character},
            "context": {"includeDeclaration": include_declaration}
        })
        return result or []
    
    async def text_document_document_symbol(self, uri: str) -> List[Dict]:
        """Get all symbols in document"""
        result = await self.send_request("textDocument/documentSymbol", {
            "textDocument": {"uri": uri}
        })
        return result or []
    
    async def workspace_symbol(self, query: str) -> List[Dict]:
        """Search for symbols in workspace"""
        result = await self.send_request("workspace/symbol", {
            "query": query
        })
        return result or []
    
    async def text_document_hover(self, uri: str, line: int, character: int) -> Optional[Dict]:
        """Get hover information at position"""
        result = await self.send_request("textDocument/hover", {
            "textDocument": {"uri": uri},
            "position": {"line": line, "character": character}
        })
        return result
    
    async def text_document_completion(self, uri: str, line: int, character: int) -> List[Dict]:
        """Get completion suggestions at position"""
        result = await self.send_request("textDocument/completion", {
            "textDocument": {"uri": uri},
            "position": {"line": line, "character": character}
        })
        
        # Result can be a list or CompletionList object
        if isinstance(result, dict) and 'items' in result:
            return result['items']
        elif isinstance(result, list):
            return result
        return []
    
    async def text_document_signature_help(self, uri: str, line: int, character: int) -> Optional[Dict]:
        """Get signature help at position"""
        result = await self.send_request("textDocument/signatureHelp", {
            "textDocument": {"uri": uri},
            "position": {"line": line, "character": character}
        })
        return result
    
    async def text_document_formatting(self, uri: str, tab_size: int = 4, 
                                      insert_spaces: bool = True) -> List[Dict]:
        """Format entire document"""
        result = await self.send_request("textDocument/formatting", {
            "textDocument": {"uri": uri},
            "options": {
                "tabSize": tab_size,
                "insertSpaces": insert_spaces
            }
        })
        return result or []
    
    async def text_document_rename(self, uri: str, line: int, character: int, 
                                  new_name: str) -> Optional[Dict]:
        """Rename symbol at position"""
        result = await self.send_request("textDocument/rename", {
            "textDocument": {"uri": uri},
            "position": {"line": line, "character": character},
            "newName": new_name
        })
        return result
    
    def format_message(self, message: Dict[str, Any]) -> str:
        """Format a message for LSP protocol (compatibility method)"""
        lsp_msg = LSPMessage(**message)
        content = lsp_msg.to_json()
        content_bytes = content.encode('utf-8')
        header = f"Content-Length: {len(content_bytes)}\r\n\r\n"
        return header + content
    
    def parse_message(self, raw_message: str) -> Dict[str, Any]:
        """Parse an LSP protocol message (compatibility method)"""
        # Find the end of headers
        header_end = raw_message.find('\r\n\r\n')
        if header_end == -1:
            raise ValueError("Invalid LSP message format")
        
        # Extract content
        content_start = header_end + 4
        content = raw_message[content_start:]
        
        # Parse JSON content
        return json.loads(content)