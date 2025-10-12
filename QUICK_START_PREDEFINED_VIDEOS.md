# 🎬 Predefined Video Feature - Quick Start Guide

## ✅ Implementation Status: COMPLETE

All components are successfully implemented and tested!

---

## 🚀 Quick Start

### Testing the Feature

1. **Start your FastAPI server:**
   ```bash
   cd rekogniton-webhook-service
   # Start your server (method depends on your setup)
   python main.py  # or uvicorn main:app --reload
   ```

2. **Upload a predefined video via frontend:**
   - Upload `sample_012.mp4` (or create a dummy file with this name)
   - Upload `demo_theft.mp4`
   - Upload `incident_report.mp4`

3. **Expected behavior:**
   - Upload completes immediately
   - Status shows "processing" for ~60 seconds
   - Status changes to "completed"
   - JSON appears in filtered directory with hash
   - Video appears in "Select a Processed Video" section
   - Chat works with story context

---

## 📋 Predefined Videos Available

| Video Name | Scene | Duration | People | Labels |
|------------|-------|----------|--------|--------|
| sample_012.mp4 | Chain snatching | 26s | 9 | 10 |
| demo_theft.mp4 | Retail shoplifting | 32s | 5 | 12 |
| incident_report.mp4 | Traffic accident | 45s | 12 | 15 |

---

## 🔧 Adding Your Own Predefined Videos

### Quick 3-Step Process:

**Step 1**: Create JSON in `processed-videos/pd/`
```json
{
  "metadata": {
    "video_info": {"original_video_name": "my_video"},
    "total_filtered_labels": 8,
    "video_duration_ms": 20000
  },
  "summary": {
    "total_unique_people": 5,
    "scene_type": "Your Scene Type"
  },
  "labels": ["label1", "label2", "label3"],
  "story": "Write your detailed narrative here..."
}
```

**Step 2**: Add to `config/pd_videos.yml`
```yaml
predefined_videos:
  - sample_012.mp4
  - demo_theft.mp4
  - incident_report.mp4
  - my_video.mp4  # Add this line
```

**Step 3**: Restart server and test!

---

## 📂 File Locations

```
sherlock-langchain/
├── config/
│   └── pd_videos.yml                    # Configuration (add videos here)
├── processed-videos/
│   ├── pd/                              # Predefined JSONs (templates)
│   │   ├── sample_012.json
│   │   ├── demo_theft.json
│   │   ├── incident_report.json
│   │   └── README.md                    # Full documentation
│   └── filtered/                        # Runtime (videos appear here after upload)
├── rekogniton-webhook-service/
│   ├── config_manager.py                # Modified (loads predefined list)
│   ├── video_processing_service.py      # Modified (handles predefined flow)
│   └── chat_service.py                  # Modified (uses story context)
├── test_predefined_videos.py            # Test script (run anytime)
└── PREDEFINED_VIDEO_FEATURE.md          # Complete documentation
```

---

## 🎯 Key Points

### ✅ What Works:
- Upload predefined videos (system detects automatically)
- 60-second simulated processing delay
- JSON copied from `pd/` to `filtered/` with hash
- Job tracking works identically
- Chat uses story context
- Frontend experience is seamless

### ❌ What Changes from Normal Flow:
- **Internally**: Skips AWS Rekognition, uses predefined JSON
- **Externally**: User sees no difference!

### 🔒 What Stays the Same:
- S3 upload still happens
- API endpoints unchanged
- Frontend code unchanged
- Job tracking unchanged
- Response formats unchanged

---

## 🐛 Troubleshooting

### Video not detected as predefined?
```bash
# Check configuration
cat config/pd_videos.yml

# Verify exact filename match (including .mp4)
```

### JSON not appearing after upload?
```bash
# Check JSON exists
ls processed-videos/pd/

# Check logs for errors
# (look for "processing predefined video" messages)
```

### Test everything is configured correctly:
```bash
python test_predefined_videos.py
```

---

## 💡 Tips

1. **Story Field**: Make it descriptive! This is what the AI uses for chat context.

2. **Labels**: Should match the story content for consistency.

3. **Metadata**: Keep video duration, people count realistic.

4. **Testing**: Use dummy video files - content doesn't matter for predefined videos!

5. **Production**: Can mix predefined and real videos seamlessly.

---

## 📊 Flow Diagram

```
User uploads sample_012.mp4
          ↓
Is it in pd_videos.yml?
    Yes → Predefined Flow      No → Normal Flow
     ↓                              ↓
Upload to S3                   Upload to S3
     ↓                              ↓
Skip Rekognition              Start Rekognition
     ↓                              ↓
60s delay simulation          Wait for webhook
     ↓                              ↓
Copy pd/sample_012.json      Process results
     ↓                              ↓
filtered/sample_012_hash     filtered/video_hash
     ↓                              ↓
Mark job completed           Mark job completed
     ↓                              ↓
        User chats with AI
```

---

## ✨ Demo Scenarios

### Scenario 1: Chain Snatching
- **Video**: `sample_012.mp4`
- **Chat Question**: "What happened in this video?"
- **Expected**: AI describes motorcycle-based chain snatching incident

### Scenario 2: Shoplifting
- **Video**: `demo_theft.mp4`
- **Chat Question**: "How many people were involved?"
- **Expected**: AI explains single person stealing in retail store

### Scenario 3: Traffic Accident
- **Video**: `incident_report.mp4`
- **Chat Question**: "Was this during day or night?"
- **Expected**: AI responds with "daylight hours" based on story

---

## 📞 Need Help?

1. **Run tests**: `python test_predefined_videos.py`
2. **Check logs**: Look for "predefined video" messages
3. **Review docs**: `processed-videos/pd/README.md`
4. **Full details**: `PREDEFINED_VIDEO_FEATURE.md`

---

## 🎉 Success!

Your predefined video feature is ready to use. No additional configuration needed!

**Test it now:**
```bash
# Verify everything is set up
python test_predefined_videos.py

# Should show: "🎉 All tests passed!"
```
