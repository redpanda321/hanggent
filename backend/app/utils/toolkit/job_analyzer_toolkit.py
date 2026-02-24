"""
Job Analyzer Toolkit for resume-job matching analysis.

This toolkit provides tools for:
- Parsing resumes from various formats (PDF, DOCX, TXT)
- Extracting structured resume data to YAML (for AIHawk integration)
- Extracting requirements from job descriptions
- Calculating match scores between resumes and jobs
- Generating detailed analysis reports
"""
import json
import os
import re
from typing import List, Dict, Optional, Any, TYPE_CHECKING
from pathlib import Path

from camel.toolkits import BaseToolkit
from camel.toolkits.function_tool import FunctionTool
from camel.models import ModelFactory

import asyncio
from app.utils.toolkit.abstract_toolkit import AbstractToolkit
from app.model.plain_text_resume import PlainTextResume
from app.model.resume_cache import ResumeCache, get_resume_cache
from app.prompts.resume_extraction import (
    get_extraction_messages,
    split_resume_sections,
    get_section_extraction_messages,
    get_detected_sections,
)
from utils import traceroot_wrapper as traceroot

if TYPE_CHECKING:
    from app.model.chat import Chat

logger = traceroot.get_logger("job_analyzer_toolkit")


class JobAnalyzerToolkit(BaseToolkit, AbstractToolkit):
    """
    Toolkit for analyzing job descriptions and resumes.
    
    Provides tools for:
    - Resume parsing (PDF, DOCX, TXT)
    - Job requirement extraction
    - Match scoring (skill, experience, education, keyword)
    - Analysis report generation
    
    Scoring methodology:
    - Skill match: 40% weight
    - Experience match: 30% weight
    - Education match: 15% weight
    - Keyword overlap: 15% weight
    """
    
    agent_name: str = "Job_Analyzer_Agent"
    
    # Scoring weights
    SKILL_WEIGHT = 0.40
    EXPERIENCE_WEIGHT = 0.30
    EDUCATION_WEIGHT = 0.15
    KEYWORD_WEIGHT = 0.15
    
    def __init__(
        self,
        api_task_id: str,
        chat_options: Optional["Chat"] = None,
        agent_name: str | None = None,
        working_directory: str = "",
    ):
        self.api_task_id = api_task_id
        self.chat_options = chat_options
        self.working_directory = working_directory
        if agent_name is not None:
            self.agent_name = agent_name
        
        # Lazy-loaded components
        self._resume_cache: Optional[ResumeCache] = None
        super().__init__()
    
    def _get_resume_cache(self) -> ResumeCache:
        """Get or create resume cache instance."""
        if self._resume_cache is None:
            cache_dir = None
            if self.working_directory:
                cache_dir = str(Path(self.working_directory) / ".resume_cache")
            self._resume_cache = get_resume_cache(cache_dir)
        return self._resume_cache
    
    def _create_llm_model(self, model_override: Optional[str] = None, json_mode: bool = True):
        """
        Create LLM model for resume extraction.
        
        Args:
            model_override: Optional model name to use instead of chat_options model
            json_mode: Whether to enable JSON response format (default True)
            
        Returns:
            Model instance for LLM calls
        """
        if not self.chat_options:
            raise ValueError("chat_options required for LLM-based extraction")
        
        model_type = model_override or self.chat_options.model_type
        
        # Build model config dict with JSON mode if requested
        model_config_dict = {}
        if json_mode:
            model_config_dict["response_format"] = {"type": "json_object"}
        
        return ModelFactory.create(
            model_platform=self.chat_options.model_platform,
            model_type=model_type,
            model_config_dict=model_config_dict if model_config_dict else None,
            api_key=self.chat_options.api_key,
            url=self.chat_options.api_url,
            timeout=120,  # Longer timeout for extraction
        )
    
    async def _call_llm_for_extraction(
        self,
        messages: List[Dict[str, str]],
        model_override: Optional[str] = None,
    ) -> str:
        """
        Call LLM with JSON mode for structured extraction.
        
        Args:
            messages: List of message dicts with role/content
            model_override: Optional model override
            
        Returns:
            JSON string response from LLM
        """
        model = self._create_llm_model(model_override)
        
        # Build messages for the model
        from camel.messages import BaseMessage
        from camel.agents import ChatAgent
        
        system_msg = None
        user_content = ""
        
        for msg in messages:
            if msg["role"] == "system":
                system_msg = msg["content"]
            elif msg["role"] == "user":
                user_content = msg["content"]
        
        # Configure JSON mode via model config
        # Note: JSON mode must be set at model creation time for some platforms
        agent = ChatAgent(
            system_message=system_msg or "You are a resume parsing assistant.",
            model=model,
        )
        
        user_msg = BaseMessage.make_user_message(
            role_name="User",
            content=user_content,
        )
        
        response = await agent.astep(user_msg)
        return response.msg.content
    
    def parse_resume_file(
        self,
        file_path: str,
    ) -> str:
        """
        Parse a resume file and extract structured information.
        
        Supports PDF, DOCX, and TXT formats. Extracts:
        - Contact information (name, email, phone)
        - Summary/objective
        - Skills
        - Work experience
        - Education
        - Certifications
        
        Args:
            file_path: Path to the resume file (PDF, DOCX, or TXT)
            
        Returns:
            JSON string with parsed resume data
        """
        file_path = Path(file_path)
        
        if not file_path.exists():
            return json.dumps({
                "status": "error",
                "message": f"File not found: {file_path}"
            })
        
        try:
            # Extract text based on file type
            suffix = file_path.suffix.lower()
            
            if suffix == '.pdf':
                text = self._extract_text_from_pdf(file_path)
            elif suffix in ['.docx', '.doc']:
                text = self._extract_text_from_docx(file_path)
            elif suffix in ['.txt', '.md']:
                with open(file_path, 'r', encoding='utf-8') as f:
                    text = f.read()
            else:
                return json.dumps({
                    "status": "error",
                    "message": f"Unsupported file format: {suffix}"
                })
            
            # Parse the extracted text
            parsed = self._parse_resume_text(text)
            parsed['raw_text'] = text
            parsed['source_file'] = str(file_path)
            
            logger.info(f"Parsed resume from {file_path}")
            
            return json.dumps({
                "status": "success",
                "resume": parsed,
            }, indent=2)
            
        except Exception as e:
            logger.error(f"Error parsing resume: {e}")
            return json.dumps({
                "status": "error",
                "message": str(e)
            })
    
    async def extract_resume_to_yaml(
        self,
        file_path: str,
        force_refresh: bool = False,
        model: Optional[str] = None,
    ) -> str:
        """
        Extract structured resume data and convert to YAML format.
        
        Uses LLM with JSON mode to extract comprehensive structured data from
        a resume file, then converts to AIHawk-compatible YAML format. Results
        are cached by file hash for efficient reuse.
        
        The output YAML matches the AIHawk plain_text_resume schema and can be
        directly used with ResumeTailorToolkit for job-specific tailoring.
        
        Args:
            file_path: Path to the resume file (PDF, DOCX, or TXT)
            force_refresh: If True, bypass cache and re-extract. Default False.
            model: Optional LLM model override. Defaults to chat_options model.
            
        Returns:
            JSON string with status, yaml content, and metadata:
            {
                "status": "success" | "partial" | "failed",
                "yaml": "extracted YAML content",
                "file_hash": "sha256 hash",
                "cached": true/false,
                "error": null | "error message"
            }
        """
        file_path = Path(file_path)
        
        if not file_path.exists():
            return json.dumps({
                "status": "failed",
                "yaml": "",
                "error": f"File not found: {file_path}"
            })
        
        try:
            cache = self._get_resume_cache()
            file_hash = cache.compute_file_hash(str(file_path))
            
            # Check cache first (unless force_refresh)
            if not force_refresh:
                cached_entry = cache.get(file_hash)
                if cached_entry:
                    logger.info(f"Using cached resume extraction for {file_path.name}")
                    return json.dumps({
                        "status": cached_entry.get("extraction_status", "success"),
                        "yaml": cached_entry.get("extracted_yaml", ""),
                        "file_hash": file_hash,
                        "cached": True,
                        "error": cached_entry.get("error_message"),
                    })
            
            # Extract raw text from file
            suffix = file_path.suffix.lower()
            
            if suffix == '.pdf':
                raw_text = self._extract_text_from_pdf(file_path)
            elif suffix in ['.docx', '.doc']:
                raw_text = self._extract_text_from_docx(file_path)
            elif suffix in ['.txt', '.md']:
                with open(file_path, 'r', encoding='utf-8') as f:
                    raw_text = f.read()
            else:
                return json.dumps({
                    "status": "failed",
                    "yaml": "",
                    "error": f"Unsupported file format: {suffix}"
                })
            
            if not raw_text.strip():
                return json.dumps({
                    "status": "failed",
                    "yaml": "",
                    "error": "No text content extracted from file"
                })
            
            # LLM extraction with retry logic
            extraction_result = await self._extract_with_llm(
                raw_text=raw_text,
                model_override=model,
            )
            
            # Cache the result
            cache.set(
                file_hash=file_hash,
                original_filename=file_path.name,
                extracted_yaml=extraction_result["yaml"],
                extraction_status=extraction_result["status"],
                error_message=extraction_result.get("error"),
                model_used=model or (self.chat_options.model_type if self.chat_options else None),
            )
            
            logger.info(f"Extracted resume to YAML: {file_path.name} ({extraction_result['status']})")
            
            return json.dumps({
                "status": extraction_result["status"],
                "yaml": extraction_result["yaml"],
                "file_hash": file_hash,
                "cached": False,
                "error": extraction_result.get("error"),
            })
            
        except Exception as e:
            logger.error(f"Error extracting resume to YAML: {e}")
            return json.dumps({
                "status": "failed",
                "yaml": "",
                "error": str(e)
            })
    
    async def _extract_with_llm(
        self,
        raw_text: str,
        model_override: Optional[str] = None,
        section_mode: bool = True,
    ) -> Dict[str, Any]:
        """
        Perform LLM extraction with section-based parallel processing.
        
        When section_mode=True (default), splits resume into sections and
        extracts each in parallel for better accuracy and token efficiency.
        Falls back to full extraction if section detection fails.
        
        Args:
            raw_text: Raw resume text to extract from
            model_override: Optional model override
            section_mode: Use parallel section extraction (default True)
            
        Returns:
            Dict with 'status', 'yaml', and optionally 'error'
        """
        if section_mode:
            result = await self._extract_sections_parallel(raw_text, model_override)
            if result["status"] != "failed":
                return result
            logger.warning("Section extraction failed, falling back to full extraction")
        
        return await self._extract_full_resume(raw_text, model_override)
    
    async def _extract_sections_parallel(
        self,
        raw_text: str,
        model_override: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Extract resume sections in parallel for better accuracy.
        
        Splits resume into sections, extracts each in parallel,
        then merges results. Falls back to full extraction if
        section detection fails.
        """
        sections = split_resume_sections(raw_text)
        detected = get_detected_sections(raw_text)
        
        logger.info(f"Detected {len(detected)} sections: {detected}")
        
        # If few sections detected, fallback to full extraction
        if len(detected) < 2:
            logger.info("Few sections detected, using full extraction")
            return await self._extract_full_resume(raw_text, model_override)
        
        # Extract sections in parallel
        async def extract_section(section_name: str, section_text: str) -> tuple:
            try:
                messages = get_section_extraction_messages(section_name, section_text)
                response = await self._call_llm_for_extraction(messages, model_override)
                parsed = json.loads(response)
                logger.debug(f"Section {section_name} extracted successfully")
                return section_name, parsed
            except Exception as e:
                logger.warning(f"Section {section_name} extraction failed: {e}")
                return section_name, {}
        
        # Build extraction tasks
        tasks = []
        
        # Always extract header as personal_information
        if "header" in sections:
            tasks.append(extract_section("personal_information", sections["header"]))
        
        # Extract detected sections
        for section_name in detected:
            if section_name in sections:
                tasks.append(extract_section(section_name, sections[section_name]))
        
        # Run in parallel
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Merge results
        section_data = {}
        for result in results:
            if isinstance(result, tuple) and len(result) == 2:
                section_name, data = result
                if data:
                    section_data[section_name] = data
        
        if not section_data:
            return {
                "status": "failed",
                "yaml": "",
                "error": "No sections extracted successfully",
            }
        
        # Build resume from merged data
        try:
            resume = PlainTextResume.merge_sections(section_data)
            return {
                "status": "success",
                "yaml": resume.to_yaml(),
                "sections_extracted": list(section_data.keys()),
            }
        except Exception as e:
            logger.error(f"Failed to merge sections: {e}")
            return {
                "status": "failed",
                "yaml": "",
                "error": str(e),
            }
    
    async def _extract_full_resume(
        self,
        raw_text: str,
        model_override: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Extract full resume in single LLM call (fallback method).
        
        Uses standard prompt first, retries with strict prompt if needed.
        """
        # First attempt with standard prompt
        messages = get_extraction_messages(raw_text, strict=False)
        
        try:
            response_json = await self._call_llm_for_extraction(messages, model_override)
            
            # Parse and validate JSON response
            parsed_data = json.loads(response_json)
            resume = PlainTextResume.from_dict(parsed_data)
            yaml_output = resume.to_yaml()
            
            return {
                "status": "success",
                "yaml": yaml_output,
            }
            
        except (json.JSONDecodeError, Exception) as first_error:
            logger.warning(f"First extraction attempt failed: {first_error}, retrying with strict prompt")
            
            # Retry with strict prompt
            messages_strict = get_extraction_messages(raw_text, strict=True)
            
            try:
                response_json = await self._call_llm_for_extraction(messages_strict, model_override)
                
                # Parse and validate
                parsed_data = json.loads(response_json)
                resume = PlainTextResume.from_dict(parsed_data)
                yaml_output = resume.to_yaml()
                
                return {
                    "status": "success",
                    "yaml": yaml_output,
                }
                
            except (json.JSONDecodeError, Exception) as second_error:
                logger.error(f"Both extraction attempts failed: {second_error}")
                
                # Return partial result with raw text fallback
                # Create minimal resume with just raw text info
                fallback_resume = PlainTextResume(
                    personal_information=self._extract_basic_info(raw_text),
                )
                
                return {
                    "status": "partial",
                    "yaml": fallback_resume.to_yaml(),
                    "error": f"LLM extraction failed, using basic extraction. Error: {str(second_error)}",
                }
    
    def _extract_basic_info(self, text: str) -> "PersonalInformation":
        """Extract basic info using regex as fallback."""
        from app.model.plain_text_resume import PersonalInformation
        
        # Basic regex extraction (similar to _parse_resume_text)
        email = ""
        phone = ""
        name = ""
        
        email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', text)
        if email_match:
            email = email_match.group()
        
        phone_match = re.search(r'[\+]?[(]?[0-9]{1,3}[)]?[-\s\.]?[(]?[0-9]{1,4}[)]?[-\s\.]?[0-9]{1,4}[-\s\.]?[0-9]{1,9}', text)
        if phone_match:
            phone = phone_match.group()
        
        # Name: first non-empty line that's not email/phone
        lines = text.split('\n')
        for line in lines[:5]:
            line = line.strip()
            if line and not re.search(r'[@\d]', line) and len(line) < 50:
                # Try to split into first/last name
                parts = line.split()
                if len(parts) >= 2:
                    name = parts[0]
                    surname = " ".join(parts[1:])
                else:
                    name = line
                    surname = ""
                break
        else:
            surname = ""
        
        return PersonalInformation(
            name=name,
            surname=surname if 'surname' in dir() else "",
            email=email,
            phone=phone,
        )
    
    def _extract_text_from_pdf(self, file_path: Path) -> str:
        """Extract text from PDF file"""
        try:
            from PyPDF2 import PdfReader
            
            reader = PdfReader(str(file_path))
            text_parts = []
            
            for page in reader.pages:
                text_parts.append(page.extract_text() or "")
            
            return "\n".join(text_parts)
            
        except ImportError:
            # Fallback to pdfminer
            try:
                from pdfminer.high_level import extract_text
                return extract_text(str(file_path))
            except ImportError:
                raise ImportError("No PDF library available. Install PyPDF2 or pdfminer.six")
    
    def _extract_text_from_docx(self, file_path: Path) -> str:
        """Extract text from DOCX file"""
        try:
            from docx import Document
            
            doc = Document(str(file_path))
            paragraphs = [p.text for p in doc.paragraphs]
            
            return "\n".join(paragraphs)
            
        except ImportError:
            raise ImportError("python-docx not installed. Run: pip install python-docx")
    
    def _parse_resume_text(self, text: str) -> Dict[str, Any]:
        """Parse resume text into structured data"""
        result = {
            "name": "",
            "email": "",
            "phone": "",
            "summary": "",
            "skills": [],
            "experience": [],
            "education": [],
            "certifications": [],
        }
        
        # Extract email
        email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', text)
        if email_match:
            result["email"] = email_match.group()
        
        # Extract phone
        phone_match = re.search(r'[\+]?[(]?[0-9]{1,3}[)]?[-\s\.]?[(]?[0-9]{1,4}[)]?[-\s\.]?[0-9]{1,4}[-\s\.]?[0-9]{1,9}', text)
        if phone_match:
            result["phone"] = phone_match.group()
        
        # Extract skills (common pattern: "Skills: skill1, skill2, ...")
        skills_section = re.search(r'(?:skills|technical skills|core competencies)[:\s]*([^\n]+(?:\n(?![A-Z])[^\n]+)*)', text, re.IGNORECASE)
        if skills_section:
            skills_text = skills_section.group(1)
            # Split by common delimiters
            skills = re.split(r'[,;•|\n]', skills_text)
            result["skills"] = [s.strip() for s in skills if s.strip() and len(s.strip()) > 2]
        
        # Extract name (usually first non-empty line or before contact info)
        lines = text.split('\n')
        for line in lines[:5]:
            line = line.strip()
            if line and not re.search(r'[@\d]', line) and len(line) < 50:
                result["name"] = line
                break
        
        return result
    
    def extract_job_requirements(
        self,
        job_description: str,
    ) -> str:
        """
        Extract structured requirements from a job description.
        
        Extracts:
        - Required skills (must-have)
        - Preferred skills (nice-to-have)
        - Experience requirements (years)
        - Education requirements
        - Key responsibilities
        - Keywords for ATS
        
        Args:
            job_description: Full text of the job description
            
        Returns:
            JSON string with extracted requirements
        """
        try:
            requirements = {
                "required_skills": [],
                "preferred_skills": [],
                "experience_years": None,
                "education_requirement": "",
                "responsibilities": [],
                "keywords": [],
            }
            
            text_lower = job_description.lower()
            
            # Extract experience years
            exp_patterns = [
                r'(\d+)\+?\s*(?:years?|yrs?)\s*(?:of)?\s*experience',
                r'experience[:\s]*(\d+)\+?\s*(?:years?|yrs?)',
            ]
            for pattern in exp_patterns:
                match = re.search(pattern, text_lower)
                if match:
                    requirements["experience_years"] = int(match.group(1))
                    break
            
            # Extract education
            edu_patterns = [
                r"bachelor'?s?\s*(?:degree)?(?:\s*in\s*[\w\s]+)?",
                r"master'?s?\s*(?:degree)?(?:\s*in\s*[\w\s]+)?",
                r"ph\.?d\.?(?:\s*in\s*[\w\s]+)?",
                r"(?:bs|ba|ms|ma|mba|phd)\s*(?:in\s*[\w\s]+)?",
            ]
            for pattern in edu_patterns:
                match = re.search(pattern, text_lower)
                if match:
                    requirements["education_requirement"] = match.group().strip()
                    break
            
            # Extract skills (from "Requirements" or "Qualifications" sections)
            skills_section = re.search(
                r'(?:requirements|qualifications|skills|must have)[:\s]*\n((?:[-•*]\s*[^\n]+\n?)+)',
                text_lower,
                re.IGNORECASE
            )
            if skills_section:
                skills_text = skills_section.group(1)
                skill_items = re.findall(r'[-•*]\s*([^\n]+)', skills_text)
                requirements["required_skills"] = [s.strip() for s in skill_items[:10]]
            
            # Extract preferred/nice-to-have skills
            preferred_section = re.search(
                r'(?:preferred|nice to have|bonus|plus)[:\s]*\n((?:[-•*]\s*[^\n]+\n?)+)',
                text_lower,
                re.IGNORECASE
            )
            if preferred_section:
                pref_text = preferred_section.group(1)
                pref_items = re.findall(r'[-•*]\s*([^\n]+)', pref_text)
                requirements["preferred_skills"] = [s.strip() for s in pref_items[:10]]
            
            # Extract common tech keywords
            tech_keywords = [
                'python', 'java', 'javascript', 'typescript', 'react', 'node', 'angular',
                'vue', 'aws', 'azure', 'gcp', 'docker', 'kubernetes', 'sql', 'nosql',
                'mongodb', 'postgresql', 'redis', 'git', 'ci/cd', 'agile', 'scrum',
                'machine learning', 'deep learning', 'nlp', 'computer vision',
                'tensorflow', 'pytorch', 'rest', 'graphql', 'microservices',
            ]
            found_keywords = [kw for kw in tech_keywords if kw in text_lower]
            requirements["keywords"] = found_keywords
            
            logger.info(f"Extracted requirements with {len(found_keywords)} keywords")
            
            return json.dumps({
                "status": "success",
                "requirements": requirements,
            }, indent=2)
            
        except Exception as e:
            logger.error(f"Error extracting requirements: {e}")
            return json.dumps({
                "status": "error",
                "message": str(e)
            })
    
    def calculate_match_score(
        self,
        resume_skills: List[str],
        resume_experience_years: int,
        resume_education: str,
        job_required_skills: List[str],
        job_preferred_skills: List[str],
        job_experience_years: Optional[int],
        job_education: str,
        job_keywords: List[str],
    ) -> str:
        """
        Calculate match score between a resume and job requirements.
        
        Scoring breakdown:
        - Skill match (40%): Required + preferred skills overlap
        - Experience match (30%): Years of experience comparison
        - Education match (15%): Education level comparison
        - Keyword overlap (15%): ATS keyword matching
        
        Args:
            resume_skills: List of skills from resume
            resume_experience_years: Total years of experience
            resume_education: Highest education level
            job_required_skills: Required skills from job posting
            job_preferred_skills: Preferred/nice-to-have skills
            job_experience_years: Required years of experience
            job_education: Required education level
            job_keywords: Important keywords from job posting
            
        Returns:
            JSON string with detailed score breakdown
        """
        try:
            # Normalize for comparison
            resume_skills_lower = [s.lower() for s in resume_skills]
            required_lower = [s.lower() for s in job_required_skills]
            preferred_lower = [s.lower() for s in job_preferred_skills]
            keywords_lower = [k.lower() for k in job_keywords]
            
            # Skill match (40%)
            required_matches = [s for s in required_lower if any(s in rs or rs in s for rs in resume_skills_lower)]
            preferred_matches = [s for s in preferred_lower if any(s in rs or rs in s for rs in resume_skills_lower)]
            
            if required_lower:
                required_score = len(required_matches) / len(required_lower)
            else:
                required_score = 0.5  # No requirements = neutral
            
            if preferred_lower:
                preferred_score = len(preferred_matches) / len(preferred_lower)
            else:
                preferred_score = 0.5
            
            skill_score = (required_score * 0.7 + preferred_score * 0.3) * 100
            
            # Experience match (30%)
            if job_experience_years:
                if resume_experience_years >= job_experience_years:
                    experience_score = 100
                else:
                    experience_score = (resume_experience_years / job_experience_years) * 100
            else:
                experience_score = 75  # No requirement = neutral-positive
            
            # Education match (15%)
            edu_levels = {
                'phd': 4, 'doctorate': 4,
                'master': 3, 'ms': 3, 'ma': 3, 'mba': 3,
                'bachelor': 2, 'bs': 2, 'ba': 2,
                'associate': 1,
                'high school': 0, 'ged': 0,
            }
            
            resume_edu_level = 0
            job_edu_level = 0
            
            for level, score in edu_levels.items():
                if level in resume_education.lower():
                    resume_edu_level = max(resume_edu_level, score)
                if level in job_education.lower():
                    job_edu_level = max(job_edu_level, score)
            
            if job_edu_level > 0:
                if resume_edu_level >= job_edu_level:
                    education_score = 100
                else:
                    education_score = (resume_edu_level / job_edu_level) * 100
            else:
                education_score = 80  # No requirement = neutral-positive
            
            # Keyword overlap (15%)
            keyword_matches = [k for k in keywords_lower if any(k in rs for rs in resume_skills_lower)]
            if keywords_lower:
                keyword_score = (len(keyword_matches) / len(keywords_lower)) * 100
            else:
                keyword_score = 50
            
            # Calculate weighted overall score
            overall_score = (
                skill_score * self.SKILL_WEIGHT +
                experience_score * self.EXPERIENCE_WEIGHT +
                education_score * self.EDUCATION_WEIGHT +
                keyword_score * self.KEYWORD_WEIGHT
            )
            
            # Determine fit level
            if overall_score >= 80:
                fit_level = "excellent"
                interview_likelihood = "high"
            elif overall_score >= 65:
                fit_level = "good"
                interview_likelihood = "medium-high"
            elif overall_score >= 50:
                fit_level = "fair"
                interview_likelihood = "medium"
            else:
                fit_level = "poor"
                interview_likelihood = "low"
            
            # Identify missing skills
            missing_skills = [s for s in required_lower if s not in required_matches]
            
            result = {
                "status": "success",
                "overall_score": round(overall_score, 1),
                "fit_level": fit_level,
                "interview_likelihood": interview_likelihood,
                "score_breakdown": {
                    "skill_match": round(skill_score, 1),
                    "experience_match": round(experience_score, 1),
                    "education_match": round(education_score, 1),
                    "keyword_match": round(keyword_score, 1),
                },
                "matching_skills": required_matches + preferred_matches,
                "missing_skills": missing_skills,
                "keyword_overlap": keyword_matches,
            }
            
            logger.info(f"Calculated match score: {overall_score:.1f} ({fit_level})")
            
            return json.dumps(result, indent=2)
            
        except Exception as e:
            logger.error(f"Error calculating match score: {e}")
            return json.dumps({
                "status": "error",
                "message": str(e)
            })
    
    def generate_analysis_report(
        self,
        job_title: str,
        company: str,
        overall_score: float,
        score_breakdown: Dict[str, float],
        matching_skills: List[str],
        missing_skills: List[str],
        fit_level: str,
        interview_likelihood: str,
    ) -> str:
        """
        Generate a detailed analysis report in markdown format.
        
        Creates a comprehensive report including:
        - Overall match assessment
        - Score breakdown by category
        - Strengths and weaknesses
        - Recommendations for improvement
        
        Args:
            job_title: Title of the job position
            company: Company name
            overall_score: Overall match score (0-100)
            score_breakdown: Dict with skill_match, experience_match, etc.
            matching_skills: List of matching skills
            missing_skills: List of missing required skills
            fit_level: excellent, good, fair, poor
            interview_likelihood: high, medium-high, medium, low
            
        Returns:
            Markdown-formatted analysis report
        """
        try:
            report = f"""# Job Match Analysis Report

## Position: {job_title} at {company}

---

## Overall Assessment

**Match Score: {overall_score:.1f}/100** ({fit_level.upper()})

**Interview Likelihood: {interview_likelihood.upper()}**

---

## Score Breakdown

| Category | Score | Weight |
|----------|-------|--------|
| Skill Match | {score_breakdown.get('skill_match', 0):.1f}/100 | 40% |
| Experience Match | {score_breakdown.get('experience_match', 0):.1f}/100 | 30% |
| Education Match | {score_breakdown.get('education_match', 0):.1f}/100 | 15% |
| Keyword Match | {score_breakdown.get('keyword_match', 0):.1f}/100 | 15% |

---

## Strengths

"""
            # Add matching skills as strengths
            if matching_skills:
                for skill in matching_skills[:5]:
                    report += f"✅ {skill}\n"
            else:
                report += "- No significant skill matches identified\n"
            
            report += f"""
---

## Areas for Improvement

"""
            # Add missing skills
            if missing_skills:
                for skill in missing_skills[:5]:
                    report += f"⚠️ Missing: {skill}\n"
            else:
                report += "✨ No critical skill gaps identified\n"
            
            report += f"""
---

## Recommendations

"""
            # Generate recommendations based on score
            if overall_score >= 80:
                report += """1. **Strong candidate** - Apply with confidence
2. Tailor your resume to highlight matching experience
3. Prepare specific examples demonstrating your skills
"""
            elif overall_score >= 65:
                report += """1. **Competitive candidate** - Apply and emphasize transferable skills
2. Consider getting certifications for missing skills
3. Highlight relevant projects in your cover letter
"""
            elif overall_score >= 50:
                report += """1. **Potential fit** - Apply but address skill gaps
2. Emphasize willingness to learn
3. Consider upskilling in key areas before applying
"""
            else:
                report += """1. **Consider alternative roles** - This may not be the best fit
2. Focus on building missing skills
3. Look for more junior positions to gain experience
"""
            
            report += f"""
---

*Report generated on {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M')}*
"""
            
            # Save report if working directory is set
            if self.working_directory:
                report_path = Path(self.working_directory) / f"analysis_{company}_{job_title}.md".replace(" ", "_")
                with open(report_path, 'w', encoding='utf-8') as f:
                    f.write(report)
                logger.info(f"Saved analysis report to {report_path}")
            
            return json.dumps({
                "status": "success",
                "report": report,
            })
            
        except Exception as e:
            logger.error(f"Error generating report: {e}")
            return json.dumps({
                "status": "error",
                "message": str(e)
            })
    
    def get_tools(self) -> List[FunctionTool]:
        return [
            FunctionTool(self.parse_resume_file),
            FunctionTool(self.extract_resume_to_yaml),
            FunctionTool(self.extract_job_requirements),
            FunctionTool(self.calculate_match_score),
            FunctionTool(self.generate_analysis_report),
        ]
