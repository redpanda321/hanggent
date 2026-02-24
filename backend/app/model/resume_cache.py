"""
Resume Cache for storing extracted YAML resumes.

Uses file-based storage with SHA256 hash-based lookup for efficient
caching of LLM-extracted resume data. Supports indefinite caching 
with optional force refresh.
"""
import hashlib
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any

from utils import traceroot_wrapper as traceroot
from app.component.environment import env

logger = traceroot.get_logger("resume_cache")


class ResumeCache:
    """
    File-based cache for extracted resume YAML.
    
    Caches extracted resumes by file content hash (SHA256) for efficient
    reuse across sessions. Cache is stored in JSON format with metadata.
    
    Cache structure:
        {cache_dir}/resume_cache/{hash[:2]}/{hash}.json
        
    Cache entry format:
        {
            "file_hash": "sha256...",
            "original_filename": "resume.pdf",
            "extracted_yaml": "yaml content...",
            "extraction_status": "success|partial|failed",
            "error_message": null | "error details",
            "created_at": "2026-01-28T12:00:00",
            "model_used": "gpt-4o"
        }
    """
    
    def __init__(self, cache_dir: Optional[str] = None):
        """
        Initialize cache with optional custom directory.
        
        Args:
            cache_dir: Custom cache directory. Defaults to ~/.hanggent/cache/resumes/
        """
        if cache_dir is None:
            cache_dir = env("resume_cache_dir", os.path.expanduser("~/.hanggent/cache/resumes/"))
        
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Resume cache initialized at {self.cache_dir}")
    
    @staticmethod
    def compute_file_hash(file_path: str) -> str:
        """
        Compute SHA256 hash of file contents.
        
        Args:
            file_path: Path to file
            
        Returns:
            Hex-encoded SHA256 hash
        """
        hasher = hashlib.sha256()
        with open(file_path, 'rb') as f:
            # Read in chunks for large files
            for chunk in iter(lambda: f.read(8192), b''):
                hasher.update(chunk)
        return hasher.hexdigest()
    
    @staticmethod
    def compute_content_hash(content: str) -> str:
        """
        Compute SHA256 hash of string content.
        
        Args:
            content: String content to hash
            
        Returns:
            Hex-encoded SHA256 hash
        """
        return hashlib.sha256(content.encode('utf-8')).hexdigest()
    
    def _get_cache_path(self, file_hash: str) -> Path:
        """Get cache file path for a hash (with 2-char prefix directory)."""
        prefix = file_hash[:2]
        return self.cache_dir / prefix / f"{file_hash}.json"
    
    def get(self, file_hash: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve cached resume by file hash.
        
        Args:
            file_hash: SHA256 hash of original file
            
        Returns:
            Cache entry dict or None if not found
        """
        cache_path = self._get_cache_path(file_hash)
        
        if not cache_path.exists():
            logger.debug(f"Cache miss for hash: {file_hash[:16]}...")
            return None
        
        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                entry = json.load(f)
            logger.info(f"Cache hit for hash: {file_hash[:16]}...")
            return entry
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Failed to read cache entry: {e}")
            return None
    
    def get_by_file(self, file_path: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve cached resume by file path (computes hash).
        
        Args:
            file_path: Path to original resume file
            
        Returns:
            Cache entry dict or None if not found
        """
        file_hash = self.compute_file_hash(file_path)
        return self.get(file_hash)
    
    def set(
        self,
        file_hash: str,
        original_filename: str,
        extracted_yaml: str,
        extraction_status: str = "success",
        error_message: Optional[str] = None,
        model_used: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Store extracted resume in cache.
        
        Args:
            file_hash: SHA256 hash of original file
            original_filename: Original file name (for reference)
            extracted_yaml: Extracted YAML content
            extraction_status: "success", "partial", or "failed"
            error_message: Error details if extraction failed/partial
            model_used: LLM model used for extraction
            
        Returns:
            The stored cache entry
        """
        cache_path = self._get_cache_path(file_hash)
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        
        entry = {
            "file_hash": file_hash,
            "original_filename": original_filename,
            "extracted_yaml": extracted_yaml,
            "extraction_status": extraction_status,
            "error_message": error_message,
            "created_at": datetime.utcnow().isoformat(),
            "model_used": model_used,
        }
        
        try:
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(entry, f, indent=2, ensure_ascii=False)
            logger.info(f"Cached resume extraction: {file_hash[:16]}... ({extraction_status})")
            return entry
        except IOError as e:
            logger.error(f"Failed to write cache entry: {e}")
            raise
    
    def delete(self, file_hash: str) -> bool:
        """
        Delete cached entry by hash.
        
        Args:
            file_hash: SHA256 hash of original file
            
        Returns:
            True if deleted, False if not found
        """
        cache_path = self._get_cache_path(file_hash)
        
        if cache_path.exists():
            cache_path.unlink()
            logger.info(f"Deleted cache entry: {file_hash[:16]}...")
            return True
        return False
    
    def clear(self) -> int:
        """
        Clear all cached entries.
        
        Returns:
            Number of entries deleted
        """
        count = 0
        for json_file in self.cache_dir.rglob("*.json"):
            json_file.unlink()
            count += 1
        logger.info(f"Cleared {count} cache entries")
        return count
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.
        
        Returns:
            Dict with cache stats (count, size, etc.)
        """
        total_count = 0
        total_size = 0
        status_counts = {"success": 0, "partial": 0, "failed": 0}
        
        for json_file in self.cache_dir.rglob("*.json"):
            total_count += 1
            total_size += json_file.stat().st_size
            
            try:
                with open(json_file, 'r') as f:
                    entry = json.load(f)
                    status = entry.get("extraction_status", "unknown")
                    if status in status_counts:
                        status_counts[status] += 1
            except:
                pass
        
        return {
            "total_entries": total_count,
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "status_breakdown": status_counts,
            "cache_directory": str(self.cache_dir),
        }


# Global cache instance (lazy-loaded)
_cache_instance: Optional[ResumeCache] = None


def get_resume_cache(cache_dir: Optional[str] = None) -> ResumeCache:
    """
    Get global resume cache instance.
    
    Args:
        cache_dir: Optional custom cache directory
        
    Returns:
        ResumeCache instance
    """
    global _cache_instance
    
    if _cache_instance is None or cache_dir is not None:
        _cache_instance = ResumeCache(cache_dir)
    
    return _cache_instance
