"""
Core data types for chatbot - platform-agnostic message and thread structures.

The internal ChatMessage/ChatThread format is the canonical representation.
Conversions to/from vendor-specific formats are handled by providers.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List, Dict, Any
from datetime import datetime
import uuid


class MessageRole(Enum):
    """Role of a message in the conversation."""
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


@dataclass
class ChatMessage:
    """
    A single message in a chat thread.
    
    This is the canonical internal representation. Provider adapters convert
    to/from this format when communicating with vendor APIs.
    
    Attributes:
        role: The role of the message sender
        content: The text content of the message
        id: Unique identifier for the message
        timestamp: When the message was created
        model: The model that generated this message (for assistant messages)
        provider: The provider used (for assistant messages)
        metadata: Additional vendor-specific metadata (preserved but not interpreted)
    """
    role: MessageRole
    content: str
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=datetime.now)
    model: Optional[str] = None
    provider: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'role': self.role.value,
            'content': self.content,
            'id': self.id,
            'timestamp': self.timestamp.isoformat(),
            'model': self.model,
            'provider': self.provider,
            'metadata': self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ChatMessage':
        """Create from dictionary."""
        return cls(
            role=MessageRole(data['role']),
            content=data['content'],
            id=data.get('id', str(uuid.uuid4())),
            timestamp=datetime.fromisoformat(data['timestamp']) if 'timestamp' in data else datetime.now(),
            model=data.get('model'),
            provider=data.get('provider'),
            metadata=data.get('metadata', {}),
        )
    
    # Convenience constructors
    @classmethod
    def system(cls, content: str) -> 'ChatMessage':
        """Create a system message."""
        return cls(role=MessageRole.SYSTEM, content=content)
    
    @classmethod
    def user(cls, content: str) -> 'ChatMessage':
        """Create a user message."""
        return cls(role=MessageRole.USER, content=content)
    
    @classmethod
    def assistant(cls, content: str, model: Optional[str] = None, 
                  provider: Optional[str] = None) -> 'ChatMessage':
        """Create an assistant message."""
        return cls(role=MessageRole.ASSISTANT, content=content, 
                   model=model, provider=provider)


@dataclass
class ChatThread:
    """
    A single conversation thread containing multiple messages.
    
    Manages the chat history and provides methods for adding messages
    and converting to vendor-specific formats.
    """
    messages: List[ChatMessage] = field(default_factory=list)
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(default_factory=datetime.now)
    title: Optional[str] = None
    
    def add_message(self, message: ChatMessage) -> None:
        """Add a message to the thread."""
        self.messages.append(message)
    
    def add_system(self, content: str) -> ChatMessage:
        """Add a system message and return it."""
        msg = ChatMessage.system(content)
        self.add_message(msg)
        return msg
    
    def add_user(self, content: str) -> ChatMessage:
        """Add a user message and return it."""
        msg = ChatMessage.user(content)
        self.add_message(msg)
        return msg
    
    def add_assistant(self, content: str, model: Optional[str] = None,
                      provider: Optional[str] = None) -> ChatMessage:
        """Add an assistant message and return it."""
        msg = ChatMessage.assistant(content, model=model, provider=provider)
        self.add_message(msg)
        return msg
    
    def get_system_message(self) -> Optional[ChatMessage]:
        """Get the system message if present."""
        for msg in self.messages:
            if msg.role == MessageRole.SYSTEM:
                return msg
        return None
    
    def get_conversation_messages(self) -> List[ChatMessage]:
        """Get all non-system messages."""
        return [m for m in self.messages if m.role != MessageRole.SYSTEM]
    
    def clear(self) -> None:
        """Clear all messages except system message."""
        system_msg = self.get_system_message()
        self.messages.clear()
        if system_msg:
            self.messages.append(system_msg)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'id': self.id,
            'created_at': self.created_at.isoformat(),
            'title': self.title,
            'messages': [m.to_dict() for m in self.messages],
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ChatThread':
        """Create from dictionary."""
        thread = cls(
            id=data.get('id', str(uuid.uuid4())),
            created_at=datetime.fromisoformat(data['created_at']) if 'created_at' in data else datetime.now(),
            title=data.get('title'),
        )
        for msg_data in data.get('messages', []):
            thread.add_message(ChatMessage.from_dict(msg_data))
        return thread
    
    # ─────────────────────────────────────────────────────────────────────
    # Vendor format conversions
    # ─────────────────────────────────────────────────────────────────────
    
    def to_openai_messages(self) -> List[Dict[str, str]]:
        """
        Convert to OpenAI API message format.
        
        Format: [{"role": "system"|"user"|"assistant", "content": "..."}]
        """
        return [
            {"role": m.role.value, "content": m.content}
            for m in self.messages
        ]
    
    def to_claude_messages(self) -> tuple:
        """
        Convert to Claude/Anthropic API message format.
        
        Claude separates system prompt from messages.
        Returns: (system_prompt: str | None, messages: List[Dict])
        
        Format: messages = [{"role": "user"|"assistant", "content": "..."}]
        """
        system_prompt = None
        messages = []
        
        for m in self.messages:
            if m.role == MessageRole.SYSTEM:
                system_prompt = m.content
            else:
                messages.append({
                    "role": m.role.value,
                    "content": m.content
                })
        
        return system_prompt, messages
    
    def to_gemini_contents(self) -> tuple:
        """
        Convert to Gemini API contents format.
        
        Gemini uses 'user' and 'model' roles, and separates system instruction.
        Returns: (system_instruction: str | None, contents: List[Dict])
        
        Format: contents = [{"role": "user"|"model", "parts": [{"text": "..."}]}]
        """
        system_instruction = None
        contents = []
        
        for m in self.messages:
            if m.role == MessageRole.SYSTEM:
                system_instruction = m.content
            else:
                gemini_role = "model" if m.role == MessageRole.ASSISTANT else "user"
                contents.append({
                    "role": gemini_role,
                    "parts": [{"text": m.content}]
                })
        
        return system_instruction, contents
    
    # ─────────────────────────────────────────────────────────────────────
    # Import from vendor formats
    # ─────────────────────────────────────────────────────────────────────
    
    @classmethod
    def from_openai_messages(cls, messages: List[Dict[str, str]], 
                             model: Optional[str] = None,
                             provider: Optional[str] = None) -> 'ChatThread':
        """
        Create thread from OpenAI message format.
        
        Args:
            messages: List of {"role": "...", "content": "..."} dicts
            model: Model name to tag assistant messages with
            provider: Provider name to tag assistant messages with
        """
        thread = cls()
        for m in messages:
            role = MessageRole(m['role'])
            if role == MessageRole.ASSISTANT:
                thread.add_assistant(m['content'], model=model, provider=provider)
            elif role == MessageRole.USER:
                thread.add_user(m['content'])
            elif role == MessageRole.SYSTEM:
                thread.add_system(m['content'])
        return thread
    
    @classmethod
    def from_claude_messages(cls, system_prompt: Optional[str],
                             messages: List[Dict[str, str]],
                             model: Optional[str] = None,
                             provider: Optional[str] = None) -> 'ChatThread':
        """
        Create thread from Claude message format.
        
        Args:
            system_prompt: The system instruction
            messages: List of {"role": "user"|"assistant", "content": "..."} dicts
            model: Model name to tag assistant messages with
            provider: Provider name to tag assistant messages with
        """
        thread = cls()
        if system_prompt:
            thread.add_system(system_prompt)
        
        for m in messages:
            role = MessageRole(m['role'])
            if role == MessageRole.ASSISTANT:
                thread.add_assistant(m['content'], model=model, provider=provider)
            else:
                thread.add_user(m['content'])
        return thread
    
    @classmethod
    def from_gemini_contents(cls, system_instruction: Optional[str],
                             contents: List[Dict],
                             model: Optional[str] = None,
                             provider: Optional[str] = None) -> 'ChatThread':
        """
        Create thread from Gemini content format.
        
        Args:
            system_instruction: The system instruction
            contents: List of {"role": "user"|"model", "parts": [{"text": "..."}]} dicts
            model: Model name to tag assistant messages with
            provider: Provider name to tag assistant messages with
        """
        thread = cls()
        if system_instruction:
            thread.add_system(system_instruction)
        
        for c in contents:
            role = c.get('role', 'user')
            # Extract text from parts
            text_parts = []
            for part in c.get('parts', []):
                if isinstance(part, dict) and 'text' in part:
                    text_parts.append(part['text'])
                elif isinstance(part, str):
                    text_parts.append(part)
            content = '\n'.join(text_parts)
            
            if role == 'model':
                thread.add_assistant(content, model=model, provider=provider)
            else:
                thread.add_user(content)
        
        return thread
