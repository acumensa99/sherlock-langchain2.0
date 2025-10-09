#!/usr/bin/env python3
"""
AI Analysis Script for Rekognition Logs
Uses AWS Bedrock to analyze video recognition logs and answer questions.
"""

import json
import os
import sys
import boto3
from datetime import datetime
from pathlib import Path
import logging
from dotenv import load_dotenv
from typing import Dict, List, Any, Optional

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

# Load environment variables
load_dotenv(Path(__file__).parent.parent / "config" / ".env")


class BedrockAnalyzer:
    """Simple AI Analyzer using AWS Bedrock to analyze rekognition logs."""
    
    def __init__(self):
        """Initialize the AWS Bedrock analyzer with default settings."""
        # AWS credentials
        self.aws_access_key = os.getenv('AWS_ACCESS_KEY_ID')
        self.aws_secret_key = os.getenv('AWS_SECRET_ACCESS_KEY')
        self.aws_region = os.getenv('AWS_REGION_NAME', 'us-east-1')
        
        # Default to Claude 3 Sonnet
        self.model_id = os.getenv('AWS_BEDROCK_MODEL_ID', 'us.anthropic.claude-3-7-sonnet-20250219-v1:0')
        
        if not self.aws_access_key or not self.aws_secret_key:
            raise ValueError("AWS_ACCESS_KEY_ID or AWS_SECRET_ACCESS_KEY not found. Please set them in config/.env")
        
        # Set up file paths
        self.rekognition_log_file = Path(__file__).parent.parent / "logs" / "rekognition_analysis.json"
        self.qa_log_file = Path(__file__).parent.parent / "logs" / "ai_analysis_qa.log"
        self.filtered_dir = Path(__file__).parent.parent / "processed-videos" / "filtered"
            
        # Create directories if they don't exist
        self.qa_log_file.parent.mkdir(exist_ok=True)
        
        # Initialize AWS Bedrock client
        session = boto3.Session(
            aws_access_key_id=self.aws_access_key,
            aws_secret_access_key=self.aws_secret_key,
            region_name=self.aws_region
        )
        
        self.bedrock_client = session.client(service_name="bedrock-runtime")
    
    def load_rekognition_logs(self):
        """Load rekognition analysis logs."""
        if not self.rekognition_log_file.exists():
            print(f"Error: Rekognition log file not found: {self.rekognition_log_file}")
            return []
        
        try:
            with open(self.rekognition_log_file, 'r') as f:
                data = json.load(f)
            
            # Check if this is the old format (list of frames) or new filtered format (dict with metadata)
            if isinstance(data, list):
                # Old format - list of frame entries
                logs = data
                print(f"✅ Loaded analysis data from {len(logs)} frames (old format)")
            elif isinstance(data, dict) and 'metadata' in data and 'summary' in data:
                # New filtered format from our data processor
                logs = []
                
                # Extract action timeline data
                action_analysis = data.get('action_analysis', {})
                action_timeline = action_analysis.get('action_timeline', [])
                
                # Convert action timeline to frame-like entries
                for entry in action_timeline:
                    frame_entry = {
                        'frame_number': None,  # Not available in filtered format
                        'timestamp': entry.get('timestamp', 0),
                        'label_analysis': [{
                            'Name': entry.get('action', 'Unknown'),
                            'Confidence': entry.get('confidence', 0)
                        }],
                        'recognized_people': [],  # Will add person data if available
                        'gender_analysis': []
                    }
                    logs.append(frame_entry)
                
                # Also add summary-level data for context
                summary = data.get('summary', {})
                activities = summary.get('primary_activities', [])
                
                # Add summary as a special entry for AI analysis
                if activities:
                    summary_entry = {
                        'frame_number': 'SUMMARY',
                        'timestamp': 0,
                        'label_analysis': [],
                        'recognized_people': [],
                        'gender_analysis': [],
                        'summary_data': {
                            'total_unique_people': summary.get('total_unique_people', 0),
                            'total_detections': summary.get('total_person_detections', 0),
                            'primary_activities': [act.get('action', 'Unknown') for act in activities[:5]],
                            'scene_type': summary.get('scene_type', 'Unknown'),
                            'key_objects': summary.get('key_objects', [])[:10]
                        }
                    }
                    
                    # Add activity data as labels
                    for activity in activities[:10]:  # Limit to top 10
                        summary_entry['label_analysis'].append({
                            'Name': activity.get('action', 'Unknown'),
                            'Confidence': activity.get('average_confidence', 0)
                        })
                    
                    logs.insert(0, summary_entry)  # Add at beginning
                
                print(f"✅ Loaded analysis data from {len(logs)} timeline entries (filtered format)")
            else:
                print(f"❌ Unknown data format in {self.rekognition_log_file}")
                return []
            
            return logs
            
        except Exception as e:
            print(f"Error loading rekognition logs: {e}")
            return []
    
    def list_filtered_files(self):
        """List all filtered JSON files"""
        if not self.filtered_dir.exists():
            return []
        
        return sorted([f for f in self.filtered_dir.glob("*.json")])
    
    def select_file_interactive(self):
        """Interactive file selection from filt
        ered directory"""
        filtered_files = self.list_filtered_files()
        
        if not filtered_files:
            print("❌ No filtered files found in processed-videos/filtered/")
            print("💡 Please run video analysis first or use the process_raw_data.py script")
            return None
        
        print("\n" + "="*60)
        print("📁 AVAILABLE FILTERED FILES")
        print("="*60)
        
        # Group files by video name for better display
        video_groups = {}
        for file_path in filtered_files:
            # Extract video name from filename (before the first underscore)
            parts = file_path.stem.split('_')
            video_name = parts[0] if parts else file_path.stem
            
            if video_name not in video_groups:
                video_groups[video_name] = []
            video_groups[video_name].append(file_path)
        
        # Display files grouped by video
        file_options = []
        index = 1
        
        for video_name, files in video_groups.items():
            print(f"\n📹 {video_name.upper()}")
            for file_path in files:
                size_mb = file_path.stat().st_size / (1024 * 1024)
                modified_time = datetime.fromtimestamp(file_path.stat().st_mtime)
                
                print(f"   {index:2d}. {file_path.name}")
                print(f"       📊 Size: {size_mb:.1f} MB")
                print(f"       🕒 Modified: {modified_time.strftime('%Y-%m-%d %H:%M:%S')}")
                
                file_options.append(file_path)
                index += 1
        
        print("\n" + "="*60)
        
        while True:
            try:
                choice = input(f"Select a file (1-{len(file_options)}) or 'q' to quit: ").strip()
                
                if choice.lower() == 'q':
                    return None
                
                file_index = int(choice) - 1
                if 0 <= file_index < len(file_options):
                    selected_file = file_options[file_index]
                    print(f"✅ Selected: {selected_file.name}")
                    return selected_file
                else:
                    print(f"❌ Invalid choice. Please select 1-{len(file_options)}")
                    
            except ValueError:
                print("❌ Invalid input. Please enter a number or 'q'")
            except KeyboardInterrupt:
                print("\n👋 Cancelled by user")
                return None
    
    def prepare_context(self, logs):
        """
        Prepare context from logs for AI analysis.
        
        Args:
            logs: List of rekognition log entries
            
        Returns:
            Formatted context string
        """
        if not logs:
            return "No rekognition analysis logs available."
        
        context_parts = []
        context_parts.append("=== VIDEO ANALYSIS LOGS ===")
        context_parts.append(f"Total frames analyzed: {len(logs)}")
        
        # Summary statistics
        people_detected = set()
        total_faces = 0
        genders = {"Male": 0, "Female": 0}
        emotions_summary = {}
        labels_summary = {}
        
        for entry in logs:
            # Collect recognized people
            if entry.get('recognized_people'):
                for person in entry['recognized_people']:
                    if isinstance(person, dict) and 'name' in person:
                        people_detected.add(person['name'])
            
            # Count faces and genders from gender_analysis
            if entry.get('gender_analysis'):
                total_faces += len(entry['gender_analysis'])
                for face in entry['gender_analysis']:
                    if face.get('Gender'):
                        gender = face['Gender']
                        genders[gender] = genders.get(gender, 0) + 1
            
            # Count labels from label_analysis
            if entry.get('label_analysis'):
                for label in entry['label_analysis']:
                    if isinstance(label, dict) and 'Name' in label:
                        label_name = label['Name']
                        labels_summary[label_name] = labels_summary.get(label_name, 0) + 1
        
        # Add summary statistics
        context_parts.append(f"\n=== SUMMARY STATISTICS ===")
        context_parts.append(f"Unique people recognized: {len(people_detected)}")
        if people_detected:
            context_parts.append(f"People names: {', '.join(sorted(people_detected))}")
            print(f"👥 Recognized people: {', '.join(sorted(people_detected))}")
        
        context_parts.append(f"Total faces detected: {total_faces}")
        context_parts.append(f"Gender distribution: {dict(genders)}")
        
        if emotions_summary:
            top_emotions = sorted(emotions_summary.items(), key=lambda x: x[1], reverse=True)[:5]
            context_parts.append(f"Top emotions: {dict(top_emotions)}")
        
        if labels_summary:
            top_labels = sorted(labels_summary.items(), key=lambda x: x[1], reverse=True)[:10]
            context_parts.append(f"Top detected objects/scenes: {dict(top_labels)}")
        
        # Add a sample of frame-by-frame analysis
        context_parts.append(f"\n=== DETAILED FRAME ANALYSIS ===")
        for i, entry in enumerate(logs[-10:], 1):  # Last 10 entries to stay within token limits
            frame_info = f"Frame {entry.get('frame_number', i)} ({entry.get('timestamp', 'unknown time')}):"
            
            if entry.get('recognized_people') and len(entry['recognized_people']) > 0:
                similarities = [f"{p.get('name', 'Unknown')}({p.get('similarity', 0):.1f}%)" 
                               for p in entry['recognized_people'] if isinstance(p, dict)]
                if similarities:
                    frame_info += f" People: {', '.join(similarities)}"
            
            if entry.get('gender_analysis'):
                face_count = len(entry['gender_analysis'])
                genders_in_frame = [f['Gender'] for f in entry['gender_analysis'] if f.get('Gender')]
                if genders_in_frame:
                    frame_info += f" Faces: {face_count} ({', '.join(genders_in_frame)})"
            
            if entry.get('label_analysis'):
                top_labels_frame = [l['Name'] for l in entry['label_analysis'][:3] if isinstance(l, dict) and 'Name' in l]
                if top_labels_frame:
                    frame_info += f" Objects: {', '.join(top_labels_frame)}"
            
            context_parts.append(frame_info)
        
        return "\n".join(context_parts)
    
    def query_bedrock(self, question, context):
        """
        Query AWS Bedrock with context and question.
        """
        system_prompt = """You are an AI assistant analyzing video surveillance logs. 
        The logs contain information about people recognition, face analysis (gender, age, emotions), 
        object detection, and other video analysis data. 
        
        Answer questions based ONLY on the provided log data. Be specific and cite frame numbers or timestamps when relevant.
        If the information is not in the logs, clearly state that.
        
        Keep responses concise but informative."""
        
        user_prompt = f"""Context from video analysis logs:
{context}

Question: {question}

Please answer based on the log data above."""
        
        try:
            # Create the request body for Claude models
            if "claude-3" in self.model_id or "claude-sonnet" in self.model_id or "claude-opus" in self.model_id:
                # Claude 3 models use the messages format with top-level system parameter
                body = json.dumps({
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 1000,
                    "temperature": 0.3,
                    "system": system_prompt,
                    "messages": [
                        {
                            "role": "user", 
                            "content": user_prompt
                        }
                    ]
                })
            # Support for Llama models
            elif "llama" in self.model_id:
                prompt = f"{system_prompt}\n\nHuman: {user_prompt}\n\nAssistant:"
                body = json.dumps({
                    "prompt": prompt,
                    "max_gen_len": 1000,
                    "temperature": 0.3,
                })
            else:
                # Default format for other models
                prompt = f"{system_prompt}\n\nHuman: {user_prompt}\n\nAssistant:"
                body = json.dumps({
                    "prompt": prompt,
                    "max_tokens_to_sample": 1000,
                    "temperature": 0.3,
                })
            
            # Invoke the model
            response = self.bedrock_client.invoke_model(
                modelId=self.model_id,
                contentType="application/json",
                accept="application/json",
                body=body
            )
            
            # Parse the response
            response_body = json.loads(response["body"].read())
            
            if "claude-3" in self.model_id or "claude-sonnet" in self.model_id or "claude-opus" in self.model_id:
                # Claude 3 response format
                # Newer models return content as a list of objects
                if isinstance(response_body.get("content", []), list):
                    answer = response_body.get("content", [{}])[0].get("text", "")
                else:
                    # Handle alternate response structures
                    answer = response_body.get("completion", "") or response_body.get("content", "")
            elif "llama" in self.model_id:
                # Llama model response format
                answer = response_body.get("generation", "")
            else:
                # Default response format for older Claude models
                answer = response_body.get("completion", "")
            
            return answer.strip()
            
        except Exception as e:
            error_message = str(e)
            print(f"Error: Failed to get response from AWS Bedrock. {error_message}")
            return f"Error: Failed to get response from AWS Bedrock. {error_message}"
    
    def log_qa(self, question, answer):
        """Log question and answer to file."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        log_entry = f"""
{'='*50}
TIMESTAMP: {timestamp}
QUESTION: {question}
ANSWER: {answer}
{'='*50}
"""
        
        try:
            with open(self.qa_log_file, 'a', encoding='utf-8') as f:
                f.write(log_entry)
            print(f"Q&A logged to {self.qa_log_file}")
        except Exception as e:
            print(f"Failed to log Q&A: {e}")
    
    def analyze_question(self, question: str, log_to_file: bool = True) -> Dict[str, Any]:
        """
        Analyze a single question programmatically (for API/integration use).
        
        Args:
            question: The question to analyze
            log_to_file: Whether to log the Q&A to file
            
        Returns:
            Dict containing question, answer, timestamp, and metadata
        """
        try:
            # Load logs if not cached
            logs = self.load_rekognition_logs()
            
            if not logs:
                return {
                    "success": False,
                    "error": "No rekognition logs available",
                    "question": question,
                    "answer": None,
                    "timestamp": datetime.now().isoformat()
                }
            
            # Prepare context
            context = self.prepare_context(logs)
            
            # Get AI answer
            answer = self.query_bedrock(question, context)
            
            result = {
                "success": True,
                "question": question,
                "answer": answer,
                "timestamp": datetime.now().isoformat(),
                "log_entries_analyzed": len(logs)
            }
            
            # Log to file if requested
            if log_to_file:
                self.log_qa(question, answer)
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error analyzing question: {e}")
            return {
                "success": False,
                "error": str(e),
                "question": question,
                "answer": None,
                "timestamp": datetime.now().isoformat()
            }
    
    def get_log_summary(self) -> Dict[str, Any]:
        """
        Get a summary of the loaded logs (for API/integration use).
        
        Returns:
            Summary statistics of the logs
        """
        logs = self.load_rekognition_logs()
        
        if not logs:
            return {"error": "No logs available"}
        
        # Calculate summary statistics
        summary = {
            "total_frames": len(logs),
            "date_range": {
                "start": logs[0].get("timestamp") if logs else None,
                "end": logs[-1].get("timestamp") if logs else None
            },
            "people_recognized": [],
            "total_faces_detected": 0,
            "gender_distribution": {"Male": 0, "Female": 0},
            "common_emotions": {},
            "common_objects": {},
            "has_moderation_flags": False,
            "has_text_detection": False
        }
        
        people_set = set()
        
        for entry in logs:
            # People recognition
            if entry.get('recognized_people'):
                for person in entry['recognized_people']:
                    people_set.add(person['name'])
            
            # Face analysis from gender_analysis
            if entry.get('gender_analysis'):
                summary["total_faces_detected"] += len(entry['gender_analysis'])
                for face in entry['gender_analysis']:
                    if face.get('Gender'):
                        gender = face['Gender']
                        summary["gender_distribution"][gender] += 1
            
            # Objects/Labels from label_analysis
            if entry.get('label_analysis'):
                for label in entry['label_analysis']:
                    if isinstance(label, dict) and 'Name' in label:
                        label_name = label['Name']
                        summary["common_objects"][label_name] = summary["common_objects"].get(label_name, 0) + 1
            
            # Check for moderation and text
            if entry.get('moderation'):
                summary["has_moderation_flags"] = True
            if entry.get('text_detections'):
                summary["has_text_detection"] = True
        
        summary["people_recognized"] = sorted(list(people_set))
        
        # Sort common items by frequency
        summary["common_emotions"] = dict(sorted(summary["common_emotions"].items(), key=lambda x: x[1], reverse=True)[:10])
        summary["common_objects"] = dict(sorted(summary["common_objects"].items(), key=lambda x: x[1], reverse=True)[:10])
        
        return summary
    
    def batch_analyze(self, questions: List[str], log_to_file: bool = True) -> List[Dict[str, Any]]:
        """
        Analyze multiple questions in batch (for API/integration use).
        
        Args:
            questions: List of questions to analyze
            log_to_file: Whether to log Q&A to file
            
        Returns:
            List of analysis results
        """
        results = []
        
        for question in questions:
            result = self.analyze_question(question, log_to_file=log_to_file)
            results.append(result)
        
        return results
    
    def interactive_analysis(self):
        """
        Run interactive analysis session.
        """
        print("🤖 AI Video Analysis Tool")
        print("="*50)
        
        # Select file to analyze
        selected_file = self.select_file_interactive()
        if not selected_file:
            print("❌ No file selected. Exiting.")
            return
        
        # Update the rekognition_log_file to the selected file
        self.rekognition_log_file = selected_file
        
        # Load logs
        print(f"\n📊 Loading analysis data from {selected_file.name}...")
        logs = self.load_rekognition_logs()
        
        if not logs:
            # Check if it's a valid filtered file with summary data
            try:
                with open(selected_file, 'r') as f:
                    file_data = json.load(f)
                
                if isinstance(file_data, dict) and 'summary' in file_data:
                    print("📋 No timeline data found, but summary data is available.")
                    print("💡 This video may contain static scenes without specific actions.")
                    
                    # Create a basic context from summary data
                    summary = file_data.get('summary', {})
                    metadata = file_data.get('metadata', {})
                    
                    context_parts = [
                        "=== VIDEO ANALYSIS SUMMARY ===",
                        f"Video: {metadata.get('video_info', {}).get('original_video_name', 'Unknown')}",
                        f"Duration: {metadata.get('video_duration_ms', 0) / 1000:.1f} seconds",
                        f"People detected: {summary.get('total_unique_people', 0)} unique people",
                        f"Total person detections: {summary.get('total_person_detections', 0)}",
                        f"Scene type: {summary.get('scene_type', 'Unknown')}",
                        f"Key objects detected: {', '.join(summary.get('key_objects', [])[:10])}",
                        f"Time periods analyzed: {summary.get('time_periods', 0)}",
                        "",
                        "=== DETAILED ANALYSIS ===",
                        f"This video appears to be primarily focused on: {', '.join(summary.get('key_objects', [])[:5])}",
                        f"The scene contains {summary.get('total_unique_people', 0)} people with {summary.get('total_person_detections', 0)} total detections.",
                    ]
                    
                    # Add person analysis if available
                    person_analysis = file_data.get('person_analysis', {})
                    if person_analysis:
                        activities = person_analysis.get('activities', [])[:5]
                        if activities:
                            context_parts.append(f"Person-related elements detected: {', '.join(activities)}")
                    
                    context = "\n".join(context_parts)
                    
                    print(f"📁 Analysis file: {selected_file}")
                    print(f"📝 Q&A will be saved to: {self.qa_log_file}")
                    print("\n💡 Example questions for this video:")
                    print("   - What is the main subject of this video?")
                    print("   - How many people are visible?")
                    print("   - What objects are detected?")
                    print("   - What type of scene is this?")
                    print("\n" + "="*50)
                    
                    # Continue with Q&A using summary context
                    self._run_qa_session(context)
                    return
                else:
                    print("❌ No analysis data found. Please run the video analysis first.")
                    return
                    
            except Exception as e:
                print(f"❌ Error reading file: {e}")
                return
        
        # Prepare context
        context = self.prepare_context(logs)
        
        print(f"📁 Logs: {self.rekognition_log_file}")
        print(f"📝 Q&A will be saved to: {self.qa_log_file}")
        print("\n💡 Example questions:")
        print("   - Who all were there in this video?")
        print("   - How many times did John appear?")
        print("   - What emotions were detected?")
        print("   - What objects were commonly seen?")
        print("   - Were there more males or females?")
        print("\n" + "="*50)
        
        # Run Q&A session
        self._run_qa_session(context)
    
    def _run_qa_session(self, context):
        """Run the interactive Q&A session"""
        while True:
            try:
                question = input("\n🔍 Ask a question (or 'quit' to exit): ").strip()
                
                if question.lower() in ['quit', 'exit', 'q']:
                    print("👋 Goodbye!")
                    break
                
                if not question:
                    continue
                
                print("\n🧠 Analyzing...")
                answer = self.query_bedrock(question, context)
                
                print(f"\n🤖 Answer:")
                print(f"{answer}\n")
                
                # Log to terminal and file
                self.log_qa(question, answer)
                
            except KeyboardInterrupt:
                print("\n👋 Goodbye!")
                break
            except Exception as e:
                print(f"❌ Error: {e}")


def main():
    """Main function."""
    try:
        analyzer = BedrockAnalyzer()
        analyzer.interactive_analysis()
    except Exception as e:
        print(f"❌ Failed to start analyzer: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
