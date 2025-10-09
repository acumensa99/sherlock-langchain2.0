"""
Video processing service that handles the complete workflow.
"""

import boto3
import os
from typing import Dict, Any, Optional
import logging
from botocore.exceptions import ClientError
from job_tracker import JobTracker
from s3_uploader import S3VideoUploader


class VideoProcessingService:
    """Manages the complete video processing workflow."""
    
    def __init__(self, config: Dict[str, Any], logger: logging.Logger):
        self.config = config
        self.logger = logger
        self.job_tracker = JobTracker()
        self.s3_uploader = S3VideoUploader(config, logger)
        
        # AWS configuration
        aws_config = config.get("aws", {})
        sns_config = aws_config.get("sns", {})
        rekognition_config = aws_config.get("rekognition", {})
        
        self.region = rekognition_config.get("region", "us-east-1")
        self.sns_topic_arn = sns_config.get("topic_arn")
        self.role_arn = sns_config.get("role_arn")
        
        # Initialize Rekognition client
        try:
            self.rekognition_client = boto3.client(
                'rekognition',
                region_name=self.region,
                aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
                aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY')
            )
        except Exception as e:
            self.logger.error(f"Failed to initialize Rekognition client: {e}")
            raise
    
    async def process_video_upload(self, file_path: str, original_filename: str) -> Dict[str, Any]:
        """
        Process uploaded video through the complete workflow.
        
        Args:
            file_path: Local path to uploaded video
            original_filename: Original filename
            
        Returns:
            Dict with job_id and status
        """
        try:
            # Generate S3 key
            s3_key = self.s3_uploader.generate_s3_key(original_filename)
            
            # Create job entry
            job_id = self.job_tracker.create_job(original_filename, s3_key)
            
            self.logger.info(f"Starting video processing for job {job_id}")
            
            # Upload to S3
            self.job_tracker.update_job_status(job_id, "uploading")
            upload_success = await self.s3_uploader.upload_video(file_path, s3_key)
            
            if not upload_success:
                self.job_tracker.update_job_status(
                    job_id, 
                    "failed", 
                    error_message="Failed to upload video to S3"
                )
                return {"job_id": job_id, "status": "failed", "error": "Upload to S3 failed"}
            
            # Start Rekognition label detection
            self.job_tracker.update_job_status(job_id, "processing")
            rekognition_job_id = await self._start_rekognition_analysis(s3_key)
            
            if not rekognition_job_id:
                self.job_tracker.update_job_status(
                    job_id, 
                    "failed", 
                    error_message="Failed to start Rekognition analysis"
                )
                return {"job_id": job_id, "status": "failed", "error": "Failed to start analysis"}
            
            # Update job with Rekognition job ID
            self.job_tracker.update_job_status(
                job_id, 
                "processing",
                rekognition_job_id=rekognition_job_id
            )
            
            self.logger.info(f"Started Rekognition analysis for job {job_id}, rekognition_job_id: {rekognition_job_id}")
            
            return {
                "job_id": job_id, 
                "status": "processing", 
                "rekognition_job_id": rekognition_job_id,
                "s3_key": s3_key
            }
            
        except Exception as e:
            self.logger.error(f"Error processing video upload: {e}")
            if 'job_id' in locals():
                self.job_tracker.update_job_status(
                    job_id, 
                    "failed", 
                    error_message=str(e)
                )
            return {"status": "failed", "error": str(e)}
    
    async def _start_rekognition_analysis(self, s3_key: str) -> Optional[str]:
        """
        Start AWS Rekognition label detection.
        
        Args:
            s3_key: S3 object key
            
        Returns:
            Rekognition job ID if successful, None otherwise
        """
        try:
            response = self.rekognition_client.start_label_detection(
                Video={
                    'S3Object': {
                        'Bucket': self.s3_uploader.bucket_name,
                        'Name': s3_key
                    }
                },
                NotificationChannel={
                    'SNSTopicArn': self.sns_topic_arn,
                    'RoleArn': self.role_arn
                }
            )
            
            return response.get('JobId')
            
        except ClientError as e:
            self.logger.error(f"Failed to start Rekognition analysis: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Unexpected error starting Rekognition analysis: {e}")
            return None
    
    def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get current job status."""
        job = self.job_tracker.get_job(job_id)
        if not job:
            return None
        
        return {
            "job_id": job_id,
            "status": job["status"],
            "original_filename": job["original_filename"],
            "created_at": job["created_at"],
            "updated_at": job["updated_at"],
            "error_message": job.get("error_message"),
            "filtered_file_path": job.get("filtered_file_path")
        }
    
    def mark_job_completed(self, rekognition_job_id: str, filtered_file_path: str):
        """Mark job as completed when webhook processing finishes."""
        job = self.job_tracker.find_job_by_rekognition_id(rekognition_job_id)
        if job:
            self.job_tracker.update_job_status(
                job["job_id"],
                "completed",
                filtered_file_path=filtered_file_path
            )
            self.logger.info(f"Marked job {job['job_id']} as completed")
    
    def mark_job_failed(self, rekognition_job_id: str, error_message: str):
        """Mark job as failed when webhook processing fails."""
        job = self.job_tracker.find_job_by_rekognition_id(rekognition_job_id)
        if job:
            self.job_tracker.update_job_status(
                job["job_id"],
                "failed",
                error_message=error_message
            )
            self.logger.error(f"Marked job {job['job_id']} as failed: {error_message}")