from sqlalchemy import Text
from sqlmodel import Field, Column, JSON, String
from typing import Optional, List
from app.model.abstract.model import AbstractModel, DefaultTimes
from pydantic import BaseModel


class UserResume(AbstractModel, DefaultTimes, table=True):
    """
    User resume model for storing parsed resume data.
    
    Stores both structured resume data (JSON) and raw text for search/analysis.
    File is also stored on disk at file_path for original format preservation.
    """
    id: int = Field(default=None, primary_key=True)
    user_id: int = Field(index=True)
    
    # File storage
    file_path: str = Field(sa_column=Column(String(500)))  # Path to original file
    file_name: str = Field(sa_column=Column(String(255)))  # Original filename
    
    # Parsed resume data
    name: str = Field(default="", sa_column=Column(String(255)))
    email: str = Field(default="", sa_column=Column(String(255)))
    phone: str = Field(default="", sa_column=Column(String(50)))
    summary: str = Field(default="", sa_column=Column(Text))
    
    # Structured data as JSON
    skills: List[str] = Field(default=[], sa_column=Column(JSON))
    experience: List[dict] = Field(default=[], sa_column=Column(JSON))  # [{title, company, duration, bullets}]
    education: List[dict] = Field(default=[], sa_column=Column(JSON))  # [{degree, school, year, gpa}]
    certifications: List[str] = Field(default=[], sa_column=Column(JSON))
    languages: List[str] = Field(default=[], sa_column=Column(JSON))
    
    # Raw text for full-text search and analysis
    raw_text: str = Field(default="", sa_column=Column(Text))


class UserResumeIn(BaseModel):
    user_id: int
    file_path: str
    file_name: str
    name: str = ""
    email: str = ""
    phone: str = ""
    summary: str = ""
    skills: List[str] = []
    experience: List[dict] = []
    education: List[dict] = []
    certifications: List[str] = []
    languages: List[str] = []
    raw_text: str = ""


class UserResumeOut(BaseModel):
    id: int
    user_id: int
    file_path: str
    file_name: str
    name: str
    email: str
    phone: str
    summary: str
    skills: List[str]
    experience: List[dict]
    education: List[dict]
    certifications: List[str]
    languages: List[str]
    raw_text: Optional[str] = None  # Optional to exclude from list responses

    class Config:
        from_attributes = True
