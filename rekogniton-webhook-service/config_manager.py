"""
Configuration manager for webhook service
"""

import yaml
import os
from typing import Dict, Any


class ConfigManager:
    """Manages configuration loading and access"""
    
    def __init__(self, config_path: str = None):
        if config_path is None:
            # Default to config/config.yml in parent directory
            self.config_path = os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                "config",
                "config.yml"
            )
        else:
            self.config_path = config_path
            
        self.config = self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from YAML file"""
        try:
            with open(self.config_path, 'r') as file:
                return yaml.safe_load(file)
        except FileNotFoundError:
            raise FileNotFoundError(f"Configuration file not found: {self.config_path}")
        except yaml.YAMLError as e:
            raise ValueError(f"Error parsing configuration file: {e}")
    
    def get_config(self) -> Dict[str, Any]:
        """Get the full configuration dictionary"""
        return self.config
    
    def get_aws_config(self) -> Dict[str, Any]:
        """Get AWS-specific configuration"""
        return self.config.get("aws", {})
    
    def get_webhook_config(self) -> Dict[str, Any]:
        """Get webhook service configuration"""
        return self.config.get("webhook_service", {})
    
    def get_rekognition_config(self) -> Dict[str, Any]:
        """Get Rekognition configuration"""
        return self.config.get("rekognition", {})
    
    def get_s3_bucket_name(self) -> str:
        """Get S3 bucket name"""
        return self.config.get("aws", {}).get("s3", {}).get("bucket_name", "")
    
    def get_aws_region(self) -> str:
        """Get AWS region"""
        return self.config.get("aws", {}).get("rekognition", {}).get("region", "us-east-1")
    
    def get_processed_videos_dir(self) -> str:
        """Get processed videos directory path"""
        webhook_config = self.get_webhook_config()
        dir_name = webhook_config.get("processed_videos_dir", "processed-videos")
        
        # Return absolute path
        return os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            dir_name
        )
    
    def get_predefined_videos(self) -> list:
        """Get list of predefined videos from pd_videos.yml"""
        try:
            pd_config_path = os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                "config",
                "pd_videos.yml"
            )
            with open(pd_config_path, 'r') as file:
                pd_config = yaml.safe_load(file)
                return pd_config.get("predefined_videos", [])
        except FileNotFoundError:
            return []
        except yaml.YAMLError:
            return []