from sqlalchemy import Text, Float
from sqlmodel import Field, Column, JSON, String
from typing import Optional, List
from datetime import datetime
from enum import Enum
from app.model.abstract.model import AbstractModel, DefaultTimes
from pydantic import BaseModel


class JobSource(str, Enum):
    """Supported job board sources from JobSpy"""
    LINKEDIN = "linkedin"
    INDEED = "indeed"
    GLASSDOOR = "glassdoor"
    ZIP_RECRUITER = "zip_recruiter"
    GOOGLE = "google"


class ScrapedJob(AbstractModel, DefaultTimes, table=True):
    """
    Scraped job listing model.
    
    Uses url_hash for deduplication across all sessions.
    Jobs are deduplicated globally - if the same job_url is found again,
    it won't create a new record.
    """
    id: int = Field(default=None, primary_key=True)
    
    # Deduplication key - MD5 hash of job_url
    url_hash: str = Field(sa_column=Column(String(32), index=True, unique=True))
    
    # Session tracking (which search found this job)
    session_id: int = Field(index=True, nullable=True)
    
    # Core job info
    title: str = Field(sa_column=Column(String(500)))
    company: str = Field(sa_column=Column(String(255)))
    location: str = Field(default="", sa_column=Column(String(255)))
    job_url: str = Field(sa_column=Column(String(1000)))
    job_url_direct: str = Field(default="", sa_column=Column(String(1000)))  # Direct apply link
    
    # Source info
    source: str = Field(sa_column=Column(String(50)))  # JobSource enum value
    
    # Job details
    description: str = Field(default="", sa_column=Column(Text))
    job_type: str = Field(default="", sa_column=Column(String(50)))  # fulltime, parttime, contract, internship
    is_remote: bool = Field(default=False)
    
    # Salary info
    salary_min: Optional[float] = Field(default=None, sa_column=Column(Float))
    salary_max: Optional[float] = Field(default=None, sa_column=Column(Float))
    salary_currency: str = Field(default="USD", sa_column=Column(String(10)))
    salary_interval: str = Field(default="yearly", sa_column=Column(String(20)))  # yearly, hourly, etc.
    
    # Dates
    posted_date: Optional[datetime] = Field(default=None)
    
    # Additional metadata
    company_url: str = Field(default="", sa_column=Column(String(500)))
    company_logo: str = Field(default="", sa_column=Column(String(500)))
    emails: List[str] = Field(default=[], sa_column=Column(JSON))
    
    # Extracted requirements (populated by analyzer agent)
    required_skills: List[str] = Field(default=[], sa_column=Column(JSON))
    preferred_skills: List[str] = Field(default=[], sa_column=Column(JSON))
    experience_years: Optional[int] = Field(default=None)
    education_requirement: str = Field(default="", sa_column=Column(String(255)))


class ScrapedJobIn(BaseModel):
    url_hash: str
    session_id: Optional[int] = None
    title: str
    company: str
    location: str = ""
    job_url: str
    job_url_direct: str = ""
    source: str
    description: str = ""
    job_type: str = ""
    is_remote: bool = False
    salary_min: Optional[float] = None
    salary_max: Optional[float] = None
    salary_currency: str = "USD"
    salary_interval: str = "yearly"
    posted_date: Optional[datetime] = None
    company_url: str = ""
    company_logo: str = ""
    emails: List[str] = []
    required_skills: List[str] = []
    preferred_skills: List[str] = []
    experience_years: Optional[int] = None
    education_requirement: str = ""


class ScrapedJobOut(BaseModel):
    id: int
    url_hash: str
    session_id: Optional[int]
    title: str
    company: str
    location: str
    job_url: str
    job_url_direct: str
    source: str
    description: str
    job_type: str
    is_remote: bool
    salary_min: Optional[float]
    salary_max: Optional[float]
    salary_currency: str
    salary_interval: str
    posted_date: Optional[datetime]
    company_url: str
    company_logo: str
    required_skills: List[str]
    preferred_skills: List[str]
    experience_years: Optional[int]
    education_requirement: str

    class Config:
        from_attributes = True
