"""
Plain Text Resume Pydantic models for structured resume extraction.

This module defines models matching the AIHawk plain_text_resume YAML schema,
enabling LLM-based extraction from raw resume text and serialization to YAML
format for resume tailoring.

All fields are Optional with empty defaults to handle partial resumes gracefully.
"""
from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field, EmailStr, HttpUrl, model_validator
import yaml
import json


class PersonalInformation(BaseModel):
    """Personal/contact information section of resume."""
    name: Optional[str] = ""
    surname: Optional[str] = ""
    date_of_birth: Optional[str] = ""
    country: Optional[str] = ""
    city: Optional[str] = ""
    address: Optional[str] = ""
    zip_code: Optional[str] = ""
    phone_prefix: Optional[str] = ""
    phone: Optional[str] = ""
    email: Optional[str] = ""
    github: Optional[str] = ""
    linkedin: Optional[str] = ""


class EducationDetail(BaseModel):
    """Single education entry."""
    education_level: Optional[str] = ""
    institution: Optional[str] = ""
    field_of_study: Optional[str] = ""
    final_evaluation_grade: Optional[str] = ""
    start_date: Optional[str] = ""
    year_of_completion: Optional[str] = ""
    exam: Optional[Dict[str, str]] = Field(default_factory=dict)


class Responsibility(BaseModel):
    """Single responsibility item with key-value structure."""
    responsibility: Optional[str] = ""


class ExperienceDetail(BaseModel):
    """Single work experience entry."""
    position: Optional[str] = ""
    company: Optional[str] = ""
    employment_period: Optional[str] = ""
    location: Optional[str] = ""
    industry: Optional[str] = ""
    key_responsibilities: Optional[List[Dict[str, str]]] = Field(default_factory=list)
    skills_acquired: Optional[List[str]] = Field(default_factory=list)


class Project(BaseModel):
    """Single project entry."""
    name: Optional[str] = ""
    description: Optional[str] = ""
    link: Optional[str] = ""


class Achievement(BaseModel):
    """Single achievement entry."""
    name: Optional[str] = ""
    description: Optional[str] = ""


class Certification(BaseModel):
    """Single certification entry."""
    name: Optional[str] = ""
    description: Optional[str] = ""


class Language(BaseModel):
    """Single language entry."""
    language: Optional[str] = ""
    proficiency: Optional[str] = ""


class Availability(BaseModel):
    """Availability information."""
    notice_period: Optional[str] = ""


class SalaryExpectations(BaseModel):
    """Salary expectations."""
    salary_range_usd: Optional[str] = ""


class SelfIdentification(BaseModel):
    """Self-identification information (EEO data)."""
    gender: Optional[str] = ""
    pronouns: Optional[str] = ""
    veteran: Optional[str] = ""
    disability: Optional[str] = ""
    ethnicity: Optional[str] = ""


class LegalAuthorization(BaseModel):
    """Legal work authorization details."""
    eu_work_authorization: Optional[str] = ""
    us_work_authorization: Optional[str] = ""
    requires_us_visa: Optional[str] = ""
    requires_us_sponsorship: Optional[str] = ""
    requires_eu_visa: Optional[str] = ""
    legally_allowed_to_work_in_eu: Optional[str] = ""
    legally_allowed_to_work_in_us: Optional[str] = ""
    requires_eu_sponsorship: Optional[str] = ""
    canada_work_authorization: Optional[str] = ""
    requires_canada_visa: Optional[str] = ""
    legally_allowed_to_work_in_canada: Optional[str] = ""
    requires_canada_sponsorship: Optional[str] = ""
    uk_work_authorization: Optional[str] = ""
    requires_uk_visa: Optional[str] = ""
    legally_allowed_to_work_in_uk: Optional[str] = ""
    requires_uk_sponsorship: Optional[str] = ""


class WorkPreferencesProfile(BaseModel):
    """Work preferences section for resume profile."""
    remote_work: Optional[str] = ""
    in_person_work: Optional[str] = ""
    open_to_relocation: Optional[str] = ""
    willing_to_complete_assessments: Optional[str] = ""
    willing_to_undergo_drug_tests: Optional[str] = ""
    willing_to_undergo_background_checks: Optional[str] = ""


