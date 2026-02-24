"""
Resume Extraction Prompts for LLM-based structured extraction.

Provides prompt templates for extracting structured resume data from
raw text using JSON mode output. Includes both standard and strict
prompts for retry logic, as well as section-specific prompts for
parallel extraction.
"""
import re
from typing import Dict, List, Tuple, Optional
from app.model.plain_text_resume import PlainTextResume


# =============================================================================
# Section Detection and Splitting
# =============================================================================

# Common section headers in resumes (case-insensitive)
SECTION_PATTERNS = {
    "personal_information": [
        r"^(contact|personal\s*info|about\s*me|profile|summary|objective)",
    ],
    "experience_details": [
        r"^(work\s*experience|experience|employment|professional\s*experience|work\s*history|career)",
    ],
    "education_details": [
        r"^(education|academic|qualifications|degrees?|schooling)",
    ],
    "skills": [
        r"^(skills|technical\s*skills|core\s*competencies|technologies|expertise|proficiencies)",
    ],
    "projects": [
        r"^(projects?|portfolio|personal\s*projects|side\s*projects)",
    ],
    "certifications": [
        r"^(certifications?|certificates?|credentials|licenses?|professional\s*development)",
    ],
    "achievements": [
        r"^(achievements?|awards?|honors?|accomplishments?|recognition)",
    ],
    "languages": [
        r"^(languages?|language\s*skills)",
    ],
    "interests": [
        r"^(interests?|hobbies|activities|extracurricular)",
    ],
}


def split_resume_sections(resume_text: str) -> Dict[str, str]:
    """
    Split resume text into logical sections based on headers.
    
    Args:
        resume_text: Full resume text
        
    Returns:
        Dict mapping section names to their text content.
        Always includes 'full_text' with the complete resume.
        'header' contains content before first section (usually contact info).
    """
    sections = {
        "full_text": resume_text,
        "header": "",  # First part before any section header (usually contact info)
    }
    
    lines = resume_text.split('\n')
    current_section = "header"
    current_content = []
    
    for line in lines:
        stripped = line.strip()
        
        # Check if line is a section header
        section_found = None
        for section_name, patterns in SECTION_PATTERNS.items():
            for pattern in patterns:
                if re.match(pattern, stripped, re.IGNORECASE):
                    section_found = section_name
                    break
            if section_found:
                break
        
        if section_found:
            # Save previous section
            if current_content:
                content_text = '\n'.join(current_content)
                if current_section in sections and sections[current_section]:
                    sections[current_section] += '\n' + content_text
                else:
                    sections[current_section] = content_text
            
            current_section = section_found
            current_content = [line]
        else:
            current_content.append(line)
    
    # Save final section
    if current_content:
        content_text = '\n'.join(current_content)
        if current_section in sections and sections[current_section]:
            sections[current_section] += '\n' + content_text
        else:
            sections[current_section] = content_text
    
    # Clean up empty sections
    sections = {k: v.strip() for k, v in sections.items() if v.strip()}
    
    # Merge header into personal_information if both exist
    # (header typically contains name/contact before any section header)
    if "header" in sections and sections["header"]:
        if "personal_information" in sections:
            # Prepend header to personal_information
            sections["personal_information"] = sections["header"] + "\n\n" + sections["personal_information"]
        else:
            # Header IS the personal_information
            sections["personal_information"] = sections["header"]
        del sections["header"]
    
    return sections


def get_detected_sections(resume_text: str) -> List[str]:
    """Get list of section names detected in resume."""
    sections = split_resume_sections(resume_text)
    return [k for k in sections.keys() if k not in ('full_text', 'header', 'other')]


# =============================================================================
# Section-Specific Schemas (Token-Optimized ~70% smaller)
# =============================================================================

SECTION_SCHEMAS = {
    "personal_information": '''{
  "personal_information": {
    "name": "First name", "surname": "Last name",
    "country": "Country", "city": "City",
    "phone_prefix": "+1", "phone": "Phone number",
    "email": "Email", "github": "GitHub URL or null", "linkedin": "LinkedIn URL or null"
  }
}''',
    
    "experience_details": '''{
  "experience_details": [{
    "position": "Job title", "company": "Company",
    "employment_period": "Jan 2020 - Present", "location": "City, Country",
    "key_responsibilities": [{"responsibility_1": "..."}],
    "skills_acquired": ["Skill 1"]
  }]
}''',
    
    "education_details": '''{
  "education_details": [{
    "education_level": "Bachelor's/Master's/PhD",
    "institution": "University name", "field_of_study": "Major",
    "year_of_completion": "2020"
  }]
}''',
    
    "projects": '''{
  "projects": [{"name": "Project name", "description": "Description", "link": "URL or null"}]
}''',
    
    "certifications": '''{
  "certifications": [{"name": "Cert name", "description": "Issuer, date"}]
}''',
    
    "achievements": '''{
  "achievements": [{"name": "Achievement", "description": "Details"}]
}''',
    
    "languages": '''{
  "languages": [{"language": "Language", "proficiency": "Native/Fluent/Professional"}]
}''',
    
    "interests": '{"interests": ["Interest 1", "Interest 2"]}',
}


