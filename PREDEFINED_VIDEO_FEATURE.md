# Predefined Video Feature - Implementation Summary

## ✅ Implementation Complete

The predefined video feature has been successfully implemented. This allows the system to handle specific videos with pre-written analysis results while maintaining a seamless user experience.

---

## 📁 Files Created/Modified

### New Files Created:
1. **`config/pd_videos.yml`**
   - Configuration file listing predefined video filenames
   - Contains: sample_012.mp4, demo_theft.mp4, incident_report.mp4

2. **`processed-videos/pd/`** (Directory)
   - Storage location for predefined JSON analysis files

3. **`processed-videos/pd/sample_012.json`**
   - Chain snatching incident (26 seconds, 9 people, 10 labels)

4. **`processed-videos/pd/demo_theft.json`**
   - Retail shoplifting incident (32 seconds, 5 people, 12 labels)

5. **`processed-videos/pd/incident_report.json`**
   - Traffic accident (45 seconds, 12 people, 15 labels)

6. **`processed-videos/pd/README.md`**
   - Comprehensive documentation for the feature

### Modified Files:

1. **`rekogniton-webhook-service/config_manager.py`**
   - Added `get_predefined_videos()` method
   - Loads and returns list from `pd_videos.yml`

2. **`rekogniton-webhook-service/video_processing_service.py`**
   - Added predefined video detection in `__init__`
   - Modified `process_video_upload()` to handle predefined videos
   - Added `_process_predefined_video()` async method
   - Implements 60-second delay simulation
   - Copies JSON from `pd/` to `filtered/` with hash

3. **`rekogniton-webhook-service/chat_service.py`**
   - Modified `start_chat_session()` to detect predefined videos
   - Added `_create_context_from_story()` method
   - Story-based context for predefined videos
   - Maintains structured context for normal videos

---

## 🔄 User Flow

### For Predefined Videos (e.g., sample_012.mp4):

```
1. User uploads sample_012.mp4
   ↓
2. Backend uploads to S3 ✅
   ↓
3. System detects it's predefined (checks pd_videos.yml)
   ↓
4. Skip AWS Rekognition analysis ⏭️
   ↓
5. Create job entry (status: uploading → processing)
   ↓
6. Background task: 60-second delay ⏰
   ↓
7. Copy pd/sample_012.json → filtered/sample_012_<timestamp>_<hash>.json
   ↓
8. Update job status: completed ✅
   ↓
9. Frontend polls status → shows completed
   ↓
10. User can chat with AI using story context 💬
```

### For Normal Videos:

```
1. User uploads video.mp4
   ↓
2. Backend uploads to S3 ✅
   ↓
3. System starts AWS Rekognition analysis
   ↓
4. Wait for SNS webhook notification
   ↓
5. Process Rekognition results
   ↓
6. Generate filtered JSON
   ↓
7. Update job status: completed ✅
   ↓
8. Frontend polls status → shows completed
   ↓
9. User can chat with AI using detection context 💬
```

---

## 🎯 Key Features

### 1. Seamless Integration
- ✅ No frontend changes required
- ✅ Same API endpoints
- ✅ Identical response formats
- ✅ User cannot detect difference

### 2. Non-Blocking Processing
- ✅ Uses `asyncio.create_task()` for background processing
- ✅ 60-second delay doesn't block other requests
- ✅ Multiple uploads can process simultaneously

### 3. Intelligent Context Handling
- ✅ Normal videos: Timeline + detection data
- ✅ Predefined videos: Story narrative + metadata
- ✅ AI chat adapts automatically

### 4. Easy Management
- ✅ Simple YAML configuration
- ✅ JSON-based templates
- ✅ No database changes
- ✅ Add new videos by creating JSON + updating config

---

## 📝 Predefined JSON Structure

```json
{
  "metadata": {
    "video_info": {
      "original_video_name": "video_name"
    },
    "total_filtered_labels": 10,
    "video_duration_ms": 26000
  },
  "summary": {
    "total_unique_people": 9,
    "scene_type": "Scene Type"
  },
  "labels": ["label1", "label2", ...],
  "story": "Detailed narrative description..."
}
```

**Key Fields:**
- `metadata`: Video information and stats
- `summary`: People count and scene type
- `labels`: Array of detected labels
- `story`: **Main narrative for AI chat context** ⭐

---

## 🔧 Technical Implementation Details

