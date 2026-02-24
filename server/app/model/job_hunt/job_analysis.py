from sqlalchemy import Text, Float
from sqlmodel import Field, Column, JSON, String
from typing import Optional, List
from app.model.abstract.model import AbstractModel, DefaultTimes
from pydantic import BaseModel


class JobAnalysis(AbstractModel, DefaultTimes, table=True):
    """
    Job-resume match analysis model.
    
    Stores the analysis results comparing a user's resume against a job posting.
    Includes scoring breakdown, skill gaps, and recommendations.
    """
    id: int = Field(default=None, primary_key=True)
    
    # Foreign keys
    resume_id: int = Field(index=True)
    job_id: int = Field(index=True)
    user_id: int = Field(index=True)
    
    # Scores (0-100)
    overall_score: float = Field(sa_column=Column(Float))
    skill_match_score: float = Field(default=0, sa_column=Column(Float))  # 40% weight
    experience_match_score: float = Field(default=0, sa_column=Column(Float))  # 30% weight
    education_match_score: float = Field(default=0, sa_column=Column(Float))  # 15% weight
    keyword_match_score: float = Field(default=0, sa_column=Column(Float))  # 15% weight
    
    # Match details
    matching_skills: List[str] = Field(default=[], sa_column=Column(JSON))
    missing_skills: List[str] = Field(default=[], sa_column=Column(JSON))
    keyword_overlap: List[str] = Field(default=[], sa_column=Column(JSON))
    
    # Qualitative analysis
    strengths: List[str] = Field(default=[], sa_column=Column(JSON))
    weaknesses: List[str] = Field(default=[], sa_column=Column(JSON))
    recommendations: List[str] = Field(default=[], sa_column=Column(JSON))
    
    # Fit assessment
    fit_level: str = Field(default="", sa_column=Column(String(50)))  # excellent, good, fair, poor
    interview_likelihood: str = Field(default="", sa_column=Column(String(50)))  # high, medium, low
    
    # Full analysis report (markdown)
    analysis_report: str = Field(default="", sa_column=Column(Text))


class JobAnalysisIn(BaseModel):
    resume_id: int
    job_id: int
    user_id: int
    overall_score: float
    skill_match_score: float = 0
    experience_match_score: float = 0
    education_match_score: float = 0
    keyword_match_score: float = 0
    matching_skills: List[str] = []
    missing_skills: List[str] = []
    keyword_overlap: List[str] = []
    strengths: List[str] = []
    weaknesses: List[str] = []
    recommendations: List[str] = []
    fit_level: str = ""
    interview_likelihood: str = ""
    analysis_report: str = ""


class JobAnalysisOut(BaseModel):
    id: int
    resume_id: int
    job_id: int
    user_id: int
    overall_score: float
    skill_match_score: float
    experience_match_score: float
    education_match_score: float
    keyword_match_score: float
    matching_skills: List[str]
    missing_skills: List[str]
    keyword_overlap: List[str]
    strengths: List[str]
    weaknesses: List[str]
    recommendations: List[str]
    fit_level: str
    interview_likelihood: str
    analysis_report: str

    class Config:
        from_attributes = True
