"""
Job Hunt Controller

API endpoints for managing job hunt workflows including:
- User resumes (CRUD)
- Scraped jobs (CRUD + deduplication)
- Job analyses (CRUD + rankings)
- Tailored resumes (CRUD)
- Job hunt sessions (CRUD + status tracking)
"""

from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlmodel import Session, select
from app.component.auth import Auth, auth_must
from app.component.database import session
from app.model.job_hunt.user_resume import UserResume
from app.model.job_hunt.scraped_job import ScrapedJob
from app.model.job_hunt.job_analysis import JobAnalysis
from app.model.job_hunt.tailored_resume import TailoredResume
from app.model.job_hunt.job_hunt_session import JobHuntSession
from utils import traceroot_wrapper as traceroot

logger = traceroot.get_logger("server_job_hunt_controller")

router = APIRouter(tags=["Job Hunt"])


# =============================================================================
# Pydantic Models for Request/Response
# =============================================================================

class UserResumeCreate(BaseModel):
    """Schema for creating a user resume."""
    title: str = Field(..., description="Resume title/name")
    raw_text: str = Field(..., description="Raw text content of the resume")
    full_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    location: Optional[str] = None
    linkedin_url: Optional[str] = None
    portfolio_url: Optional[str] = None
    summary: Optional[str] = None
    skills: List[str] = Field(default_factory=list)
    experience: List[dict] = Field(default_factory=list)
    education: List[dict] = Field(default_factory=list)
    certifications: List[str] = Field(default_factory=list)
    languages: List[str] = Field(default_factory=list)


class UserResumeOut(BaseModel):
    """Schema for user resume output."""
    id: int
    user_id: int
    title: str
    full_name: Optional[str]
    email: Optional[str]
    phone: Optional[str]
    location: Optional[str]
    linkedin_url: Optional[str]
    portfolio_url: Optional[str]
    summary: Optional[str]
    skills: List[str]
    experience: List[dict]
    education: List[dict]
    certifications: List[str]
    languages: List[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ScrapedJobCreate(BaseModel):
    """Schema for creating a scraped job."""
    session_id: int
    url_hash: str
    job_url: str
    site: str
    title: str
    company: str
    location: Optional[str] = None
    description: Optional[str] = None
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    salary_currency: Optional[str] = None
    job_type: Optional[str] = None
    is_remote: bool = False
    date_posted: Optional[datetime] = None
    company_url: Optional[str] = None
    company_logo: Optional[str] = None
    company_industry: Optional[str] = None
    company_description: Optional[str] = None
    requirements: List[str] = Field(default_factory=list)
    benefits: List[str] = Field(default_factory=list)


class ScrapedJobOut(BaseModel):
    """Schema for scraped job output."""
    id: int
    session_id: int
    url_hash: str
    job_url: str
    site: str
    title: str
    company: str
    location: Optional[str]
    description: Optional[str]
    salary_min: Optional[int]
    salary_max: Optional[int]
    salary_currency: Optional[str]
    job_type: Optional[str]
    is_remote: bool
    date_posted: Optional[datetime]
    company_url: Optional[str]
    company_industry: Optional[str]
    requirements: List[str]
    benefits: List[str]
    is_analyzed: bool
    created_at: datetime

    class Config:
        from_attributes = True


class JobAnalysisCreate(BaseModel):
    """Schema for creating a job analysis."""
    session_id: int
    job_id: int
    resume_id: int
    overall_score: float
    skill_match_score: float
    experience_match_score: float
    education_match_score: float
    keyword_overlap_score: float
    matching_skills: List[str] = Field(default_factory=list)
    missing_skills: List[str] = Field(default_factory=list)
    experience_gaps: List[str] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)
    fit_level: str = Field(default="fair", description="excellent, good, fair, poor")
    analysis_report: Optional[str] = None


