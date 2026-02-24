"""
Job Scraper Toolkit using JobSpy (https://github.com/speedyapply/JobSpy)

This toolkit provides tools for scraping job listings from multiple job boards
including LinkedIn, Indeed, Glassdoor, ZipRecruiter, and Google Jobs.

Default settings:
- Sites: LinkedIn, Indeed
- Time range: Last 7 days (168 hours)
- Deduplication: By job_url hash across all sessions
"""
import hashlib
import json
import os
from datetime import datetime
from typing import List, Optional
from pathlib import Path

from camel.toolkits import BaseToolkit
from camel.toolkits.function_tool import FunctionTool

from app.utils.toolkit.abstract_toolkit import AbstractToolkit
from app.utils.listen.toolkit_listen import auto_listen_toolkit, listen_toolkit
from app.component.environment import env
from utils import traceroot_wrapper as traceroot

logger = traceroot.get_logger("job_scraper_toolkit")


class JobScraperToolkit(BaseToolkit, AbstractToolkit):
    """
    Toolkit for scraping job listings using python-jobspy.
    
    Default configuration:
    - Sites: LinkedIn, Indeed (most reliable sources)
    - Time range: 7 days (168 hours)
    - Results: 20 per site
    - Deduplication: MD5 hash of job_url
    """
    
    agent_name: str = "Job_Scraper_Agent"
    
    # Default settings
    DEFAULT_SITES = ["linkedin", "indeed"]
    DEFAULT_HOURS_OLD = 168  # 7 days
    DEFAULT_RESULTS = 20
    
    def __init__(
        self,
        api_task_id: str,
        agent_name: str | None = None,
        working_directory: str = "",
        server_url: str | None = None,
    ):
        self.api_task_id = api_task_id
        self.working_directory = working_directory
        self.server_url = server_url or env("SERVER_URL", "http://localhost:3001")
        if agent_name is not None:
            self.agent_name = agent_name
        super().__init__()
        
        # Cache of known job URL hashes (populated from server)
        self._known_hashes: set = set()
        self._hashes_loaded = False
    
    def _compute_url_hash(self, job_url: str) -> str:
        """Compute MD5 hash of job URL for deduplication"""
        return hashlib.md5(job_url.encode()).hexdigest()
    
    async def _load_existing_hashes(self) -> None:
        """Load existing job URL hashes from server for deduplication"""
        if self._hashes_loaded:
            return
            
        try:
            import httpx
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.server_url}/api/job-hunt/jobs/hashes",
                    timeout=30.0,
                )
                if response.status_code == 200:
                    self._known_hashes = set(response.json().get("hashes", []))
                    logger.info(f"Loaded {len(self._known_hashes)} existing job hashes")
        except Exception as e:
            logger.warning(f"Could not load existing hashes: {e}")
        
        self._hashes_loaded = True
    
    def _load_existing_hashes_sync(self) -> None:
        """Synchronous version of hash loading"""
        if self._hashes_loaded:
            return
            
        try:
            import httpx
            response = httpx.get(
                f"{self.server_url}/api/job-hunt/jobs/hashes",
                timeout=30.0,
            )
            if response.status_code == 200:
                self._known_hashes = set(response.json().get("hashes", []))
                logger.info(f"Loaded {len(self._known_hashes)} existing job hashes")
        except Exception as e:
            logger.warning(f"Could not load existing hashes: {e}")
        
        self._hashes_loaded = True
    
    def search_jobs(
        self,
        search_term: str,
        location: str = "",
        site_names: Optional[List[str]] = None,
        results_wanted: int = 20,
        hours_old: int = 168,
        country_indeed: str = "USA",
        is_remote: bool = False,
        job_type: Optional[str] = None,
        easy_apply: bool = False,
        description_format: str = "markdown",
        linkedin_fetch_description: bool = True,
        offset: int = 0,
    ) -> str:
        """
        Search for jobs across multiple job boards using JobSpy.
        
        Automatically deduplicates against previously scraped jobs using URL hashing.
        Default: LinkedIn and Indeed, last 7 days.
        
        Args:
            search_term: Job title or keywords (e.g., "software engineer", "python developer")
            location: City, state, or country (e.g., "San Francisco, CA", "Remote")
            site_names: Job boards to search. Options: linkedin, indeed, glassdoor, zip_recruiter, google
                       Default: ["linkedin", "indeed"]
            results_wanted: Number of results per site (default 20)
            hours_old: Filter jobs posted within X hours (default 168 = 7 days)
            country_indeed: Country for Indeed search (default "USA")
            is_remote: Filter for remote jobs only
            job_type: Filter by type - fulltime, parttime, internship, contract
            easy_apply: LinkedIn easy apply jobs only
            description_format: Output format - markdown or html
            linkedin_fetch_description: Fetch full description from LinkedIn (slower but complete)
            offset: Pagination offset
            
        Returns:
            JSON string of new job listings (deduplicated) with fields:
            title, company, location, job_url, description, salary, date_posted, etc.
        """
        try:
            from jobspy import scrape_jobs
            
            # Use defaults if not specified
            sites = site_names or self.DEFAULT_SITES
            
            logger.info(f"Searching jobs: '{search_term}' in '{location}' on {sites}")
            
            # Scrape jobs
            jobs_df = scrape_jobs(
                site_name=sites,
                search_term=search_term,
                location=location,
                results_wanted=results_wanted,
                hours_old=hours_old,
                country_indeed=country_indeed,
                is_remote=is_remote,
                job_type=job_type,
                easy_apply=easy_apply,
                description_format=description_format,
                linkedin_fetch_description=linkedin_fetch_description,
                offset=offset,
            )
            
            if jobs_df.empty:
                return json.dumps({
                    "status": "success",
                    "message": "No jobs found matching the criteria.",
                    "jobs": [],
                    "total_found": 0,
                    "new_jobs": 0,
                })
            
            # Load existing hashes for deduplication
            self._load_existing_hashes_sync()
            
            # Process and deduplicate jobs
            jobs = jobs_df.to_dict('records')
            new_jobs = []
            duplicates = 0
            
            for job in jobs:
                job_url = job.get('job_url', '')
                if not job_url:
                    continue
                    
                url_hash = self._compute_url_hash(job_url)
                
                # Skip if already known
                if url_hash in self._known_hashes:
                    duplicates += 1
                    continue
                
                # Add hash for tracking
                job['url_hash'] = url_hash
                
                # Convert datetime objects to strings
                for key, value in job.items():
                    if isinstance(value, datetime):
                        job[key] = value.isoformat()
                    elif hasattr(value, 'item'):  # numpy types
                        job[key] = value.item()
                
                new_jobs.append(job)
                self._known_hashes.add(url_hash)
            
            # Save to working directory
            if self.working_directory and new_jobs:
                output_path = Path(self.working_directory) / "jobs_scraped.json"
                with open(output_path, 'w', encoding='utf-8') as f:
                    json.dump(new_jobs, f, indent=2, default=str)
                logger.info(f"Saved {len(new_jobs)} jobs to {output_path}")
                
                # Also save CSV for easy viewing
                csv_path = Path(self.working_directory) / "jobs_scraped.csv"
                jobs_df[jobs_df['job_url'].isin([j['job_url'] for j in new_jobs])].to_csv(
                    csv_path, index=False
                )
            
            logger.info(f"Found {len(jobs)} jobs, {len(new_jobs)} new, {duplicates} duplicates")
            
            return json.dumps({
                "status": "success",
                "message": f"Found {len(new_jobs)} new jobs ({duplicates} duplicates filtered)",
                "jobs": new_jobs,
                "total_found": len(jobs),
                "new_jobs": len(new_jobs),
                "duplicates_filtered": duplicates,
                "search_criteria": {
                    "search_term": search_term,
                    "location": location,
                    "sites": sites,
                    "hours_old": hours_old,
                    "is_remote": is_remote,
                    "job_type": job_type,
                }
            }, indent=2, default=str)
            
        except ImportError:
            error_msg = "python-jobspy is not installed. Run: pip install python-jobspy"
            logger.error(error_msg)
            return json.dumps({"status": "error", "message": error_msg})
        except Exception as e:
            error_msg = f"Error scraping jobs: {str(e)}"
            logger.error(error_msg)
            return json.dumps({"status": "error", "message": error_msg})
    
    def search_jobs_with_proxies(
        self,
        search_term: str,
        location: str,
        site_names: Optional[List[str]] = None,
        results_wanted: int = 20,
        proxies: Optional[List[str]] = None,
    ) -> str:
        """
        Search jobs using rotating proxies to avoid rate limiting.
        
        Use this method when you need to scrape a large number of jobs
        or when facing rate limiting issues.
        
        Args:
            search_term: Job title or keywords
            location: Location for search
            site_names: Job boards to search (default: linkedin, indeed)
            results_wanted: Number of results per site
            proxies: List of proxy URLs (e.g., ["http://user:pass@host:port"])
            
        Returns:
            JSON string of job listings
        """
        try:
            from jobspy import scrape_jobs
            
            sites = site_names or self.DEFAULT_SITES
            
            jobs_df = scrape_jobs(
                site_name=sites,
                search_term=search_term,
                location=location,
                results_wanted=results_wanted,
                hours_old=self.DEFAULT_HOURS_OLD,
                proxies=proxies,
            )
            
            if jobs_df.empty:
                return json.dumps({
                    "status": "success",
                    "message": "No jobs found.",
                    "jobs": [],
                })
            
            jobs = jobs_df.to_dict('records')
            
            # Add hashes and convert types
            for job in jobs:
                job['url_hash'] = self._compute_url_hash(job.get('job_url', ''))
                for key, value in job.items():
                    if isinstance(value, datetime):
                        job[key] = value.isoformat()
                    elif hasattr(value, 'item'):
                        job[key] = value.item()
            
            return json.dumps({
                "status": "success",
                "jobs": jobs,
                "total": len(jobs),
            }, indent=2, default=str)
            
        except Exception as e:
            return json.dumps({"status": "error", "message": str(e)})
    
    def get_job_board_status(self) -> str:
        """
        Check the status and availability of supported job boards.
        
        Returns:
            JSON string with status of each supported job board
        """
        supported_boards = {
            "linkedin": "LinkedIn Jobs - Most professional jobs, good for tech/business",
            "indeed": "Indeed - Largest job board, wide variety of jobs",
            "glassdoor": "Glassdoor - Good for company reviews and salaries",
            "zip_recruiter": "ZipRecruiter - AI-powered job matching",
            "google": "Google Jobs - Aggregates from multiple sources",
        }
        
        return json.dumps({
            "status": "success",
            "supported_boards": supported_boards,
            "default_boards": self.DEFAULT_SITES,
            "default_time_range_hours": self.DEFAULT_HOURS_OLD,
            "note": "LinkedIn and Indeed are the most reliable sources. "
                   "Other boards may have rate limiting or require proxies.",
        }, indent=2)
    
    def check_job_exists(self, job_url: str) -> str:
        """
        Check if a job URL has already been scraped.
        
        Args:
            job_url: The job URL to check
            
        Returns:
            JSON string with exists status
        """
        self._load_existing_hashes_sync()
        url_hash = self._compute_url_hash(job_url)
        exists = url_hash in self._known_hashes
        
        return json.dumps({
            "job_url": job_url,
            "url_hash": url_hash,
            "exists": exists,
        })
    
    def get_tools(self) -> List[FunctionTool]:
        return [
            FunctionTool(self.search_jobs),
            FunctionTool(self.search_jobs_with_proxies),
            FunctionTool(self.get_job_board_status),
            FunctionTool(self.check_job_exists),
        ]
