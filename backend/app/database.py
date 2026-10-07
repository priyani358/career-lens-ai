from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, Text, ForeignKey, DateTime, JSON
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from . import config

engine = create_engine(config.DB_URL, connect_args={"check_same_thread": False} if config.DB_URL.startswith("sqlite") else {})
SessionLocal = sessionmaker(bind=engine, autoflush=False)
Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    email = Column(String, unique=True, index=True)
    pw_hash = Column(String)
    profile = relationship("Profile", uselist=False, back_populates="user")

class Profile(Base):
    __tablename__ = "profiles"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True)
    data = Column(JSON, default=dict)
    saved_careers = Column(JSON, default=list)
    user = relationship("User", back_populates="profile")

class Assessment(Base):
    __tablename__ = "assessments"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    result = Column(JSON)
    created = Column(DateTime, default=datetime.utcnow)

class Roadmap(Base):
    __tablename__ = "roadmaps"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    career_id = Column(String)
    data = Column(JSON)  # phases -> items, each with "done" flag (the progress record)

class Conversation(Base):
    __tablename__ = "conversations"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    title = Column(String, default="New conversation")
    messages = relationship("Message", order_by="Message.id")

class Message(Base):
    __tablename__ = "messages"
    id = Column(Integer, primary_key=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"))
    role = Column(String)
    content = Column(Text)

class Selection(Base):
    """The currently selected career used by the connected career workspace."""
    __tablename__ = "selections"
    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    career_id = Column(String)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