class JobAnalysisOut(BaseModel):
    """Schema for job analysis output."""
    id: int
    session_id: int
    job_id: int
    resume_id: int
    overall_score: float
    skill_match_score: float
    experience_match_score: float
    education_match_score: float
    keyword_overlap_score: float
    matching_skills: List[str]
    missing_skills: List[str]
    experience_gaps: List[str]
    recommendations: List[str]
    fit_level: str
    analysis_report: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class TailoredResumeCreate(BaseModel):
    """Schema for creating a tailored resume."""
    session_id: int
    analysis_id: int
    job_id: int
    resume_id: int
    tailored_content: str
    ats_score: Optional[float] = None
    keywords_added: List[str] = Field(default_factory=list)
    sections_modified: List[str] = Field(default_factory=list)
    cover_letter: Optional[str] = None
    pdf_path: Optional[str] = None
    docx_path: Optional[str] = None


class TailoredResumeOut(BaseModel):
    """Schema for tailored resume output."""
    id: int
    session_id: int
    analysis_id: int
    job_id: int
    resume_id: int
    tailored_content: str
    ats_score: Optional[float]
    keywords_added: List[str]
    sections_modified: List[str]
    cover_letter: Optional[str]
    pdf_path: Optional[str]
    docx_path: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class JobHuntSessionCreate(BaseModel):
    """Schema for creating a job hunt session."""
    title: str
    search_criteria: dict = Field(default_factory=dict)
    resume_id: Optional[int] = None


class JobHuntSessionOut(BaseModel):
    """Schema for job hunt session output."""
    id: int
    user_id: int
    resume_id: Optional[int]
    title: str
    search_criteria: dict
    status: str
    jobs_found: int
    jobs_analyzed: int
    resumes_tailored: int
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class JobHashesResponse(BaseModel):
    """Schema for job URL hashes response (used for deduplication)."""
    hashes: List[str]
    count: int


class SessionStatusUpdate(BaseModel):
    """Schema for updating session status."""
    status: str = Field(..., description="pending, running, completed, failed, cancelled")


# =============================================================================
# User Resume Endpoints
# =============================================================================

@router.get("/job-hunt/resumes", name="list user resumes", response_model=List[UserResumeOut])
@traceroot.trace()
def list_resumes(
    session: Session = Depends(session),
    auth: Auth = Depends(auth_must),
    active_only: bool = Query(True, description="Only return active resumes")
):
    """List all resumes for the current user."""
    query = select(UserResume).where(
        UserResume.user_id == auth.user.id,
        UserResume.deleted_at.is_(None)
    )
    if active_only:
        query = query.where(UserResume.is_active == True)
    query = query.order_by(UserResume.created_at.desc())
    
    resumes = session.exec(query).all()
    logger.debug(f"Listed {len(resumes)} resumes for user {auth.user.id}")
    return resumes


@router.post("/job-hunt/resumes", name="create resume", response_model=UserResumeOut)
@traceroot.trace()
def create_resume(
    data: UserResumeCreate,
    session: Session = Depends(session),
    auth: Auth = Depends(auth_must)
):
    """Create a new user resume."""
    resume = UserResume(
        user_id=auth.user.id,
        title=data.title,
        raw_text=data.raw_text,
        full_name=data.full_name,
        email=data.email,
        phone=data.phone,
        location=data.location,
        linkedin_url=data.linkedin_url,
        portfolio_url=data.portfolio_url,
        summary=data.summary,
        skills=data.skills,
        experience=data.experience,
        education=data.education,
        certifications=data.certifications,
        languages=data.languages,
    )
    resume.save(session)
    logger.info(f"Created resume {resume.id} for user {auth.user.id}")
    return resume


@router.get("/job-hunt/resumes/{resume_id}", name="get resume", response_model=UserResumeOut)
@traceroot.trace()
def get_resume(
    resume_id: int,
    session: Session = Depends(session),
    auth: Auth = Depends(auth_must)
):
    """Get a specific resume by ID."""
    resume = session.exec(
        select(UserResume).where(
            UserResume.id == resume_id,
            UserResume.user_id == auth.user.id,
            UserResume.deleted_at.is_(None)
        )
    ).first()
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")
    return resume


