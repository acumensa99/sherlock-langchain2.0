"""
Job tracking system for managing video processing jobs.
"""

import json
import os
from datetime import datetime
from typing import Dict, Any, Optional
from pathlib import Path
import uuid


class JobTracker:
    """Manages job status and information using JSON file storage."""
    
    def __init__(self, jobs_file: str = "jobs.json"):
        self.jobs_file = Path(__file__).parent / jobs_file
        self.jobs = self._load_jobs()
    
    def _load_jobs(self) -> Dict[str, Any]:
        """Load jobs from JSON file."""
        if self.jobs_file.exists():
            try:
                with open(self.jobs_file, 'r') as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}
    
    def _save_jobs(self):
        """Save jobs to JSON file."""
        try:
            with open(self.jobs_file, 'w') as f:
                json.dump(self.jobs, f, indent=2, default=str)
        except Exception as e:
            print(f"Error saving jobs: {e}")
    
    def create_job(self, original_filename: str, s3_key: str) -> str:
        """
        Create a new job entry.
        
        Args:
            original_filename: Original uploaded filename
            s3_key: S3 object key where video is stored
            
        Returns:
            job_id: Unique job identifier
        """
        job_id = str(uuid.uuid4())
        
        self.jobs[job_id] = {
            "job_id": job_id,
            "original_filename": original_filename,
            "s3_key": s3_key,
            "status": "uploading",
            "rekognition_job_id": None,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "error_message": None,
            "filtered_file_path": None
        }
        
        self._save_jobs()
        return job_id
    
    def update_job_status(self, job_id: str, status: str, **kwargs):
        """
        Update job status and additional fields.
        
        Args:
            job_id: Job identifier
            status: New status (uploading, processing, completed, failed)
            **kwargs: Additional fields to update
        """
        if job_id in self.jobs:
            self.jobs[job_id]["status"] = status
            self.jobs[job_id]["updated_at"] = datetime.now().isoformat()
            
            # Update additional fields
            for key, value in kwargs.items():
                self.jobs[job_id][key] = value
            
            self._save_jobs()
    
    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get job information by ID."""
        return self.jobs.get(job_id)
    
    def get_all_jobs(self) -> Dict[str, Any]:
        """Get all jobs."""
        return self.jobs
    
    def find_job_by_rekognition_id(self, rekognition_job_id: str) -> Optional[Dict[str, Any]]:
        """Find job by Rekognition job ID."""
        for job in self.jobs.values():
            if job.get("rekognition_job_id") == rekognition_job_id:
                return job
        return None
    
    def cleanup_old_jobs(self, days: int = 7):
        """Remove jobs older than specified days."""
        cutoff_date = datetime.now().timestamp() - (days * 24 * 60 * 60)
        
        jobs_to_remove = []
        for job_id, job in self.jobs.items():
            created_at = datetime.fromisoformat(job["created_at"]).timestamp()
            if created_at < cutoff_date:
                jobs_to_remove.append(job_id)
        
        for job_id in jobs_to_remove:
            del self.jobs[job_id]
        
        if jobs_to_remove:
            self._save_jobs()