from sqlalchemy import Text, Float
from sqlmodel import Field, Column, JSON, String
from typing import Optional, List
from enum import Enum
from app.model.abstract.model import AbstractModel, DefaultTimes
from pydantic import BaseModel


class ResumeFormat(str, Enum):
    """Supported export formats"""
    PDF = "pdf"
    DOCX = "docx"
    MARKDOWN = "markdown"


class TailoredResume(AbstractModel, DefaultTimes, table=True):
    """
    Tailored resume model.
    
    Stores resumes that have been optimized for specific job postings.
    Links to the original resume and the target job analysis.
    """
    id: int = Field(default=None, primary_key=True)
    
    # Foreign keys
    analysis_id: int = Field(index=True)  # Links to JobAnalysis
    original_resume_id: int = Field(index=True)  # Links to UserResume
    job_id: int = Field(index=True)  # Links to ScrapedJob
    user_id: int = Field(index=True)
    
    # File storage
    file_path: str = Field(sa_column=Column(String(500)))  # Path to generated file
    format: str = Field(sa_column=Column(String(20)))  # ResumeFormat enum value
    
    # Tailored content
    tailored_content: str = Field(default="", sa_column=Column(Text))  # Markdown/text version
    
    # Optimization tracking
    optimizations_made: List[str] = Field(default=[], sa_column=Column(JSON))  # List of changes made
    keywords_added: List[str] = Field(default=[], sa_column=Column(JSON))  # Keywords incorporated
    
    # Quality scores
    ats_score: float = Field(default=0, sa_column=Column(Float))  # ATS compatibility score (0-100)
    improvement_delta: float = Field(default=0, sa_column=Column(Float))  # Score improvement vs original
    
    # Cover letter (optional)
    cover_letter_path: Optional[str] = Field(default=None, sa_column=Column(String(500)))
    cover_letter_content: str = Field(default="", sa_column=Column(Text))


class TailoredResumeIn(BaseModel):
    analysis_id: int
    original_resume_id: int
    job_id: int
    user_id: int
    file_path: str
    format: str
    tailored_content: str = ""
    optimizations_made: List[str] = []
    keywords_added: List[str] = []
    ats_score: float = 0
    improvement_delta: float = 0
    cover_letter_path: Optional[str] = None
    cover_letter_content: str = ""


class TailoredResumeOut(BaseModel):
    id: int
    analysis_id: int
    original_resume_id: int
    job_id: int
    user_id: int
    file_path: str
    format: str
    tailored_content: str
    optimizations_made: List[str]
    keywords_added: List[str]
    ats_score: float
    improvement_delta: float
    cover_letter_path: Optional[str]
    cover_letter_content: str

    class Config:
        from_attributes = True