@router.put("/job-hunt/resumes/{resume_id}", name="update resume", response_model=UserResumeOut)
@traceroot.trace()
def update_resume(
    resume_id: int,
    data: UserResumeCreate,
    session: Session = Depends(session),
    auth: Auth = Depends(auth_must)
):
    """Update an existing resume."""
    resume = session.exec(
        select(UserResume).where(
            UserResume.id == resume_id,
            UserResume.user_id == auth.user.id,
            UserResume.deleted_at.is_(None)
        )
    ).first()
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")
    
    for field, value in data.dict().items():
        setattr(resume, field, value)
    resume.save(session)
    logger.info(f"Updated resume {resume_id}")
    return resume


@router.delete("/job-hunt/resumes/{resume_id}", name="delete resume")
@traceroot.trace()
def delete_resume(
    resume_id: int,
    session: Session = Depends(session),
    auth: Auth = Depends(auth_must)
):
    """Soft delete a resume."""
    resume = session.exec(
        select(UserResume).where(
            UserResume.id == resume_id,
            UserResume.user_id == auth.user.id,
            UserResume.deleted_at.is_(None)
        )
    ).first()
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")
    
    resume.delete(session)
    logger.info(f"Deleted resume {resume_id}")
    return {"message": "Resume deleted successfully"}


# =============================================================================
# Job Hunt Session Endpoints
# =============================================================================

@router.get("/job-hunt/sessions", name="list sessions", response_model=List[JobHuntSessionOut])
@traceroot.trace()
def list_sessions(
    session: Session = Depends(session),
    auth: Auth = Depends(auth_must),
    status: Optional[str] = Query(None, description="Filter by status")
):
    """List all job hunt sessions for the current user."""
    query = select(JobHuntSession).where(
        JobHuntSession.user_id == auth.user.id,
        JobHuntSession.deleted_at.is_(None)
    )
    if status:
        query = query.where(JobHuntSession.status == status)
    query = query.order_by(JobHuntSession.created_at.desc())
    
    sessions = session.exec(query).all()
    logger.debug(f"Listed {len(sessions)} sessions for user {auth.user.id}")
    return sessions


@router.post("/job-hunt/sessions", name="create session", response_model=JobHuntSessionOut)
@traceroot.trace()
def create_session(
    data: JobHuntSessionCreate,
    session: Session = Depends(session),
    auth: Auth = Depends(auth_must)
):
    """Create a new job hunt session."""
    hunt_session = JobHuntSession(
        user_id=auth.user.id,
        resume_id=data.resume_id,
        title=data.title,
        search_criteria=data.search_criteria,
    )
    hunt_session.save(session)
    logger.info(f"Created session {hunt_session.id} for user {auth.user.id}")
    return hunt_session


@router.get("/job-hunt/sessions/{session_id}", name="get session", response_model=JobHuntSessionOut)
@traceroot.trace()
def get_session(
    session_id: int,
    session: Session = Depends(session),
    auth: Auth = Depends(auth_must)
):
    """Get a specific job hunt session by ID."""
    hunt_session = session.exec(
        select(JobHuntSession).where(
            JobHuntSession.id == session_id,
            JobHuntSession.user_id == auth.user.id,
            JobHuntSession.deleted_at.is_(None)
        )
    ).first()
    if not hunt_session:
        raise HTTPException(status_code=404, detail="Session not found")
    return hunt_session


@router.patch("/job-hunt/sessions/{session_id}/status", name="update session status", response_model=JobHuntSessionOut)
@traceroot.trace()
def update_session_status(
    session_id: int,
    data: SessionStatusUpdate,
    session: Session = Depends(session),
    auth: Auth = Depends(auth_must)
):
    """Update the status of a job hunt session."""
    hunt_session = session.exec(
        select(JobHuntSession).where(
            JobHuntSession.id == session_id,
            JobHuntSession.user_id == auth.user.id,
            JobHuntSession.deleted_at.is_(None)
        )
    ).first()
    if not hunt_session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    valid_statuses = ["pending", "running", "completed", "failed", "cancelled"]
    if data.status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {valid_statuses}")
    
    hunt_session.status = data.status
    if data.status == "running" and not hunt_session.started_at:
        hunt_session.started_at = datetime.utcnow()
    elif data.status in ["completed", "failed", "cancelled"]:
        hunt_session.completed_at = datetime.utcnow()
    
    hunt_session.save(session)
    logger.info(f"Updated session {session_id} status to {data.status}")
    return hunt_session


