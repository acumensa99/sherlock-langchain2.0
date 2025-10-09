"""
S3 uploader for video files.
"""

import boto3
import os
from datetime import datetime
from typing import Optional
import logging
from botocore.exceptions import ClientError, NoCredentialsError


class S3VideoUploader:
    """Handles video uploads to S3 bucket."""
    
    def __init__(self, config: dict, logger: logging.Logger):
        self.config = config
        self.logger = logger
        
        # AWS configuration
        aws_config = config.get("aws", {})
        s3_config = aws_config.get("s3", {})
        self.bucket_name = s3_config.get("bucket_name")
        self.region = s3_config.get("region", "us-east-1")
        
        if not self.bucket_name:
            raise ValueError("S3 bucket name not configured")
        
        # Initialize S3 client
        try:
            self.s3_client = boto3.client(
                's3',
                region_name=self.region,
                aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
                aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY')
            )
        except Exception as e:
            self.logger.error(f"Failed to initialize S3 client: {e}")
            raise
    
    def generate_s3_key(self, original_filename: str) -> str:
        """
        Generate S3 object key with timestamp.
        
        Args:
            original_filename: Original file name
            
        Returns:
            S3 object key
        """
        # Extract file extension
        file_ext = os.path.splitext(original_filename)[1]
        
        # Create timestamp-based name
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_name = os.path.splitext(original_filename)[0]
        
        # Clean the base name (remove special characters)
        clean_name = "".join(c for c in base_name if c.isalnum() or c in ('-', '_'))
        
        s3_key = f"videos/{clean_name}_{timestamp}{file_ext}"
        return s3_key
    
    async def upload_video(self, file_path: str, s3_key: str) -> bool:
        """
        Upload video file to S3.
        
        Args:
            file_path: Local path to video file
            s3_key: S3 object key
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            self.logger.info(f"Uploading {file_path} to s3://{self.bucket_name}/{s3_key}")
            
            # Upload file
            self.s3_client.upload_file(
                file_path,
                self.bucket_name,
                s3_key,
                ExtraArgs={
                    'ContentType': 'video/mp4'
                }
            )
            
            self.logger.info(f"Successfully uploaded to s3://{self.bucket_name}/{s3_key}")
            return True
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            self.logger.error(f"S3 upload failed with error {error_code}: {e}")
            return False
        except NoCredentialsError:
            self.logger.error("AWS credentials not found")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error during S3 upload: {e}")
            return False
    
    def get_s3_url(self, s3_key: str) -> str:
        """Get S3 URL for the uploaded video."""
        return f"https://{self.bucket_name}.s3.{self.region}.amazonaws.com/{s3_key}"
    
    def check_file_exists(self, s3_key: str) -> bool:
        """Check if file exists in S3."""
        try:
            self.s3_client.head_object(Bucket=self.bucket_name, Key=s3_key)
            return True
        except ClientError:
            return False