class PlainTextResume(BaseModel):
    """
    Root model for structured plain text resume.
    
    Matches AIHawk's plain_text_resume YAML schema for seamless integration
    with resume tailoring and job application automation.
    
    Usage:
        # From dict (e.g., LLM JSON output)
        resume = PlainTextResume.from_dict(llm_response)
        
        # To YAML for AIHawk
        yaml_str = resume.to_yaml()
        
        # From YAML file
        resume = PlainTextResume.from_yaml(yaml_content)
        
        # Get JSON schema for LLM extraction prompt
        schema = PlainTextResume.get_extraction_schema()
    """
    personal_information: Optional[PersonalInformation] = Field(default_factory=PersonalInformation)
    education_details: Optional[List[EducationDetail]] = Field(default_factory=list)
    experience_details: Optional[List[ExperienceDetail]] = Field(default_factory=list)
    projects: Optional[List[Project]] = Field(default_factory=list)
    achievements: Optional[List[Achievement]] = Field(default_factory=list)
    certifications: Optional[List[Certification]] = Field(default_factory=list)
    languages: Optional[List[Language]] = Field(default_factory=list)
    interests: Optional[List[str]] = Field(default_factory=list)
    availability: Optional[Availability] = Field(default_factory=Availability)
    salary_expectations: Optional[SalaryExpectations] = Field(default_factory=SalaryExpectations)
    self_identification: Optional[SelfIdentification] = Field(default_factory=SelfIdentification)
    legal_authorization: Optional[LegalAuthorization] = Field(default_factory=LegalAuthorization)
    work_preferences: Optional[WorkPreferencesProfile] = Field(default_factory=WorkPreferencesProfile)
    
    @model_validator(mode='before')
    @classmethod
    def handle_none_values(cls, data: Any) -> Any:
        """Convert None values to empty defaults."""
        if isinstance(data, dict):
            # Convert None to empty dict for nested models
            for key in ['personal_information', 'availability', 'salary_expectations',
                       'self_identification', 'legal_authorization', 'work_preferences']:
                if data.get(key) is None:
                    data[key] = {}
            # Convert None to empty list for list fields
            for key in ['education_details', 'experience_details', 'projects',
                       'achievements', 'certifications', 'languages', 'interests']:
                if data.get(key) is None:
                    data[key] = []
        return data
    
    def to_yaml(self) -> str:
        """
        Serialize to YAML string for AIHawk consumption.
        
        Returns:
            YAML-formatted string matching plain_text_resume schema
        """
        # Convert to dict, excluding None values
        data = self.model_dump(exclude_none=True, exclude_unset=False)
        
        # Clean up empty values for cleaner YAML output
        data = self._clean_empty_values(data)
        
        return yaml.dump(data, default_flow_style=False, allow_unicode=True, sort_keys=False)
    
    def _clean_empty_values(self, data: Any) -> Any:
        """Recursively remove empty strings and empty lists from dict."""
        if isinstance(data, dict):
            return {
                k: self._clean_empty_values(v)
                for k, v in data.items()
                if v not in (None, "", []) and self._clean_empty_values(v) not in (None, "", [], {})
            }
        elif isinstance(data, list):
            cleaned = [self._clean_empty_values(item) for item in data if item not in (None, "", [])]
            return [item for item in cleaned if item not in (None, "", [], {})]
        return data
    
    @classmethod
    def from_yaml(cls, yaml_str: str) -> "PlainTextResume":
        """
        Parse from YAML string.
        
        Args:
            yaml_str: YAML content matching plain_text_resume schema
            
        Returns:
            PlainTextResume instance
        """
        data = yaml.safe_load(yaml_str)
        return cls.from_dict(data)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PlainTextResume":
        """
        Create from dictionary (e.g., LLM JSON response).
        
        Args:
            data: Dictionary matching model structure
            
        Returns:
            PlainTextResume instance
        """
        if data is None:
            data = {}
        return cls.model_validate(data)
    
    @classmethod
    def merge_sections(cls, section_results: Dict[str, Dict]) -> "PlainTextResume":
        """
        Merge extracted section results into a unified PlainTextResume.
        
        Args:
            section_results: Dict mapping section names to extracted data dicts
            
        Returns:
            Merged PlainTextResume instance
        """
        merged = {}
        
        for section_name, data in section_results.items():
            if data and isinstance(data, dict):
                merged.update(data)
        
        return cls.from_dict(merged)
    
    @classmethod
    def get_extraction_schema(cls) -> Dict[str, Any]:
        """
        Get JSON schema for LLM extraction prompts.
        
        Returns:
            JSON schema dict describing the expected structure
        """
        return cls.model_json_schema()
    
    @classmethod
    def get_extraction_schema_simplified(cls) -> str:
        """
        Get simplified human-readable schema for LLM prompts.
        
        Returns:
            Simplified schema description string
        """
        return """
{
  "personal_information": {
    "name": "First name",
    "surname": "Last name", 
    "date_of_birth": "Date of birth or null",
    "country": "Country",
    "city": "City",
    "address": "Street address or null",
    "zip_code": "Postal/ZIP code or null",
    "phone_prefix": "Phone country code e.g. +1",
    "phone": "Phone number",
    "email": "Email address",
    "github": "GitHub profile URL or null",
    "linkedin": "LinkedIn profile URL or null"
  },
  "education_details": [
    {
      "education_level": "e.g. Bachelor's Degree, Master's Degree, PhD",
      "institution": "School/University name",
      "field_of_study": "Major/Field",
      "final_evaluation_grade": "GPA or grade or null",
      "start_date": "Start date or null",
      "year_of_completion": "Graduation year",
      "exam": {"Course Name": "Grade"} or null
    }
  ],
  "experience_details": [
    {
      "position": "Job title",
      "company": "Company name",
      "employment_period": "e.g. Jan 2020 - Present",
      "location": "City, Country",
      "industry": "Industry sector",
      "key_responsibilities": [
        {"responsibility_1": "Description of responsibility"},
        {"responsibility_2": "Description of responsibility"}
      ],
      "skills_acquired": ["Skill 1", "Skill 2"]
    }
  ],
  "projects": [
    {
      "name": "Project name",
      "description": "Project description",
      "link": "Project URL or null"
    }
  ],
  "achievements": [
    {
      "name": "Achievement name",
      "description": "Achievement description"
    }
  ],
  "certifications": [
    {
      "name": "Certification name",
      "description": "Issuing organization, date, etc."
    }
  ],
  "languages": [
    {
      "language": "Language name",
      "proficiency": "e.g. Native, Fluent, Professional, Conversational"
    }
  ],
  "interests": ["Interest 1", "Interest 2"],
  "availability": {
    "notice_period": "e.g. 2 weeks, Immediately available"
  },
  "salary_expectations": {
    "salary_range_usd": "e.g. $80,000 - $100,000 or null"
  },
  "self_identification": {
    "gender": "Gender or null",
    "pronouns": "Pronouns or null",
    "veteran": "Yes/No or null",
    "disability": "Yes/No or null",
    "ethnicity": "Ethnicity or null"
  },
  "legal_authorization": {
    "eu_work_authorization": "Yes/No",
    "us_work_authorization": "Yes/No",
    "requires_us_visa": "Yes/No",
    "requires_us_sponsorship": "Yes/No",
    "requires_eu_visa": "Yes/No",
    "legally_allowed_to_work_in_eu": "Yes/No",
    "legally_allowed_to_work_in_us": "Yes/No",
    "requires_eu_sponsorship": "Yes/No",
    "canada_work_authorization": "Yes/No",
    "requires_canada_visa": "Yes/No",
    "legally_allowed_to_work_in_canada": "Yes/No",
    "requires_canada_sponsorship": "Yes/No",
    "uk_work_authorization": "Yes/No",
    "requires_uk_visa": "Yes/No",
    "legally_allowed_to_work_in_uk": "Yes/No",
    "requires_uk_sponsorship": "Yes/No"
  },
  "work_preferences": {
    "remote_work": "Yes/No",
    "in_person_work": "Yes/No",
    "open_to_relocation": "Yes/No",
    "willing_to_complete_assessments": "Yes/No",
    "willing_to_undergo_drug_tests": "Yes/No",
    "willing_to_undergo_background_checks": "Yes/No"
  }
}
"""