# =============================================================================
# Section-Specific Prompts
# =============================================================================

SECTION_SYSTEM_PROMPT = """Extract ONLY {section_name} from the resume section. Output valid JSON.
Schema: {schema}
Rules: Use null for missing fields, [] for empty lists. No fabrication."""

SECTION_USER_PROMPT = """Extract {section_name}:
---
{section_text}
---
Output JSON only."""


def get_section_extraction_messages(
    section_name: str,
    section_text: str,
) -> List[Dict[str, str]]:
    """Get messages for extracting a specific resume section."""
    schema = SECTION_SCHEMAS.get(section_name, SECTION_SCHEMAS.get("personal_information"))
    readable_name = section_name.replace("_", " ").title()
    
    system_prompt = SECTION_SYSTEM_PROMPT.replace("{section_name}", readable_name)
    system_prompt = system_prompt.replace("{schema}", schema)
    
    user_prompt = SECTION_USER_PROMPT.replace("{section_name}", readable_name)
    user_prompt = user_prompt.replace("{section_text}", section_text)
    
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


# =============================================================================
# Full Resume Extraction Prompts (Original - kept for fallback)
# =============================================================================

EXTRACTION_SYSTEM_PROMPT = """You are a professional resume parser. Your task is to extract structured information from a resume and output it as valid JSON matching the provided schema.

## Instructions:
1. Extract ALL information present in the resume into the appropriate fields
2. Use null for fields that are not mentioned or cannot be determined
3. Use empty arrays [] for list fields with no entries
4. Preserve the original wording for responsibilities and descriptions
5. For dates, use the format provided in the resume (e.g., "Jan 2020 - Present")
6. For experience responsibilities, format as [{"responsibility_1": "..."}, {"responsibility_2": "..."}]
7. Infer reasonable values where obvious (e.g., country from city names)

## Schema:
{schema}

## Important:
- Output ONLY valid JSON, no markdown code blocks or explanations
- Ensure all string values are properly escaped
- Do not fabricate information not present in the resume
"""

EXTRACTION_SYSTEM_PROMPT_STRICT = """You are a professional resume parser. Your task is to extract structured information from a resume and output it as valid JSON.

## CRITICAL REQUIREMENTS:
1. You MUST output ONLY valid JSON - no text before or after
2. You MUST NOT include markdown code blocks (no ```)
3. Use null for ANY field not explicitly mentioned in the resume
4. Use [] for list fields with no data
5. Do NOT fabricate, infer, or guess any information

## Output Schema (follow EXACTLY):
{schema}

## Response Format:
Start directly with {{ and end with }}. Nothing else.
"""

EXTRACTION_USER_PROMPT = """Extract structured information from the following resume text:

---
{resume_text}
---

Output the extracted data as a JSON object matching the schema."""


def get_extraction_messages(
    resume_text: str,
    strict: bool = False,
) -> List[Dict[str, str]]:
    """
    Get formatted messages for resume extraction LLM call.
    
    Args:
        resume_text: Raw resume text to extract from
        strict: Use stricter prompt for retry attempts
        
    Returns:
        List of message dicts with role and content
    """
    schema = PlainTextResume.get_extraction_schema_simplified()
    
    # Use string replacement instead of format() to avoid issues with JSON braces
    system_template = (
        EXTRACTION_SYSTEM_PROMPT_STRICT if strict else EXTRACTION_SYSTEM_PROMPT
    )
    system_prompt = system_template.replace("{schema}", schema)
    
    user_prompt = EXTRACTION_USER_PROMPT.replace("{resume_text}", resume_text)
    
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


def get_extraction_prompt_tuple(
    resume_text: str,
    strict: bool = False,
) -> Tuple[str, str]:
    """
    Get extraction prompts as tuple (system, user).
    
    Args:
        resume_text: Raw resume text to extract from
        strict: Use stricter prompt for retry attempts
        
    Returns:
        Tuple of (system_prompt, user_prompt)
    """
    messages = get_extraction_messages(resume_text, strict)
    return messages[0]["content"], messages[1]["content"]


# Validation prompt for when extraction returns questionable data
VALIDATION_PROMPT = """Review the following extracted resume data and fix any obvious errors:

Extracted Data:
{extracted_json}

Original Resume Text:
{resume_text}

If the extracted data looks correct, return it unchanged.
If there are errors (wrong fields, missing obvious data, malformed structure), fix them.

Output ONLY the corrected JSON, no explanations."""


def get_validation_messages(
    extracted_json: str,
    resume_text: str,
) -> List[Dict[str, str]]:
    """
    Get messages for validating/correcting extracted resume data.
    
    Args:
        extracted_json: JSON string of extracted data
        resume_text: Original resume text for reference
        
    Returns:
        List of message dicts
    """
    # Use string replacement to avoid issues with JSON braces
    content = VALIDATION_PROMPT.replace("{extracted_json}", extracted_json)
    content = content.replace("{resume_text}", resume_text[:2000])  # Truncate for token limit
    
    return [
        {
            "role": "system",
            "content": "You are a data validation assistant. Fix any errors in the extracted resume JSON. Output ONLY valid JSON."
        },
        {
            "role": "user", 
            "content": content
        },
    ]
