from sqlmodel import Field, Column, JSON, String
from typing import Optional, List
from enum import IntEnum
from app.model.abstract.model import AbstractModel, DefaultTimes
from pydantic import BaseModel


class SessionStatus(IntEnum):
    """Job hunt session status"""
    CREATED = 1
    SCRAPING = 2
    ANALYZING = 3
    TAILORING = 4
    COMPLETED = 5
    FAILED = 6


class JobHuntSession(AbstractModel, DefaultTimes, table=True):
    """
    Job hunt session model.
    
    Tracks a complete job hunting workflow from search to tailored resumes.
    Links user's resume with search criteria and tracks progress.
    """
    id: int = Field(default=None, primary_key=True)
    
    # User and project context
    user_id: int = Field(index=True)
    project_id: str = Field(sa_column=Column(String(64), index=True))
    task_id: str = Field(sa_column=Column(String(64), index=True))
    
    # Resume being used
    resume_id: int = Field(index=True)
    
    # Search criteria
    search_criteria: dict = Field(default={}, sa_column=Column(JSON))
    # Example: {
    #   "search_terms": ["software engineer", "python developer"],
    #   "locations": ["San Francisco, CA", "Remote"],
    #   "job_types": ["fulltime"],
    #   "salary_min": 100000,
    #   "is_remote": True,
    #   "sites": ["linkedin", "indeed"]
    # }
    
    # Progress tracking
    status: int = Field(default=SessionStatus.CREATED.value)
    status_message: str = Field(default="", sa_column=Column(String(500)))
    
    # Results
    jobs_found_count: int = Field(default=0)
    jobs_analyzed_count: int = Field(default=0)
    jobs_tailored_count: int = Field(default=0)
    
    # IDs of related records (for quick lookup)
    job_ids: List[int] = Field(default=[], sa_column=Column(JSON))
    analysis_ids: List[int] = Field(default=[], sa_column=Column(JSON))
    tailored_resume_ids: List[int] = Field(default=[], sa_column=Column(JSON))
    
    # Configuration
    auto_analyze: bool = Field(default=True)  # Automatically analyze found jobs
    auto_tailor_top_n: int = Field(default=3)  # Auto-tailor top N matches
    min_score_threshold: float = Field(default=60.0)  # Minimum score to consider for tailoring


class JobHuntSessionIn(BaseModel):
    user_id: int
    project_id: str
    task_id: str
    resume_id: int
    search_criteria: dict = {}
    auto_analyze: bool = True
    auto_tailor_top_n: int = 3
    min_score_threshold: float = 60.0


class JobHuntSessionOut(BaseModel):
    id: int
    user_id: int
    project_id: str
    task_id: str
    resume_id: int
    search_criteria: dict
    status: int
    status_message: str
    jobs_found_count: int
    jobs_analyzed_count: int
    jobs_tailored_count: int
    job_ids: List[int]
    analysis_ids: List[int]
    tailored_resume_ids: List[int]
    auto_analyze: bool
    auto_tailor_top_n: int
    min_score_threshold: float

    class Config:
        from_attributes = True