@router.delete("/job-hunt/sessions/{session_id}", name="delete session")
@traceroot.trace()
def delete_session(
    session_id: int,
    session: Session = Depends(session),
    auth: Auth = Depends(auth_must)
):
    """Soft delete a job hunt session."""
    hunt_session = session.exec(
        select(JobHuntSession).where(
            JobHuntSession.id == session_id,
            JobHuntSession.user_id == auth.user.id,
            JobHuntSession.deleted_at.is_(None)
        )
    ).first()
    if not hunt_session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    hunt_session.delete(session)
    logger.info(f"Deleted session {session_id}")
    return {"message": "Session deleted successfully"}


# =============================================================================
# Scraped Jobs Endpoints
# =============================================================================

@router.get("/job-hunt/jobs", name="list jobs", response_model=List[ScrapedJobOut])
@traceroot.trace()
def list_jobs(
    session: Session = Depends(session),
    auth: Auth = Depends(auth_must),
    session_id: Optional[int] = Query(None, description="Filter by session ID"),
    is_analyzed: Optional[bool] = Query(None, description="Filter by analysis status"),
    limit: int = Query(100, le=500)
):
    """List scraped jobs, optionally filtered by session."""
    # Get user's session IDs
    user_session_ids = session.exec(
        select(JobHuntSession.id).where(
            JobHuntSession.user_id == auth.user.id,
            JobHuntSession.deleted_at.is_(None)
        )
    ).all()
    
    if not user_session_ids:
        return []
    
    query = select(ScrapedJob).where(
        ScrapedJob.session_id.in_(user_session_ids),
        ScrapedJob.deleted_at.is_(None)
    )
    if session_id:
        if session_id not in user_session_ids:
            raise HTTPException(status_code=403, detail="Access denied to this session")
        query = query.where(ScrapedJob.session_id == session_id)
    if is_analyzed is not None:
        query = query.where(ScrapedJob.is_analyzed == is_analyzed)
    
    query = query.order_by(ScrapedJob.created_at.desc()).limit(limit)
    jobs = session.exec(query).all()
    logger.debug(f"Listed {len(jobs)} jobs")
    return jobs


@router.post("/job-hunt/jobs", name="create job", response_model=ScrapedJobOut)
@traceroot.trace()
def create_job(
    data: ScrapedJobCreate,
    session: Session = Depends(session),
    auth: Auth = Depends(auth_must)
):
    """Create a new scraped job record."""
    # Verify session belongs to user
    hunt_session = session.exec(
        select(JobHuntSession).where(
            JobHuntSession.id == data.session_id,
            JobHuntSession.user_id == auth.user.id,
            JobHuntSession.deleted_at.is_(None)
        )
    ).first()
    if not hunt_session:
        raise HTTPException(status_code=403, detail="Access denied to this session")
    
    # Check for duplicate by url_hash (global deduplication)
    existing = session.exec(
        select(ScrapedJob).where(ScrapedJob.url_hash == data.url_hash)
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="Job with this URL already exists")
    
    job = ScrapedJob(**data.dict())
    job.save(session)
    
    # Update session job count
    hunt_session.jobs_found = hunt_session.jobs_found + 1
    hunt_session.save(session)
    
    logger.info(f"Created job {job.id} for session {data.session_id}")
    return job


