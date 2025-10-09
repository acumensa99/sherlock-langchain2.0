"""
Chat service for AI-powered video analysis conversations.
"""

import os
import sys
from pathlib import Path
from typing import Dict, Any, Optional
import logging
import json

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))
sys.path.append(str(Path(__file__).parent.parent / "ai-analysis"))

from analyze_logs import BedrockAnalyzer


class VideoChatService:
    """Handles AI chat conversations about processed videos."""
    
    def __init__(self, logger: logging.Logger):
        self.logger = logger
        self.chat_sessions = {}  # In-memory storage for chat sessions
    
    def start_chat_session(self, job_id: str, filtered_file_path: str) -> bool:
        """
        Start a new chat session for a processed video.
        
        Args:
            job_id: Job identifier
            filtered_file_path: Path to filtered analysis JSON
            
        Returns:
            bool: True if session started successfully
        """
        try:
            # Check if filtered file exists
            if not Path(filtered_file_path).exists():
                self.logger.error(f"Filtered file not found: {filtered_file_path}")
                return False
            
            # Create a BedrockAnalyzer instance for this session
            analyzer = BedrockAnalyzer()
            analyzer.rekognition_log_file = Path(filtered_file_path)
            
            # Load and prepare the analysis data
            logs = analyzer.load_rekognition_logs()
            
            # For filtered JSON files, even if timeline is empty, we can still analyze
            # Load the raw filtered data to create context
            with open(filtered_file_path, 'r') as f:
                filtered_data = json.load(f)
            
            # Create context from filtered data even if no timeline entries
            if not logs:
                self.logger.info(f"No timeline entries found, creating context from filtered data structure")
                context = self._create_context_from_filtered_data(filtered_data)
            else:
                # Prepare context for AI analysis
                context = analyzer.prepare_context(logs)
            
            # Store session data
            self.chat_sessions[job_id] = {
                "analyzer": analyzer,
                "context": context,
                "logs": logs,
                "chat_history": []
            }
            
            self.logger.info(f"Started chat session for job {job_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error starting chat session for job {job_id}: {e}")
            return False
    
    def get_chat_response(self, job_id: str, question: str) -> Dict[str, Any]:
        """
        Get AI response to user question.
        
        Args:
            job_id: Job identifier
            question: User's question
            
        Returns:
            Dict with response and metadata
        """
        try:
            # Check if session exists
            if job_id not in self.chat_sessions:
                return {
                    "success": False,
                    "error": "Chat session not found. Please ensure video processing is complete."
                }
            
            session = self.chat_sessions[job_id]
            analyzer = session["analyzer"]
            context = session["context"]
            
            # Get response from AI
            self.logger.info(f"Processing question for job {job_id}: {question}")
            response = analyzer.query_bedrock(question, context)
            
            # Store in chat history
            from datetime import datetime
            chat_entry = {
                "question": question,
                "answer": response,
                "timestamp": datetime.now().isoformat()
            }
            session["chat_history"].append(chat_entry)
            
            return {
                "success": True,
                "answer": response,
                "question": question,
                "timestamp": chat_entry["timestamp"]
            }
            
        except Exception as e:
            self.logger.error(f"Error getting chat response for job {job_id}: {e}")
            return {
                "success": False,
                "error": f"Failed to process question: {str(e)}"
            }
    
    def get_chat_history(self, job_id: str) -> Dict[str, Any]:
        """
        Get chat history for a job.
        
        Args:
            job_id: Job identifier
            
        Returns:
            Dict with chat history
        """
        if job_id not in self.chat_sessions:
            return {"success": False, "error": "Chat session not found"}
        
        return {
            "success": True,
            "chat_history": self.chat_sessions[job_id]["chat_history"]
        }
    
    def get_video_summary(self, job_id: str) -> Dict[str, Any]:
        """
        Get a summary of the video analysis.
        
        Args:
            job_id: Job identifier
            
        Returns:
            Dict with video summary
        """
        try:
            if job_id not in self.chat_sessions:
                return {"success": False, "error": "Chat session not found"}
            
            session = self.chat_sessions[job_id]
            
            # Load the full filtered data to get summary
            analyzer = session["analyzer"]
            with open(analyzer.rekognition_log_file, 'r') as f:
                filtered_data = json.load(f)
            
            summary = filtered_data.get("summary", {})
            metadata = filtered_data.get("metadata", {})
            
            return {
                "success": True,
                "summary": {
                    "total_unique_people": summary.get('total_unique_people', 0),
                    "total_person_detections": summary.get('total_person_detections', 0),
                    "primary_activities": [
                        activity.get('action', str(activity)) 
                        for activity in summary.get('primary_activities', [])[:5]
                    ],
                    "scene_type": summary.get('scene_type', 'Unknown'),
                    "key_objects": summary.get('key_objects', [])[:10],
                    "video_duration_ms": metadata.get('video_duration_ms', 0),
                    "total_labels": metadata.get('total_filtered_labels', 0)
                }
            }
            
        except Exception as e:
            self.logger.error(f"Error getting video summary for job {job_id}: {e}")
            return {"success": False, "error": str(e)}
    
    def end_session(self, job_id: str):
        """End a chat session and free up memory."""
        if job_id in self.chat_sessions:
            del self.chat_sessions[job_id]
            self.logger.info(f"Ended chat session for job {job_id}")
    
    def _create_context_from_filtered_data(self, filtered_data: Dict[str, Any]) -> str:
        """
        Create analysis context from filtered JSON data when no timeline entries exist.
        
        Args:
            filtered_data: The filtered analysis data
            
        Returns:
            Formatted context string for AI analysis
        """
        context_parts = []
        
        # Add metadata information
        metadata = filtered_data.get("metadata", {})
        video_info = metadata.get("video_info", {})
        
        context_parts.append("=== VIDEO ANALYSIS SUMMARY ===")
        context_parts.append(f"Video: {video_info.get('original_video_name', 'Unknown')}")
        context_parts.append(f"Duration: {metadata.get('video_duration_ms', 0) / 1000:.1f} seconds")
        context_parts.append(f"Total labels analyzed: {metadata.get('total_original_labels', 0)}")
        context_parts.append(f"Filtered labels: {metadata.get('total_filtered_labels', 0)}")
        context_parts.append(f"Confidence threshold: {metadata.get('confidence_threshold', 0)}%")
        
        # Add summary information
        summary = filtered_data.get("summary", {})
        context_parts.append(f"\n=== DETECTION SUMMARY ===")
        context_parts.append(f"People detected: {summary.get('total_unique_people', 0)} unique")
        context_parts.append(f"Person detections: {summary.get('total_person_detections', 0)}")
        
        # Add primary activities
        activities = summary.get('primary_activities', [])
        if activities:
            activity_names = [activity.get('action', str(activity)) for activity in activities[:5]]
            context_parts.append(f"Primary activities: {', '.join(activity_names)}")
        
        # Add scene analysis
        context_parts.append(f"Scene type: {summary.get('scene_type', 'Unknown')}")
        
        # Add key objects
        key_objects = summary.get('key_objects', [])
        if key_objects:
            context_parts.append(f"Key objects detected: {', '.join(key_objects[:15])}")
        
        # Add scene analysis details if available
        scene_analysis = filtered_data.get("scene_analysis", {})
        if scene_analysis:
            context_parts.append(f"\n=== SCENE ANALYSIS ===")
            context_parts.append(f"Environment confidence: {scene_analysis.get('environment_confidence', 0):.1f}%")
            
            categories = scene_analysis.get('categories', {})
            for category, items in categories.items():
                if items and len(items) > 0:
                    item_names = [item.get('name', str(item)) if isinstance(item, dict) else str(item) for item in items[:5]]
                    context_parts.append(f"{category}: {', '.join(item_names)}")
        
        # Add action analysis if available
        action_analysis = filtered_data.get("action_analysis", {})
        if action_analysis:
            context_parts.append(f"\n=== ACTION ANALYSIS ===")
            context_parts.append(f"Total actions detected: {action_analysis.get('total_actions_detected', 0)}")
        
        return "\n".join(context_parts)
    
    def cleanup_old_sessions(self, max_sessions: int = 10):
        """Keep only the most recent sessions to manage memory."""
        if len(self.chat_sessions) > max_sessions:
            # Remove oldest sessions (simple FIFO)
            sessions_to_remove = list(self.chat_sessions.keys())[:-max_sessions]
            for job_id in sessions_to_remove:
                self.end_session(job_id)