"""
Rekognition processor for handling label detection results
"""

import boto3
import json
import os
import time
from typing import Dict, Any, Optional, List
import logging
from datetime import datetime
from data_processor import DataProcessor


class RekognitionProcessor:
    """Handles AWS Rekognition operations and result processing"""
    
    def __init__(self, config: Dict[str, Any], logger: logging.Logger):
        self.config = config
        self.logger = logger
        
        # AWS configuration
        aws_config = config.get("aws", {})
        self.region = aws_config.get("rekognition", {}).get("region", "us-east-1")
        
        # Webhook configuration
        webhook_config = config.get("webhook_service", {})
        self.max_retry_attempts = webhook_config.get("max_retry_attempts", 3)
        self.retry_delay = webhook_config.get("retry_delay_seconds", 2)
        
        # Initialize boto3 client
        self.rekognition_client = boto3.client('rekognition', region_name=self.region)
        
        # Initialize data processor
        self.data_processor = DataProcessor(config, logger)
        
        # Processed videos directory (legacy - now handled by DataProcessor)
        self.processed_videos_dir = self._get_processed_videos_dir()
        self._ensure_directory_exists(self.processed_videos_dir)
    
    def _get_processed_videos_dir(self) -> str:
        """Get the processed videos directory path"""
        webhook_config = self.config.get("webhook_service", {})
        dir_name = webhook_config.get("processed_videos_dir", "processed-videos")
        
        # Return absolute path
        return os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            dir_name
        )
    
    def _ensure_directory_exists(self, directory: str):
        """Ensure the directory exists, create if it doesn't"""
        if not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)
            self.logger.info(f"Created directory: {directory}")
    
    async def process_label_detection_job(
        self,
        job_id: str,
        original_video_name: str,
        s3_bucket: str,
        s3_object_name: str
    ) -> bool:
        """
        Process a label detection job by fetching all paginated results
        and consolidating them into a single JSON file
        """
        try:
            self.logger.info(f"Processing label detection job {job_id}")
            
            # Collect all paginated results
            all_results = await self._collect_all_label_detection_results(job_id)
            
            if not all_results:
                self.logger.error(f"No results collected for job {job_id}")
                return False
            
            # Create consolidated result
            consolidated_result = self._create_consolidated_result(
                all_results,
                job_id,
                original_video_name,
                s3_bucket,
                s3_object_name
            )
            
            # Process and save both raw and filtered versions
            output_filename = f"{original_video_name}_{job_id}.json"
            raw_path, filtered_path = self.data_processor.process_and_save(
                consolidated_result, 
                output_filename
            )
            
            self.logger.info(f"Saved raw data to {raw_path}")
            self.logger.info(f"Saved filtered data to {filtered_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error processing job {job_id}: {str(e)}")
            return False
    
    async def _collect_all_label_detection_results(self, job_id: str) -> List[Dict[str, Any]]:
        """
        Collect all paginated results from get_label_detection
        """
        all_results = []
        next_token = None
        page_count = 0
        
        try:
            while True:
                page_count += 1
                self.logger.info(f"Fetching page {page_count} for job {job_id}")
                
                # Prepare request parameters
                params = {
                    'JobId': job_id
                }
                
                if next_token:
                    params['NextToken'] = next_token
                
                # Make the API call with retry logic
                response = await self._get_label_detection_with_retry(params)
                
                if not response:
                    self.logger.error(f"Failed to get response for job {job_id}, page {page_count}")
                    break
                
                all_results.append(response)
                
                # Check if there are more pages
                next_token = response.get('NextToken')
                if not next_token:
                    self.logger.info(f"Completed fetching all pages for job {job_id}. Total pages: {page_count}")
                    break
                
                # Small delay between requests to be nice to AWS
                time.sleep(0.5)
                
        except Exception as e:
            self.logger.error(f"Error collecting results for job {job_id}: {str(e)}")
        
        return all_results
    
    async def _get_label_detection_with_retry(self, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Get label detection results with retry logic
        """
        for attempt in range(self.max_retry_attempts):
            try:
                response = self.rekognition_client.get_label_detection(**params)
                return response
                
            except Exception as e:
                self.logger.warning(
                    f"Attempt {attempt + 1} failed for get_label_detection: {str(e)}"
                )
                
                if attempt < self.max_retry_attempts - 1:
                    time.sleep(self.retry_delay * (attempt + 1))  # Exponential backoff
                else:
                    self.logger.error(f"All retry attempts failed for get_label_detection")
        
        return None
    
    def _create_consolidated_result(
        self,
        all_results: List[Dict[str, Any]],
        job_id: str,
        original_video_name: str,
        s3_bucket: str,
        s3_object_name: str
    ) -> Dict[str, Any]:
        """
        Create a consolidated result from all paginated responses
        """
        if not all_results:
            return {}
        
        # Start with the first result as base
        consolidated = all_results[0].copy()
        
        # Remove NextToken from the final result
        consolidated.pop('NextToken', None)
        
        # Consolidate labels from all pages
        all_labels = []
        
        for result in all_results:
            labels = result.get('Labels', [])
            all_labels.extend(labels)
        
        # Update the consolidated result
        consolidated['Labels'] = all_labels
        consolidated['TotalLabels'] = len(all_labels)
        consolidated['PagesProcessed'] = len(all_results)
        
        # Add metadata
        consolidated['ProcessingMetadata'] = {
            'original_video_name': original_video_name,
            's3_bucket': s3_bucket,
            's3_object_name': s3_object_name,
            'processed_at': datetime.utcnow().isoformat(),
            'total_pages': len(all_results),
            'total_labels': len(all_labels)
        }
        
        # Add summary statistics
        consolidated['Summary'] = self._generate_summary_stats(all_labels)
        
        return consolidated
    
    def _generate_summary_stats(self, labels: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Generate summary statistics from labels
        """
        if not labels:
            return {}
        
        # Count unique label names
        unique_labels = set()
        person_instances = 0
        timestamps = set()
        
        for label_entry in labels:
            timestamp = label_entry.get('Timestamp', 0)
            timestamps.add(timestamp)
            
            label_info = label_entry.get('Label', {})
            label_name = label_info.get('Name', '')
            unique_labels.add(label_name)
            
            # Count person instances
            if label_name.lower() == 'person':
                instances = label_info.get('Instances', [])
                person_instances += len(instances)
        
        return {
            'unique_labels_count': len(unique_labels),
            'unique_labels': sorted(list(unique_labels)),
            'total_timestamps': len(timestamps),
            'person_instances_detected': person_instances,
            'video_duration_processed_ms': max(timestamps) if timestamps else 0
        }