@router.post("/job-hunt/jobs/bulk", name="bulk create jobs", response_model=dict)
@traceroot.trace()
def bulk_create_jobs(
    jobs: List[ScrapedJobCreate],
    session: Session = Depends(session),
    auth: Auth = Depends(auth_must)
):
    """Bulk create scraped job records with deduplication."""
    if not jobs:
        return {"created": 0, "duplicates": 0, "errors": []}
    
    # Verify all sessions belong to user
    session_ids = set(job.session_id for job in jobs)
    user_sessions = session.exec(
        select(JobHuntSession).where(
            JobHuntSession.id.in_(session_ids),
            JobHuntSession.user_id == auth.user.id,
            JobHuntSession.deleted_at.is_(None)
        )
    ).all()
    user_session_ids = {s.id for s in user_sessions}
    
    if session_ids - user_session_ids:
        raise HTTPException(status_code=403, detail="Access denied to some sessions")
    
    # Get existing hashes for deduplication
    new_hashes = [job.url_hash for job in jobs]
    existing_hashes = set(session.exec(
        select(ScrapedJob.url_hash).where(ScrapedJob.url_hash.in_(new_hashes))
    ).all())
    
    created = 0
    duplicates = 0
    errors = []
    session_job_counts = {s.id: 0 for s in user_sessions}
    
    for job_data in jobs:
        if job_data.url_hash in existing_hashes:
            duplicates += 1
            continue
        
        try:
            job = ScrapedJob(**job_data.dict())
            session.add(job)
            created += 1
            session_job_counts[job_data.session_id] += 1
            existing_hashes.add(job_data.url_hash)  # Prevent intra-batch duplicates
        except Exception as e:
            errors.append(str(e))
    
    # Update session job counts
    for sess in user_sessions:
        if session_job_counts[sess.id] > 0:
            sess.jobs_found = sess.jobs_found + session_job_counts[sess.id]
    
    session.commit()
    logger.info(f"Bulk created {created} jobs, {duplicates} duplicates skipped")
    return {"created": created, "duplicates": duplicates, "errors": errors}


@router.get("/job-hunt/jobs/hashes", name="get job hashes", response_model=JobHashesResponse)
@traceroot.trace()
def get_job_hashes(
    session: Session = Depends(session),
    auth: Auth = Depends(auth_must),
    session_id: Optional[int] = Query(None, description="Filter by session ID (optional)")
):
    """
    Get all existing job URL hashes for deduplication.
    
    This endpoint is used by the Job Scraper Agent to check which jobs
    have already been scraped before making new requests.
    """
    # If no session filter, get hashes from all user's sessions
    if session_id:
        # Verify session belongs to user
        hunt_session = session.exec(
            select(JobHuntSession).where(
                JobHuntSession.id == session_id,
                JobHuntSession.user_id == auth.user.id,
                JobHuntSession.deleted_at.is_(None)
            )
        ).first()
        if not hunt_session:
            raise HTTPException(status_code=403, detail="Access denied to this session")
        
        hashes = session.exec(
            select(ScrapedJob.url_hash).where(
                ScrapedJob.session_id == session_id,
                ScrapedJob.deleted_at.is_(None)
            )
        ).all()
    else:
        # Get hashes from all sessions (global deduplication)
        hashes = session.exec(
            select(ScrapedJob.url_hash).where(
                ScrapedJob.deleted_at.is_(None)
            )
        ).all()
    
    logger.debug(f"Retrieved {len(hashes)} job hashes")
    return JobHashesResponse(hashes=list(hashes), count=len(hashes))


@router.get("/job-hunt/jobs/{job_id}", name="get job", response_model=ScrapedJobOut)
@traceroot.trace()
def get_job(
    job_id: int,
    session: Session = Depends(session),
    auth: Auth = Depends(auth_must)
):
    """Get a specific job by ID."""
    # Get user's session IDs
    user_session_ids = session.exec(
        select(JobHuntSession.id).where(
            JobHuntSession.user_id == auth.user.id,
            JobHuntSession.deleted_at.is_(None)
        )
    ).all()
    
    job = session.exec(
        select(ScrapedJob).where(
            ScrapedJob.id == job_id,
            ScrapedJob.session_id.in_(user_session_ids),
            ScrapedJob.deleted_at.is_(None)
        )
    ).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


# =============================================================================
# Job Analysis Endpoints
# =============================================================================

