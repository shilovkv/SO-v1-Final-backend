from sqlalchemy import Column,Integer,String,Float,Text,DateTime,Boolean
from sqlalchemy.sql import func
from .db import Base
class Agent(Base):
    __tablename__="agents"
    id=Column(Integer,primary_key=True); name=Column(String); type=Column(String); role=Column(Text); status=Column(String,default="active"); created_at=Column(DateTime(timezone=True),server_default=func.now())
class Task(Base):
    __tablename__="tasks"
    id=Column(Integer,primary_key=True); title=Column(String); owner=Column(String); layer=Column(String); status=Column(String,default="queued"); value=Column(Float,default=0); progress=Column(Integer,default=0); created_at=Column(DateTime(timezone=True),server_default=func.now())
class Candidate(Base):
    __tablename__="candidates"
    id=Column(Integer,primary_key=True); phone=Column(String,index=True); name=Column(String,nullable=True); city=Column(String,nullable=True); age=Column(Integer,nullable=True); source=Column(String,default="unknown"); external_id=Column(String,nullable=True); bitrix_status=Column(String,nullable=True); avito_chat_id=Column(String,nullable=True); avito_vacancy_id=Column(String,nullable=True); avito_response_id=Column(String,nullable=True); last_dialogue=Column(Text,nullable=True); consent=Column(Boolean,default=False); do_not_contact=Column(Boolean,default=False); segment=Column(String,default="Unsegmented"); status=Column(String,default="New"); next_action=Column(String,default="segment"); risk_flag=Column(String,nullable=True); created_at=Column(DateTime(timezone=True),server_default=func.now())
class Campaign(Base):
    __tablename__="campaigns"
    id=Column(Integer,primary_key=True); name=Column(String); channel=Column(String,default="SMS"); size=Column(Integer,default=0); status=Column(String,default="prepared"); message=Column(Text); created_at=Column(DateTime(timezone=True),server_default=func.now())
class Memory(Base):
    __tablename__="memory"
    id=Column(Integer,primary_key=True); event_type=Column(String); content=Column(Text); created_at=Column(DateTime(timezone=True),server_default=func.now())
