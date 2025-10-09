# Video Analysis Integration

## Overview

The video analysis service has been successfully integrated into the main Sherlock FastAPI application as a router. This allows video upload, processing, and AI-powered analysis through the same API server.

## Integration Details

### Routes Added
The video analysis functionality is now available under `/video-analysis/` prefix:

- `GET /video-analysis/` - Service health check
- `GET /video-analysis/health` - Detailed health check
- `POST /video-analysis/upload` - Upload video for processing
- `GET /video-analysis/status/{job_id}` - Get job processing status
- `POST /video-analysis/chat/{job_id}` - Chat with AI about processed video
- `GET /video-analysis/summary/{job_id}` - Get video analysis summary
- `GET /video-analysis/files/filtered` - List processed video files
- `POST /video-analysis/chat-file` - Chat with specific processed file
- `POST /video-analysis/webhook/rekognition` - AWS Rekognition webhook endpoint

### Main API Updates
The root API now includes:

- `GET /` - Shows available services and endpoints
- `GET /health` - Combined health check for all services

### Configuration
- Uses the same `config/config.yml` file for AWS and service settings
- Integrated logging with the main application
- CORS middleware added for frontend integration (Vite dev server)

### Dependencies
The following packages were added to the main `requirements.txt`:
- `boto3==1.34.0` - AWS SDK for Rekognition integration
- `aiofiles==24.1.0` - Async file operations

### File Structure
```
sherlock-langchain/
├── main.py                            # Main FastAPI app with integrated router
├── rekogniton-webhook-service/
│   ├── router.py                      # Video analysis FastAPI router
│   ├── config_manager.py             # Configuration management
│   ├── rekognition_processor.py      # AWS Rekognition processing
│   ├── video_processing_service.py   # Video processing logic
│   ├── chat_service.py               # AI chat functionality
│   ├── data_processor.py             # Data processing utilities
│   ├── job_tracker.py                # Job status tracking
│   ├── s3_uploader.py                # S3 upload functionality
│   └── uploads/                      # Video upload directory
├── processed-videos/
│   ├── raw/                          # Raw processing data
│   └── filtered/                     # Processed and filtered data
└── config/
    └── config.yml                    # Unified configuration file
```

## Usage Examples

### Upload Video
```bash
curl -X POST "http://localhost:8000/video-analysis/upload" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@video.mp4" 
```

### Check Processing Status
```bash
curl "http://localhost:8000/video-analysis/status/job_123"
```

### Chat with Processed Video
```bash
curl -X POST "http://localhost:8000/video-analysis/chat/job_123" \
  -H "Content-Type: application/json" \
  -d '{"question": "What activities are happening in this video?"}'
```

### List Available Processed Files
```bash
curl "http://localhost:8000/video-analysis/files/filtered"
```

### Chat with Specific File
```bash
curl -X POST "http://localhost:8000/video-analysis/chat-file" \
  -H "Content-Type: application/json" \
  -d '{
    "file_path": "/path/to/processed/video.json",
    "question": "Describe the scene in detail"
  }'
```

## Health Monitoring

### Service Status
```bash
curl "http://localhost:8000/health"
```

Response:
```json
{
  "status": "healthy",
  "timestamp": "2025-01-XX 10:30:45",
  "services": {
    "data_analytics": "active",
    "video_analysis": "active"
  }
}
```

### Available Services Overview
```bash
curl "http://localhost:8000/"
```

Response:
```json
{
  "status": "running",
  "service": "sherlock-langchain-api",
  "available_endpoints": {
    "data_analytics": ["/query", "/general", "/generate_title", "/autocomplete"],
    "models": ["/enabled_models"],
    "video_analysis": [
      "/video-analysis/upload",
      "/video-analysis/status/{job_id}",
      "/video-analysis/chat/{job_id}",
      "/video-analysis/summary/{job_id}",
      "/video-analysis/files/filtered",
      "/video-analysis/chat-file"
    ]
  }
}
```

## AWS Configuration

The service uses the AWS configuration from `config/config.yml`:

```yaml
aws:
  s3:
    bucket_name: "video-anomaly-logs-us-east-1"
    region: "us-east-1"
  rekognition:
    region: "us-east-1"
  sns:
    topic_arn: "arn:aws:sns:us-east-1:380312705225:rekognition-person-tracking-notifications"
    role_arn: "arn:aws:iam::380312705225:role/video-anomaly-detection"
```

## Development Notes

### Error Handling
The integration includes graceful fallback if video analysis components are not available. If imports fail, the main API continues to work without video analysis features.

### Logging
All video analysis operations use the same logging configuration as the main application (`logging.basicConfig(level=logging.INFO)`).

### CORS
CORS middleware is configured to allow frontend access from Vite dev server (`localhost:5173`).

### Background Tasks
Video processing uses FastAPI's `BackgroundTasks` for async processing, ensuring quick API responses while processing continues in the background.

## Production Deployment

The integrated service maintains the same systemd deployment structure. The video analysis functionality is now part of the main `sherlock_api.service` and doesn't require a separate service.

### Updated Service Status
```bash
# Check if video analysis is working
curl "http://localhost:8000/video-analysis/health"

# Main API status remains the same
sudo systemctl status sherlock_api.service
```

## Troubleshooting

### Import Issues
If video analysis features are not available, check:
1. All dependencies are installed: `pip install -r requirements.txt`
2. AWS credentials are configured
3. Config file exists: `config/config.yml`

### AWS Connectivity
Ensure AWS credentials are configured through:
- Environment variables (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`)
- AWS CLI configuration (`aws configure`)
- IAM roles (for EC2 instances)

### File Permissions
Ensure the upload directory has proper permissions:
```bash
chmod 755 rekogniton-webhook-service/uploads/
chmod 755 processed-videos/
```

The integration is now complete and the video analysis service is accessible through the main Sherlock API at `http://localhost:8000/video-analysis/`.