@router.get("/job-hunt/analyses", name="list analyses", response_model=List[JobAnalysisOut])
@traceroot.trace()
def list_analyses(
    session: Session = Depends(session),
    auth: Auth = Depends(auth_must),
    session_id: Optional[int] = Query(None, description="Filter by session ID"),
    min_score: Optional[float] = Query(None, ge=0, le=100, description="Minimum overall score"),
    limit: int = Query(100, le=500)
):
    """List job analyses, optionally filtered."""
    # Get user's session IDs
    user_session_ids = session.exec(
        select(JobHuntSession.id).where(
            JobHuntSession.user_id == auth.user.id,
            JobHuntSession.deleted_at.is_(None)
        )
    ).all()
    
    if not user_session_ids:
        return []
    
    query = select(JobAnalysis).where(
        JobAnalysis.session_id.in_(user_session_ids),
        JobAnalysis.deleted_at.is_(None)
    )
    if session_id:
        if session_id not in user_session_ids:
            raise HTTPException(status_code=403, detail="Access denied to this session")
        query = query.where(JobAnalysis.session_id == session_id)
    if min_score is not None:
        query = query.where(JobAnalysis.overall_score >= min_score)
    
    query = query.order_by(JobAnalysis.overall_score.desc()).limit(limit)
    analyses = session.exec(query).all()
    logger.debug(f"Listed {len(analyses)} analyses")
    return analyses


@router.post("/job-hunt/analyses", name="create analysis", response_model=JobAnalysisOut)
@traceroot.trace()
def create_analysis(
    data: JobAnalysisCreate,
    session: Session = Depends(session),
    auth: Auth = Depends(auth_must)
):
    """Create a new job analysis."""
    # Verify session belongs to user
    hunt_session = session.exec(
        select(JobHuntSession).where(
            JobHuntSession.id == data.session_id,
            JobHuntSession.user_id == auth.user.id,
            JobHuntSession.deleted_at.is_(None)
        )
    ).first()
    if not hunt_session:
        raise HTTPException(status_code=403, detail="Access denied to this session")
    
    analysis = JobAnalysis(**data.dict())
    analysis.save(session)
    
    # Mark job as analyzed
    job = session.get(ScrapedJob, data.job_id)
    if job:
        job.is_analyzed = True
        job.save(session)
    
    # Update session analysis count
    hunt_session.jobs_analyzed = hunt_session.jobs_analyzed + 1
    hunt_session.save(session)
    
    logger.info(f"Created analysis {analysis.id} for job {data.job_id}")
    return analysis


@router.get("/job-hunt/analyses/{analysis_id}", name="get analysis", response_model=JobAnalysisOut)
@traceroot.trace()
def get_analysis(
    analysis_id: int,
    session: Session = Depends(session),
    auth: Auth = Depends(auth_must)
):
    """Get a specific analysis by ID."""
    # Get user's session IDs
    user_session_ids = session.exec(
        select(JobHuntSession.id).where(
            JobHuntSession.user_id == auth.user.id,
            JobHuntSession.deleted_at.is_(None)
        )
    ).all()
    
    analysis = session.exec(
        select(JobAnalysis).where(
            JobAnalysis.id == analysis_id,
            JobAnalysis.session_id.in_(user_session_ids),
            JobAnalysis.deleted_at.is_(None)
        )
    ).first()
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return analysis


# =============================================================================
# Tailored Resume Endpoints
# =============================================================================

@router.get("/job-hunt/tailored-resumes", name="list tailored resumes", response_model=List[TailoredResumeOut])
@traceroot.trace()
def list_tailored_resumes(
    session: Session = Depends(session),
    auth: Auth = Depends(auth_must),
    session_id: Optional[int] = Query(None, description="Filter by session ID"),
    limit: int = Query(100, le=500)
):
    """List tailored resumes."""
    # Get user's session IDs
    user_session_ids = session.exec(
        select(JobHuntSession.id).where(
            JobHuntSession.user_id == auth.user.id,
            JobHuntSession.deleted_at.is_(None)
        )
    ).all()
    
    if not user_session_ids:
        return []
    
    query = select(TailoredResume).where(
        TailoredResume.session_id.in_(user_session_ids),
        TailoredResume.deleted_at.is_(None)
    )
    if session_id:
        if session_id not in user_session_ids:
            raise HTTPException(status_code=403, detail="Access denied to this session")
        query = query.where(TailoredResume.session_id == session_id)
    
    query = query.order_by(TailoredResume.created_at.desc()).limit(limit)
    resumes = session.exec(query).all()
    logger.debug(f"Listed {len(resumes)} tailored resumes")
    return resumes


