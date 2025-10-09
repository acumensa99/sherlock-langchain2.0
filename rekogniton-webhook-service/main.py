"""
FastAPI webhook service for receiving AWS SNS notifications
and processing Rekognition label detection results.
"""

from fastapi import FastAPI, Request, HTTPException, BackgroundTasks, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import json
import os
import sys
from typing import Optional, Dict, Any, List
import asyncio
from datetime import datetime
import uuid
import boto3
import aiofiles
from pathlib import Path

# Add parent directory to path to import utilities
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.logger import setup_logger
from config_manager import ConfigManager
from rekognition_processor import RekognitionProcessor
from video_processing_service import VideoProcessingService
from chat_service import VideoChatService

# Initialize logger
logger = setup_logger(
    name="webhook_service",
    level="INFO",
    log_file="../logs/webhook_service.log"
)

# Initialize configuration
config_manager = ConfigManager()
config = config_manager.get_config()

# Initialize services
processor = RekognitionProcessor(config, logger)
video_service = VideoProcessingService(config, logger)
chat_service = VideoChatService(logger)

# Initialize FastAPI app
app = FastAPI(
    title="Video Anomaly Detection API",
    description="API for video upload, processing, and AI-powered analysis",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],  # Vite dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create uploads directory
UPLOAD_DIR = Path(__file__).parent / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)


class SNSNotification(BaseModel):
    """Model for SNS notification payload"""
    Type: str
    MessageId: str
    TopicArn: str
    Message: str
    Timestamp: str
    SignatureVersion: str
    Signature: str
    SigningCertURL: str
    UnsubscribeURL: str

class ChatRequest(BaseModel):
    question: str

class FileChatRequest(BaseModel):
    file_path: str
    question: str

class ChatResponse(BaseModel):
    success: bool
    answer: Optional[str] = None
    error: Optional[str] = None
    timestamp: Optional[str] = None

class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    original_filename: str
    created_at: str
    updated_at: str
    error_message: Optional[str] = None
    filtered_file_path: Optional[str] = None


@app.get("/")
async def root():
    """Health check endpoint"""
    return {"status": "running", "service": "video-analysis-webhook"}