### Hash Generation
```python
hash_input = f"{base_filename}_{timestamp}_{job_id}"
file_hash = hashlib.sha256(hash_input.encode()).hexdigest()
```

### File Naming
- **Source**: `sample_012.json`
- **Destination**: `sample_012_20251012_051929_c8dccd6ec44a519ecdb9542cb05035880172405b4293b149d7abbbb3a7f5d44d.json`

### Predefined Detection
```python
is_predefined = original_filename in self.predefined_videos
```

### Background Task
```python
asyncio.create_task(
    self._process_predefined_video(job_id, original_filename)
)
```

---

## 🚀 How to Add New Predefined Videos

### Step 1: Create JSON
```bash
# Create new JSON file
nano processed-videos/pd/new_video.json
```

### Step 2: Define Content
```json
{
  "metadata": {
    "video_info": {"original_video_name": "new_video"},
    "total_filtered_labels": 8,
    "video_duration_ms": 20000
  },
  "summary": {
    "total_unique_people": 3,
    "scene_type": "Your Scene"
  },
  "labels": ["label1", "label2", "label3"],
  "story": "Your detailed narrative here..."
}
```

### Step 3: Update Config
```yaml
# Add to config/pd_videos.yml
predefined_videos:
  - sample_012.mp4
  - demo_theft.mp4
  - incident_report.mp4
  - new_video.mp4  # Add this
```

### Step 4: Restart Service
```bash
# Restart the service to reload config
# (Method depends on your deployment)
```

---

## 🎬 Example Predefined Videos

### 1. sample_012.mp4
- **Scene**: Chain snatching on motorcycle
- **Duration**: 26 seconds
- **People**: 9 unique individuals
- **Labels**: 10 (person, motorcycle, street, jewelry, etc.)
- **Story**: Two people on motorcycle snatch chain from woman

### 2. demo_theft.mp4
- **Scene**: Retail store shoplifting
- **Duration**: 32 seconds
- **People**: 5 unique individuals
- **Labels**: 12 (person, shop, retail, backpack, etc.)
- **Story**: Customer conceals items in backpack without payment

### 3. incident_report.mp4
- **Scene**: Traffic accident at intersection
- **Duration**: 45 seconds
- **People**: 12 unique individuals
- **Labels**: 15 (person, vehicle, traffic, accident, etc.)
- **Story**: Vehicle-pedestrian collision with witnesses

---

## 📊 Frontend Display

When a predefined video is processed, the frontend shows:

```
File: sample_012_20251012_051929_c8dccd6ec44a519e...json
Size: 0.02 MB
Processed: 2025-10-12 06:03:53
Duration: 0:26
People: 9 unique
Labels: 10 detected
Scene: Crime Scene
```

**Note**: The `story` field is NOT displayed in the frontend - it's used only for AI chat context.

---

## ✅ Testing Checklist

- [x] Config file created (`pd_videos.yml`)
- [x] Predefined directory created (`processed-videos/pd/`)
- [x] Sample JSON files created (3 examples)
- [x] Config manager updated (load predefined list)
- [x] Video processing service modified (detect & handle)
- [x] Background task implemented (60-second delay)
- [x] JSON copying logic (pd → filtered with hash)
- [x] Chat service updated (story context)
- [x] Job tracker integration (status updates)
- [x] Documentation created (README + summary)

---

## 🐛 Troubleshooting

### Issue: Video not recognized as predefined
**Solution**: 
- Check exact filename match in `pd_videos.yml`
- Ensure `.mp4` extension included
- Restart service after config changes

### Issue: JSON not found after processing
**Solution**:
- Verify JSON exists in `processed-videos/pd/`
- Check filename matches video name (no extension)
- Review logs for copy errors

### Issue: Chat not using story context
**Solution**:
- Confirm `story` field exists in JSON
- Validate JSON syntax
- Check `is_predefined` flag in logs

---

## 📞 Support

For questions or issues:
1. Check logs in terminal
2. Review `processed-videos/pd/README.md`
3. Verify JSON structure matches template
4. Check `config/pd_videos.yml` configuration

---

## 🎉 Summary

The predefined video feature is now fully operational. You can:
- ✅ Upload predefined videos (sample_012.mp4, demo_theft.mp4, incident_report.mp4)
- ✅ System simulates 60-second processing
- ✅ JSON appears in filtered directory with hash
- ✅ Chat works with story context
- ✅ Frontend experience identical to normal videos
- ✅ Easy to add new predefined videos

**No breaking changes to existing functionality!**