@router.post("/job-hunt/tailored-resumes", name="create tailored resume", response_model=TailoredResumeOut)
@traceroot.trace()
def create_tailored_resume(
    data: TailoredResumeCreate,
    session: Session = Depends(session),
    auth: Auth = Depends(auth_must)
):
    """Create a new tailored resume."""
    # Verify session belongs to user
    hunt_session = session.exec(
        select(JobHuntSession).where(
            JobHuntSession.id == data.session_id,
            JobHuntSession.user_id == auth.user.id,
            JobHuntSession.deleted_at.is_(None)
        )
    ).first()
    if not hunt_session:
        raise HTTPException(status_code=403, detail="Access denied to this session")
    
    tailored = TailoredResume(**data.dict())
    tailored.save(session)
    
    # Update session tailored count
    hunt_session.resumes_tailored = hunt_session.resumes_tailored + 1
    hunt_session.save(session)
    
    logger.info(f"Created tailored resume {tailored.id} for job {data.job_id}")
    return tailored


@router.get("/job-hunt/tailored-resumes/{tailored_id}", name="get tailored resume", response_model=TailoredResumeOut)
@traceroot.trace()
def get_tailored_resume(
    tailored_id: int,
    session: Session = Depends(session),
    auth: Auth = Depends(auth_must)
):
    """Get a specific tailored resume by ID."""
    # Get user's session IDs
    user_session_ids = session.exec(
        select(JobHuntSession.id).where(
            JobHuntSession.user_id == auth.user.id,
            JobHuntSession.deleted_at.is_(None)
        )
    ).all()
    
    tailored = session.exec(
        select(TailoredResume).where(
            TailoredResume.id == tailored_id,
            TailoredResume.session_id.in_(user_session_ids),
            TailoredResume.deleted_at.is_(None)
        )
    ).first()
    if not tailored:
        raise HTTPException(status_code=404, detail="Tailored resume not found")
    return tailored


# =============================================================================
# Aggregation Endpoints
# =============================================================================

@router.get("/job-hunt/sessions/{session_id}/summary", name="get session summary")
@traceroot.trace()
def get_session_summary(
    session_id: int,
    session: Session = Depends(session),
    auth: Auth = Depends(auth_must)
):
    """Get a comprehensive summary of a job hunt session."""
    hunt_session = session.exec(
        select(JobHuntSession).where(
            JobHuntSession.id == session_id,
            JobHuntSession.user_id == auth.user.id,
            JobHuntSession.deleted_at.is_(None)
        )
    ).first()
    if not hunt_session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Get top analyses
    top_analyses = session.exec(
        select(JobAnalysis).where(
            JobAnalysis.session_id == session_id,
            JobAnalysis.deleted_at.is_(None)
        ).order_by(JobAnalysis.overall_score.desc()).limit(10)
    ).all()
    
    # Get job details for top analyses
    top_jobs = []
    for analysis in top_analyses:
        job = session.get(ScrapedJob, analysis.job_id)
        if job:
            top_jobs.append({
                "job_id": job.id,
                "title": job.title,
                "company": job.company,
                "location": job.location,
                "salary_min": job.salary_min,
                "salary_max": job.salary_max,
                "job_url": job.job_url,
                "overall_score": analysis.overall_score,
                "fit_level": analysis.fit_level,
                "analysis_id": analysis.id,
            })
    
    # Get tailored resume count
    tailored_count = session.exec(
        select(func.count(TailoredResume.id)).where(
            TailoredResume.session_id == session_id,
            TailoredResume.deleted_at.is_(None)
        )
    ).one()
    
    return {
        "session": hunt_session,
        "top_matches": top_jobs,
        "statistics": {
            "total_jobs_found": hunt_session.jobs_found,
            "jobs_analyzed": hunt_session.jobs_analyzed,
            "resumes_tailored": tailored_count,
            "excellent_matches": len([j for j in top_jobs if j["fit_level"] == "excellent"]),
            "good_matches": len([j for j in top_jobs if j["fit_level"] == "good"]),
        }
    }
