from datetime import datetime
from typing import List, Optional, Dict, Any
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Text, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from pydantic import BaseModel, Field

# SQLAlchemy models
Base = declarative_base()

class ProfileModel(Base):
    __tablename__ = "profiles"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    provider = Column(String, default="custom")  # 'ollama', 'openai', 'anthropic', 'custom'
    url = Column(String)
    model_name = Column(String)
    token_size = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    chats = relationship("ChatModel", back_populates="profile", cascade="all, delete-orphan")

class ChatModel(Base):
    __tablename__ = "chats"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, default="New Chat")
    profile_id = Column(Integer, ForeignKey("profiles.id"))
    created_at = Column(DateTime, default=datetime.utcnow)
    
    profile = relationship("ProfileModel", back_populates="chats")
    messages = relationship("MessageModel", back_populates="chat", cascade="all, delete-orphan")

class MessageModel(Base):
    __tablename__ = "messages"
    
    id = Column(Integer, primary_key=True, index=True)
    chat_id = Column(Integer, ForeignKey("chats.id"))
    role = Column(String)  # "user" or "assistant"
    content = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    chat = relationship("ChatModel", back_populates="messages")

# Database setup
SQLALCHEMY_DATABASE_URL = "sqlite:///./localchat.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create tables
Base.metadata.create_all(bind=engine)

# Pydantic models for API
class ProfileBase(BaseModel):
    name: str
    provider: str = "custom"  # 'ollama', 'openai', 'anthropic', 'custom'
    url: str
    model_name: str
    token_size: int

class ProfileCreate(ProfileBase):
    pass

class Profile(ProfileBase):
    id: int
    created_at: datetime
    
    class Config:
        orm_mode = True
        from_attributes = True

class MessageBase(BaseModel):
    role: str
    content: str

class MessageCreate(MessageBase):
    pass

class Message(MessageBase):
    id: int
    chat_id: int
    created_at: datetime
    
    class Config:
        orm_mode = True
        from_attributes = True

class ChatBase(BaseModel):
    title: str
    profile_id: int

class ChatCreate(ChatBase):
    pass

class Chat(ChatBase):
    id: int
    created_at: datetime
    messages: List[Message] = []
    
    class Config:
        orm_mode = True
        from_attributes = True

class ModelRequest(BaseModel):
    model: str
    messages: List[Dict[str, str]]
    max_tokens: Optional[int] = None
