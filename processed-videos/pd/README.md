# Predefined Video Analysis Feature

## Overview
This feature allows the system to handle predefined videos with pre-written analysis results, providing a seamless experience for demonstration or testing purposes while maintaining the appearance of real-time AWS Rekognition analysis.

## How It Works

### 1. Configuration
Predefined videos are listed in `config/pd_videos.yml`:
```yaml
predefined_videos:
  - sample_012.mp4
  - demo_theft.mp4
  - incident_report.mp4
```

### 2. Predefined JSON Files
Pre-written analysis files are stored in `processed-videos/pd/` directory with a simplified structure:
```json
{
  "metadata": {
    "video_info": {
      "original_video_name": "sample_012"
    },
    "total_filtered_labels": 10,
    "video_duration_ms": 26000
  },
  "summary": {
    "total_unique_people": 9,
    "scene_type": "Crime Scene"
  },
  "labels": ["person", "motorcycle", "street", ...],
  "story": "Detailed narrative description of the video..."
}
```

### 3. Upload Flow for Predefined Videos

When a predefined video is uploaded:

1. **Upload to S3**: Video is uploaded to S3 bucket (normal flow)
2. **Skip Rekognition**: AWS Rekognition analysis is NOT initiated
3. **Job Creation**: Job entry is created in job tracker
4. **Simulated Processing**: 
   - Job status: `uploading` → `processing`
   - 60-second delay simulates analysis time
5. **Copy JSON**: After delay, predefined JSON is copied from `pd/` to `filtered/`
   - Original: `processed-videos/pd/sample_012.json`
   - Destination: `processed-videos/filtered/sample_012_20251012_051929_<hash>.json`
6. **Job Completion**: Job status updated to `completed`
7. **Frontend**: User sees completed analysis (identical to normal flow)

### 4. Chat Context

For predefined videos, the AI chat uses the `story` field as the primary context:
- Normal videos: Use timeline, labels, and detection data
- Predefined videos: Use story narrative + summary metadata

### 5. Frontend Experience

From the user's perspective:
- Upload works identically
- Processing time is ~1 minute
- Status polling shows normal progression
- Results appear in "Select a Processed Video" section
- Chat functionality works seamlessly
- No indication that it's a predefined video

## Adding New Predefined Videos

### Step 1: Create JSON File
Create a new JSON file in `processed-videos/pd/`:
```bash
touch processed-videos/pd/your_video.json
```

### Step 2: Define JSON Structure
```json
{
  "metadata": {
    "video_info": {
      "original_video_name": "your_video"
    },
    "total_filtered_labels": 10,
    "video_duration_ms": 30000
  },
  "summary": {
    "total_unique_people": 5,
    "scene_type": "Your Scene Type"
  },
  "labels": ["label1", "label2", "label3", ...],
  "story": "Write a detailed narrative description of what happens in the video..."
}
```

### Step 3: Update Configuration
Add the video filename to `config/pd_videos.yml`:
```yaml
predefined_videos:
  - sample_012.mp4
  - demo_theft.mp4
  - incident_report.mp4
  - your_video.mp4  # Add your new video
```

### Step 4: Test Upload
Upload the video through the frontend and verify:
- Video uploads successfully
- Processing completes after ~1 minute
- JSON appears in filtered directory with hash
- Chat works with the story context

## Key Features

### Seamless Integration
- No frontend changes required
- Same API responses as normal videos
- Identical user experience

### Flexible Context
- Story-based narratives for predefined videos
- Maintains structured data for frontend display
- AI chat adapts to context type automatically

### Easy Management
- Simple YAML configuration
- JSON-based templates
- No database changes needed

## Technical Details

### File Naming Convention
- Source: `{video_name}.json` (e.g., `sample_012.json`)
- Destination: `{video_name}_{timestamp}_{hash}.json`
- Hash generation: SHA256 of `{video_name}_{timestamp}_{job_id}`

### Job Tracking
Predefined videos are tracked identically to normal videos:
- Job ID generation
- Status updates
- Completion timestamps
- File path references

### Background Processing
Uses `asyncio.create_task()` for non-blocking 60-second delay:
- Other API endpoints remain responsive
- Multiple uploads can process simultaneously
- No impact on normal video processing

## Troubleshooting

### Video Not Recognized as Predefined
- Check filename in `config/pd_videos.yml` (must match exactly)
- Ensure `.mp4` extension is included in config
- Restart service after config changes

### JSON Not Found After Processing
- Verify JSON file exists in `processed-videos/pd/`
- Check filename matches video name without extension
- Review logs for copy errors

### Chat Not Using Story
- Confirm `story` field exists in JSON
- Check JSON syntax is valid
- Verify chat session initialization logs

## Example Predefined Videos

### sample_012.mp4
**Scene**: Chain snatching incident
**Duration**: 26 seconds
**Story**: Motorcycle-based street robbery

### demo_theft.mp4
**Scene**: Retail shoplifting
**Duration**: 32 seconds
**Story**: Customer stealing items in store

### incident_report.mp4
**Scene**: Traffic accident
**Duration**: 45 seconds
**Story**: Vehicle-pedestrian collision at intersection
