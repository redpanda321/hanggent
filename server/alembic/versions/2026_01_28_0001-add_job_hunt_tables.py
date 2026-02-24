"""Add job hunt tables for multi-agent job hunting workforce

Revision ID: add_job_hunt_tables
Revises: add_stripe_fields_to_user
Create Date: 2026-01-28

Tables created:
- user_resume: User uploaded and parsed resumes
- scraped_job: Jobs scraped from job boards with url_hash deduplication
- job_analysis: Resume-job match analysis results
- tailored_resume: AI-generated tailored resumes
- job_hunt_session: Job hunting workflow sessions

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add_job_hunt_tables'
down_revision: Union[str, None] = 'add_stripe_fields_to_user'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create user_resume table
    op.create_table(
        'user_resume',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('user_id', sa.Integer(), nullable=False, index=True),
        
        # File storage
        sa.Column('file_path', sa.String(500), nullable=False),
        sa.Column('file_name', sa.String(255), nullable=False),
        
        # Parsed resume data
        sa.Column('name', sa.String(255), nullable=True, server_default=''),
        sa.Column('email', sa.String(255), nullable=True, server_default=''),
        sa.Column('phone', sa.String(50), nullable=True, server_default=''),
        sa.Column('summary', sa.Text(), nullable=True),
        
        # Structured data as JSON
        sa.Column('skills', sa.JSON(), nullable=True),
        sa.Column('experience', sa.JSON(), nullable=True),
        sa.Column('education', sa.JSON(), nullable=True),
        sa.Column('certifications', sa.JSON(), nullable=True),
        sa.Column('languages', sa.JSON(), nullable=True),
        
        # Raw text for search
        sa.Column('raw_text', sa.Text(), nullable=True),
        
        # Timestamps
        sa.Column('created_at', sa.TIMESTAMP(), nullable=True, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.TIMESTAMP(), nullable=True, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('deleted_at', sa.TIMESTAMP(), nullable=True),
    )
    
    # Create scraped_job table with url_hash unique constraint for deduplication
    op.create_table(
        'scraped_job',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        
        # Deduplication key - unique across all sessions
        sa.Column('url_hash', sa.String(32), nullable=False, unique=True, index=True),
        
        # Session tracking
        sa.Column('session_id', sa.Integer(), nullable=True, index=True),
        
        # Core job info
        sa.Column('title', sa.String(500), nullable=False),
        sa.Column('company', sa.String(255), nullable=False),
        sa.Column('location', sa.String(255), nullable=True, server_default=''),
        sa.Column('job_url', sa.String(1000), nullable=False),
        sa.Column('job_url_direct', sa.String(1000), nullable=True, server_default=''),
        
        # Source info
        sa.Column('source', sa.String(50), nullable=False),
        
        # Job details
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('job_type', sa.String(50), nullable=True, server_default=''),
        sa.Column('is_remote', sa.Boolean(), nullable=False, server_default='0'),
        
        # Salary info
        sa.Column('salary_min', sa.Float(), nullable=True),
        sa.Column('salary_max', sa.Float(), nullable=True),
        sa.Column('salary_currency', sa.String(10), nullable=True, server_default='USD'),
        sa.Column('salary_interval', sa.String(20), nullable=True, server_default='yearly'),
        
        # Dates
        sa.Column('posted_date', sa.TIMESTAMP(), nullable=True),
        
        # Additional metadata
        sa.Column('company_url', sa.String(500), nullable=True, server_default=''),
        sa.Column('company_logo', sa.String(500), nullable=True, server_default=''),
        sa.Column('emails', sa.JSON(), nullable=True),
        
        # Extracted requirements
        sa.Column('required_skills', sa.JSON(), nullable=True),
        sa.Column('preferred_skills', sa.JSON(), nullable=True),
        sa.Column('experience_years', sa.Integer(), nullable=True),
        sa.Column('education_requirement', sa.String(255), nullable=True, server_default=''),
        
        # Timestamps
        sa.Column('created_at', sa.TIMESTAMP(), nullable=True, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.TIMESTAMP(), nullable=True, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('deleted_at', sa.TIMESTAMP(), nullable=True),
    )
    
    # Create job_analysis table
    op.create_table(
        'job_analysis',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        
        # Foreign keys
        sa.Column('resume_id', sa.Integer(), nullable=False, index=True),
        sa.Column('job_id', sa.Integer(), nullable=False, index=True),
        sa.Column('user_id', sa.Integer(), nullable=False, index=True),
        
        # Scores (0-100)
        sa.Column('overall_score', sa.Float(), nullable=False),
        sa.Column('skill_match_score', sa.Float(), nullable=True, server_default='0'),
        sa.Column('experience_match_score', sa.Float(), nullable=True, server_default='0'),
        sa.Column('education_match_score', sa.Float(), nullable=True, server_default='0'),
        sa.Column('keyword_match_score', sa.Float(), nullable=True, server_default='0'),
        
        # Match details
        sa.Column('matching_skills', sa.JSON(), nullable=True),
        sa.Column('missing_skills', sa.JSON(), nullable=True),
        sa.Column('keyword_overlap', sa.JSON(), nullable=True),
        
        # Qualitative analysis
        sa.Column('strengths', sa.JSON(), nullable=True),
        sa.Column('weaknesses', sa.JSON(), nullable=True),
        sa.Column('recommendations', sa.JSON(), nullable=True),
        
        # Fit assessment
        sa.Column('fit_level', sa.String(50), nullable=True, server_default=''),
        sa.Column('interview_likelihood', sa.String(50), nullable=True, server_default=''),
        
        # Full analysis report
        sa.Column('analysis_report', sa.Text(), nullable=True),
        
        # Timestamps
        sa.Column('created_at', sa.TIMESTAMP(), nullable=True, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.TIMESTAMP(), nullable=True, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('deleted_at', sa.TIMESTAMP(), nullable=True),
    )
    
    # Create tailored_resume table
    op.create_table(
        'tailored_resume',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        
        # Foreign keys
        sa.Column('analysis_id', sa.Integer(), nullable=False, index=True),
        sa.Column('original_resume_id', sa.Integer(), nullable=False, index=True),
        sa.Column('job_id', sa.Integer(), nullable=False, index=True),
        sa.Column('user_id', sa.Integer(), nullable=False, index=True),
        
        # File storage
        sa.Column('file_path', sa.String(500), nullable=False),
        sa.Column('format', sa.String(20), nullable=False),
        
        # Tailored content
        sa.Column('tailored_content', sa.Text(), nullable=True),
        
        # Optimization tracking
        sa.Column('optimizations_made', sa.JSON(), nullable=True),
        sa.Column('keywords_added', sa.JSON(), nullable=True),
        
        # Quality scores
        sa.Column('ats_score', sa.Float(), nullable=True, server_default='0'),
        sa.Column('improvement_delta', sa.Float(), nullable=True, server_default='0'),
        
        # Cover letter
        sa.Column('cover_letter_path', sa.String(500), nullable=True),
        sa.Column('cover_letter_content', sa.Text(), nullable=True),
        
        # Timestamps
        sa.Column('created_at', sa.TIMESTAMP(), nullable=True, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.TIMESTAMP(), nullable=True, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('deleted_at', sa.TIMESTAMP(), nullable=True),
    )
    
    # Create job_hunt_session table
    op.create_table(
        'job_hunt_session',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        
        # User and project context
        sa.Column('user_id', sa.Integer(), nullable=False, index=True),
        sa.Column('project_id', sa.String(64), nullable=False, index=True),
        sa.Column('task_id', sa.String(64), nullable=False, index=True),
        
        # Resume being used
        sa.Column('resume_id', sa.Integer(), nullable=False, index=True),
        
        # Search criteria
        sa.Column('search_criteria', sa.JSON(), nullable=True),
        
        # Progress tracking
        sa.Column('status', sa.SmallInteger(), nullable=False, server_default='1'),
        sa.Column('status_message', sa.String(500), nullable=True, server_default=''),
        
        # Results
        sa.Column('jobs_found_count', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('jobs_analyzed_count', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('jobs_tailored_count', sa.Integer(), nullable=True, server_default='0'),
        
        # IDs of related records
        sa.Column('job_ids', sa.JSON(), nullable=True),
        sa.Column('analysis_ids', sa.JSON(), nullable=True),
        sa.Column('tailored_resume_ids', sa.JSON(), nullable=True),
        
        # Configuration
        sa.Column('auto_analyze', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('auto_tailor_top_n', sa.Integer(), nullable=False, server_default='3'),
        sa.Column('min_score_threshold', sa.Float(), nullable=False, server_default='60'),
        
        # Timestamps
        sa.Column('created_at', sa.TIMESTAMP(), nullable=True, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.TIMESTAMP(), nullable=True, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('deleted_at', sa.TIMESTAMP(), nullable=True),
    )
    
    # Create composite index for job analysis lookups
    op.create_index('ix_job_analysis_resume_job', 'job_analysis', ['resume_id', 'job_id'])


def downgrade() -> None:
    op.drop_index('ix_job_analysis_resume_job', 'job_analysis')
    op.drop_table('job_hunt_session')
    op.drop_table('tailored_resume')
    op.drop_table('job_analysis')
    op.drop_table('scraped_job')
    op.drop_table('user_resume')
