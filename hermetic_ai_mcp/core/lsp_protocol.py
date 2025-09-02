"""
LSP Protocol Implementation
Language Server Protocol handlers and message types
"""
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass
from enum import Enum
import json


class MessageType(Enum):
    """LSP message types"""
    REQUEST = "request"
    RESPONSE = "response"
    NOTIFICATION = "notification"


class LSPErrorCode(Enum):
    """LSP error codes"""
    PARSE_ERROR = -32700
    INVALID_REQUEST = -32600
    METHOD_NOT_FOUND = -32601
    INVALID_PARAMS = -32602
    INTERNAL_ERROR = -32603
    SERVER_ERROR_START = -32099
    SERVER_ERROR_END = -32000
    SERVER_NOT_INITIALIZED = -32002
    UNKNOWN_ERROR_CODE = -32001


@dataclass
class Position:
    """Position in a text document"""
    line: int
    character: int


@dataclass
class Range:
    """Range in a text document"""
    start: Position
    end: Position


@dataclass
class Location:
    """Location in a text document"""
    uri: str
    range: Range


@dataclass
class Diagnostic:
    """Diagnostic information"""
    range: Range
    severity: int
    code: Optional[Union[int, str]] = None
    source: Optional[str] = None
    message: str = ""


@dataclass
class TextDocumentIdentifier:
    """Text document identifier"""
    uri: str


@dataclass
class TextDocumentItem:
    """Text document item"""
    uri: str
    languageId: str
    version: int
    text: str


@dataclass
class CompletionItem:
    """Completion item"""
    label: str
    kind: Optional[int] = None
    detail: Optional[str] = None
    documentation: Optional[str] = None
    insertText: Optional[str] = None


class LSPMessage:
    """Base LSP message"""
    
    def __init__(self, jsonrpc: str = "2.0"):
        self.jsonrpc = jsonrpc
    
    def to_json(self) -> str:
        """Convert to JSON string"""
        return json.dumps(self.__dict__)


class LSPRequest(LSPMessage):
    """LSP request message"""
    
    def __init__(self, id: Union[int, str], method: str, params: Optional[Dict[str, Any]] = None):
        super().__init__()
        self.id = id
        self.method = method
        if params:
            self.params = params


class LSPResponse(LSPMessage):
    """LSP response message"""
    
    def __init__(self, id: Union[int, str], result: Optional[Any] = None, error: Optional[Dict[str, Any]] = None):
        super().__init__()
        self.id = id
        if result is not None:
            self.result = result
        if error is not None:
            self.error = error


class LSPNotification(LSPMessage):
    """LSP notification message"""
    
    def __init__(self, method: str, params: Optional[Dict[str, Any]] = None):
        super().__init__()
        self.method = method
        if params:
            self.params = params


class LSPProtocolHandler:
    """Handles LSP protocol messages"""
    
    def __init__(self):
        self.message_id = 0
    
    def next_id(self) -> int:
        """Get next message ID"""
        self.message_id += 1
        return self.message_id
    
    def create_request(self, method: str, params: Optional[Dict[str, Any]] = None) -> LSPRequest:
        """Create an LSP request"""
        return LSPRequest(self.next_id(), method, params)
    
    def create_response(self, id: Union[int, str], result: Optional[Any] = None, error: Optional[Dict[str, Any]] = None) -> LSPResponse:
        """Create an LSP response"""
        return LSPResponse(id, result, error)
    
    def create_notification(self, method: str, params: Optional[Dict[str, Any]] = None) -> LSPNotification:
        """Create an LSP notification"""
        return LSPNotification(method, params)
    
    def parse_message(self, message: str) -> Union[LSPRequest, LSPResponse, LSPNotification]:
        """Parse an LSP message from JSON string"""
        data = json.loads(message)
        
        if "id" in data:
            if "method" in data:
                # Request
                return LSPRequest(data["id"], data["method"], data.get("params"))
            else:
                # Response
                return LSPResponse(data["id"], data.get("result"), data.get("error"))
        else:
            # Notification
            return LSPNotification(data["method"], data.get("params"))
    
    def format_message(self, message: LSPMessage) -> str:
        """Format an LSP message for sending"""
        content = message.to_json()
        header = f"Content-Length: {len(content)}\r\n\r\n"
        return header + content