@app.get("/health")
async def health_check():
    """Detailed health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "video-analysis-webhook",
        "version": "1.0.0"
    }


@app.post("/api/upload")
async def upload_video(file: UploadFile = File(...)):
    """
    Upload video file for processing.
    
    Returns:
        Job ID and initial status
    """
    try:
        # Validate file type
        if not file.content_type or not file.content_type.startswith('video/'):
            raise HTTPException(status_code=400, detail="Only video files are allowed")
        
        # Check file size (10MB limit)
        if file.size and file.size > 10 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="File size exceeds 10MB limit")
        
        # Save uploaded file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_filename = "".join(c for c in file.filename if c.isalnum() or c in ('-', '_', '.'))
        local_filename = f"{timestamp}_{safe_filename}"
        local_file_path = UPLOAD_DIR / local_filename
        
        async with aiofiles.open(local_file_path, 'wb') as f:
            content = await file.read()
            await f.write(content)
        
        logger.info(f"Saved uploaded file: {local_file_path}")
        
        # Process video upload
        result = await video_service.process_video_upload(str(local_file_path), file.filename)
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in video upload: {e}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@app.get("/api/status/{job_id}")
async def get_job_status(job_id: str):
    """
    Get processing status for a job.
    
    Args:
        job_id: Job identifier
        
    Returns:
        Job status information
    """
    try:
        status = video_service.get_job_status(job_id)
        
        if not status:
            raise HTTPException(status_code=404, detail="Job not found")
        
        return status
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting job status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/chat/{job_id}")
async def chat_with_ai(job_id: str, request: ChatRequest):
    """
    Chat with AI about processed video.
    
    Args:
        job_id: Job identifier
        request: Chat request with question
        
    Returns:
        AI response
    """
    try:
        # Check if job is completed
        status = video_service.get_job_status(job_id)
        if not status:
            raise HTTPException(status_code=404, detail="Job not found")
        
        if status["status"] != "completed":
            raise HTTPException(status_code=400, detail="Video processing not completed yet")
        
        # Start chat session if not already started
        if job_id not in chat_service.chat_sessions:
            success = chat_service.start_chat_session(job_id, status["filtered_file_path"])
            if not success:
                raise HTTPException(status_code=500, detail="Failed to start chat session")
        
        # Get AI response
        response = chat_service.get_chat_response(job_id, request.question)
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in chat endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/summary/{job_id}")
async def get_video_summary(job_id: str):
    """
    Get video analysis summary.
    
    Args:
        job_id: Job identifier
        
    Returns:
        Video summary data
    """
    try:
        # Check if job is completed
        status = video_service.get_job_status(job_id)
        if not status:
            raise HTTPException(status_code=404, detail="Job not found")
        
        if status["status"] != "completed":
            raise HTTPException(status_code=400, detail="Video processing not completed yet")
        
        # Start chat session if needed to get summary
        if job_id not in chat_service.chat_sessions:
            success = chat_service.start_chat_session(job_id, status["filtered_file_path"])
            if not success:
                raise HTTPException(status_code=500, detail="Failed to start chat session")
        
        # Get summary
        summary = chat_service.get_video_summary(job_id)
        
        return summary
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting video summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/files/filtered")
async def list_filtered_files():
    """
    List all available filtered files for direct chat.
    
    Returns:
        List of filtered files with metadata
    """
    try:
        base_dir = Path(__file__).parent.parent
        filtered_dir = base_dir / "processed-videos" / "filtered"
        
        if not filtered_dir.exists():
            return {"files": []}
        
        files = []
        for file_path in filtered_dir.glob("*.json"):
            try:
                # Get file stats
                stat = file_path.stat()
                file_size = stat.st_size
                modified_time = datetime.fromtimestamp(stat.st_mtime)
                
                # Try to extract basic info from filename
                filename = file_path.stem
                parts = filename.split('_')
                video_name = parts[0] if parts else filename
                
                # Try to read metadata from the file
                metadata = {}
                summary_info = {}
                try:
                    with open(file_path, 'r') as f:
                        data = json.load(f)
                        metadata = data.get('metadata', {})
                        summary_info = data.get('summary', {})
                except Exception:
                    pass
                
                file_info = {
                    "filename": file_path.name,
                    "file_path": str(file_path),
                    "video_name": video_name,
                    "size_mb": round(file_size / (1024 * 1024), 2),
                    "modified_at": modified_time.isoformat(),
                    "modified_display": modified_time.strftime("%Y-%m-%d %H:%M:%S"),
                    "original_video_name": metadata.get('video_info', {}).get('original_video_name', video_name),
                    "total_labels": metadata.get('total_filtered_labels', 0),
                    "video_duration_ms": metadata.get('video_duration_ms', 0),
                    "people_count": summary_info.get('total_unique_people', 0),
                    "scene_type": summary_info.get('scene_type', 'Unknown')
                }
                
                files.append(file_info)
                
            except Exception as e:
                logger.error(f"Error processing file {file_path}: {e}")
                continue
        
        # Sort by modification time (newest first)
        files.sort(key=lambda x: x["modified_at"], reverse=True)
        
        return {"files": files}
        
    except Exception as e:
        logger.error(f"Error listing filtered files: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/chat-file")
async def chat_with_file(request: FileChatRequest):
    """
    Start chat with a specific filtered file.
    
    Args:
        request: Contains file_path and question
        
    Returns:
        Chat response
    """
    try:
        file_path = request.file_path
        question = request.question
        
        # Validate file exists
        if not Path(file_path).exists():
            raise HTTPException(status_code=404, detail="File not found")
        
        # Generate a temporary job ID for this file
        temp_job_id = f"file_{Path(file_path).stem}"
        
        # Start chat session
        if temp_job_id not in chat_service.chat_sessions:
            success = chat_service.start_chat_session(temp_job_id, file_path)
            if not success:
                raise HTTPException(status_code=500, detail="Failed to start chat session")
        
        # Get AI response
        response = chat_service.get_chat_response(temp_job_id, question)
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in file chat endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/webhook/rekognition")
async def rekognition_webhook(
    request: Request,
    background_tasks: BackgroundTasks
):
    """
    Webhook endpoint to receive SNS notifications from AWS Rekognition
    """
    try:
        # Parse the request body
        body = await request.body()
        notification_data = json.loads(body.decode())
        
        logger.info(f"Received webhook notification: {notification_data.get('MessageId', 'unknown')}")
        
        # Handle SNS subscription confirmation
        if notification_data.get("Type") == "SubscriptionConfirmation":
            logger.info("Received SNS subscription confirmation")
            
            # Get the SubscribeURL and confirm the subscription
            subscribe_url = notification_data.get("SubscribeURL")
            if subscribe_url:
                import requests
                try:
                    logger.info(f"Confirming subscription at: {subscribe_url}")
                    response = requests.get(subscribe_url, timeout=10)
                    if response.status_code == 200:
                        logger.info("Subscription confirmed successfully!")
                        return {"status": "subscription_confirmed"}
                    else:
                        logger.error(f"Failed to confirm subscription: {response.status_code}")
                        return {"status": "confirmation_failed"}
                except Exception as e:
                    logger.error(f"Error confirming subscription: {str(e)}")
                    return {"status": "confirmation_error"}
            else:
                logger.error("No SubscribeURL found in confirmation message")
                return {"status": "no_subscribe_url"}
        
        # Handle notification
        if notification_data.get("Type") == "Notification":
            # Parse the inner message
            message_str = notification_data.get("Message", "{}")
            message_data = json.loads(message_str)
            
            # Extract job information
            job_id = message_data.get("JobId")
            status = message_data.get("Status")
            api = message_data.get("API")
            
            logger.info(f"Processing job {job_id} with status {status} for API {api}")
            
            # Only process successful label detection jobs
            if status == "SUCCEEDED" and api == "StartLabelDetection":
                # Process in background to return response quickly
                background_tasks.add_task(
                    process_rekognition_results,
                    job_id,
                    message_data
                )
                return {"status": "processing_started", "job_id": job_id}
            else:
                logger.warning(f"Skipping job {job_id} - Status: {status}, API: {api}")
                return {"status": "skipped", "job_id": job_id}
        
        return {"status": "processed"}
        
    except Exception as e:
        logger.error(f"Error processing webhook: {str(e)}")
        return {"status": "error", "message": str(e)}


async def process_rekognition_results(job_id: str, message_data: Dict[str, Any]):
    """
    Background task to process Rekognition results
    """
    try:
        logger.info(f"Starting background processing for job {job_id}")
        
        # Extract video information
        video_info = message_data.get("Video", {})
        s3_object_name = video_info.get("S3ObjectName", "")
        s3_bucket = video_info.get("S3Bucket", "")
        
        # Extract original video name from S3 path
        original_video_name = os.path.basename(s3_object_name).replace('.mp4', '')
        
        # Process the results
        success = await processor.process_label_detection_job(
            job_id=job_id,
            original_video_name=original_video_name,
            s3_bucket=s3_bucket,
            s3_object_name=s3_object_name
        )
        
        if success:
            logger.info(f"Successfully processed job {job_id}")
            # Update job status to completed with absolute path
            base_dir = Path(__file__).parent.parent
            filtered_file_path = str(base_dir / "processed-videos" / "filtered" / f"{original_video_name}_{job_id}.json")
            video_service.mark_job_completed(job_id, filtered_file_path)
        else:
            logger.error(f"Failed to process job {job_id}")
            video_service.mark_job_failed(job_id, "Processing failed")
            
    except Exception as e:
        logger.error(f"Error in background processing for job {job_id}: {str(e)}")
        video_service.mark_job_failed(job_id, str(e))


if __name__ == "__main__":
    import uvicorn
    
    # Get host and port from config
    webhook_config = config.get("webhook_service", {})
    host = webhook_config.get("host", "0.0.0.0")
    port = webhook_config.get("port", 8000)
    
    logger.info(f"Starting webhook service on {host}:{port}")
    
    uvicorn.run(
        app,
        host=host,
        port=port,
        reload=True,
        log_level="info"
    )