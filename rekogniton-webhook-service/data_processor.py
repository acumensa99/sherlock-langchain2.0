"""
Data processor for filtering and optimizing Rekognition results for AI analysis.
"""

import json
import os
from typing import Dict, List, Any, Tuple, Set
from datetime import datetime
import logging
from collections import defaultdict, Counter
import math


class DataProcessor:
    """Processes raw Rekognition data into AI-optimized format"""
    
    def __init__(self, config: Dict[str, Any], logger: logging.Logger):
        self.config = config
        self.logger = logger
        
        # Processing configuration
        processing_config = config.get("data_processing", {})
        self.confidence_threshold = processing_config.get("confidence_threshold", 75.0)
        self.person_dedup_threshold = processing_config.get("person_deduplication_threshold", 0.7)
        self.temporal_window = processing_config.get("temporal_grouping_window", 5000)
        self.priority_labels = set(processing_config.get("priority_labels", []))
        
        # Directories
        webhook_config = config.get("webhook_service", {})
        base_dir = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            webhook_config.get("processed_videos_dir", "processed-videos")
        )
        
        self.raw_dir = os.path.join(base_dir, "raw")
        self.filtered_dir = os.path.join(base_dir, "filtered")
        
        # Ensure directories exist
        os.makedirs(self.raw_dir, exist_ok=True)
        os.makedirs(self.filtered_dir, exist_ok=True)
    
    def process_and_save(self, raw_data: Dict[str, Any], filename: str) -> Tuple[str, str]:
        """
        Process raw data and save both raw and filtered versions.
        
        Returns:
            Tuple of (raw_file_path, filtered_file_path)
        """
        try:
            # Save raw data
            raw_file_path = os.path.join(self.raw_dir, filename)
            with open(raw_file_path, 'w') as f:
                json.dump(raw_data, f, indent=2, default=str)
            
            self.logger.info(f"Saved raw data to {raw_file_path}")
            
            # Process and save filtered data
            filtered_data = self.create_filtered_data(raw_data)
            filtered_file_path = os.path.join(self.filtered_dir, filename)
            
            with open(filtered_file_path, 'w') as f:
                json.dump(filtered_data, f, indent=2, default=str)
            
            self.logger.info(f"Saved filtered data to {filtered_file_path}")
            
            return raw_file_path, filtered_file_path
            
        except Exception as e:
            self.logger.error(f"Error processing data: {str(e)}")
            raise
    
    def create_filtered_data(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create AI-optimized filtered data from raw Rekognition results"""
        
        # Filter labels by confidence
        filtered_labels = self._filter_labels_by_confidence(raw_data.get("Labels", []))
        
        # Analyze person detections
        person_analysis = self._analyze_person_detections(filtered_labels)
        
        # Analyze actions and activities
        action_analysis = self._analyze_actions(filtered_labels)
        
        # Create temporal summary
        temporal_summary = self._create_temporal_summary(filtered_labels)
        
        # Create scene analysis
        scene_analysis = self._analyze_scene(filtered_labels)
        
        # Create the filtered structure
        filtered_data = {
            "metadata": {
                "original_job_id": raw_data.get("JobId"),
                "video_info": raw_data.get("ProcessingMetadata", {}),
                "processed_at": datetime.utcnow().isoformat(),
                "confidence_threshold": self.confidence_threshold,
                "total_original_labels": len(raw_data.get("Labels", [])),
                "total_filtered_labels": len(filtered_labels),
                "video_duration_ms": raw_data.get("Summary", {}).get("video_duration_processed_ms", 0)
            },
            
            "summary": {
                "total_unique_people": person_analysis["unique_people_count"],
                "total_person_detections": person_analysis["total_detections"],
                "primary_activities": action_analysis["primary_activities"][:5],
                "scene_type": scene_analysis["scene_type"],
                "key_objects": scene_analysis["key_objects"][:10],
                "time_periods": len(temporal_summary)
            },
            
            "person_analysis": person_analysis,
            "action_analysis": action_analysis,
            "scene_analysis": scene_analysis,
            "temporal_summary": temporal_summary,
            
            "high_confidence_labels": self._get_high_confidence_labels(filtered_labels),
            "key_timestamps": self._extract_key_timestamps(filtered_labels)
        }
        
        return filtered_data
    
    def _filter_labels_by_confidence(self, labels: List[Dict]) -> List[Dict]:
        """Filter labels by confidence threshold"""
        filtered = []
        
        for label_entry in labels:
            label_info = label_entry.get("Label", {})
            confidence = label_info.get("Confidence", 0)
            
            # Always keep priority labels with slightly lower threshold
            label_name = label_info.get("Name", "")
            if label_name in self.priority_labels:
                threshold = max(self.confidence_threshold - 10, 60)  # 10% lower for priority
            else:
                threshold = self.confidence_threshold
            
            if confidence >= threshold:
                # Also filter instances by confidence
                instances = label_info.get("Instances", [])
                filtered_instances = [
                    inst for inst in instances 
                    if inst.get("Confidence", 0) >= threshold
                ]
                
                # Create filtered label entry
                filtered_label = label_entry.copy()
                filtered_label["Label"] = label_info.copy()
                filtered_label["Label"]["Instances"] = filtered_instances
                
                filtered.append(filtered_label)
        
        return filtered
    
    def _analyze_person_detections(self, labels: List[Dict]) -> Dict[str, Any]:
        """Analyze person detections with deduplication"""
        
        person_detections = []
        unique_people = set()
        person_instances_by_timestamp = defaultdict(list)
        
        # Collect all person instances
        for label_entry in labels:
            label_info = label_entry.get("Label", {})
            if label_info.get("Name") == "Person":
                timestamp = label_entry.get("Timestamp", 0)
                instances = label_info.get("Instances", [])
                
                for instance in instances:
                    person_detections.append({
                        "timestamp": timestamp,
                        "bounding_box": instance.get("BoundingBox", {}),
                        "confidence": instance.get("Confidence", 0)
                    })
                    person_instances_by_timestamp[timestamp].append(instance)
        
        # Deduplicate people across timestamps using IoU
        unique_people_count = self._estimate_unique_people(person_instances_by_timestamp)
        
        # Analyze person movement and activities
        person_activities = self._analyze_person_activities(labels)
        
        timestamps = sorted(list(person_instances_by_timestamp.keys()))
        
        return {
            "total_detections": len(person_detections),
            "unique_people_count": unique_people_count,
            "detection_time_range": {
                "first_detection_ms": min(timestamps) if timestamps else 0,
                "last_detection_ms": max(timestamps) if timestamps else 0,
                "total_detection_periods": len(timestamps)
            },
            "activities": person_activities,
            "peak_person_count": max([len(instances) for instances in person_instances_by_timestamp.values()], default=0),
            "average_confidence": sum([d["confidence"] for d in person_detections]) / len(person_detections) if person_detections else 0
        }
    
    def _estimate_unique_people(self, person_instances_by_timestamp: Dict) -> int:
        """Estimate unique people using bounding box overlap across timestamps"""
        timestamps = sorted(person_instances_by_timestamp.keys())
        if len(timestamps) <= 1:
            return max([len(instances) for instances in person_instances_by_timestamp.values()], default=0)
        
        # For simplicity, take the maximum number of people detected in any single frame
        # In a more sophisticated version, we'd track people across frames
        max_simultaneous = max([len(instances) for instances in person_instances_by_timestamp.values()], default=0)
        
        return max_simultaneous
    
    def _analyze_actions(self, labels: List[Dict]) -> Dict[str, Any]:
        """Analyze actions and activities in the video"""
        
        action_labels = ["Walking", "Running", "Dancing", "Sitting", "Standing", "Jumping", "Clapping"]
        actions_detected = defaultdict(list)
        
        for label_entry in labels:
            label_info = label_entry.get("Label", {})
            label_name = label_info.get("Name", "")
            
            if label_name in action_labels:
                actions_detected[label_name].append({
                    "timestamp": label_entry.get("Timestamp", 0),
                    "confidence": label_info.get("Confidence", 0)
                })
        
        # Sort actions by frequency and confidence
        primary_activities = []
        for action, detections in actions_detected.items():
            avg_confidence = sum([d["confidence"] for d in detections]) / len(detections)
            timestamps = [d["timestamp"] for d in detections]
            primary_activities.append({
                "action": action,
                "frequency": len(detections),
                "average_confidence": avg_confidence,
                "time_range": {
                    "start_ms": min(timestamps),
                    "end_ms": max(timestamps),
                    "duration_ms": max(timestamps) - min(timestamps)
                }
            })
        
        primary_activities.sort(key=lambda x: (x["frequency"], x["average_confidence"]), reverse=True)
        
        return {
            "total_actions_detected": len(actions_detected),
            "primary_activities": primary_activities,
            "action_timeline": self._create_action_timeline(actions_detected)
        }
    
    def _analyze_person_activities(self, labels: List[Dict]) -> List[str]:
        """Extract person-related activities"""
        person_activities = []
        
        for label_entry in labels:
            label_info = label_entry.get("Label", {})
            label_name = label_info.get("Name", "")
            
            # Check if this label is related to person activities
            if any(parent.get("Name") == "Person" for parent in label_info.get("Parents", [])):
                person_activities.append(label_name)
        
        return list(set(person_activities))
    
    def _analyze_scene(self, labels: List[Dict]) -> Dict[str, Any]:
        """Analyze scene and environment"""
        
        scene_categories = defaultdict(list)
        objects = []
        
        for label_entry in labels:
            label_info = label_entry.get("Label", {})
            label_name = label_info.get("Name", "")
            categories = label_info.get("Categories", [])
            
            # Group by categories
            for category in categories:
                category_name = category.get("Name", "")
                scene_categories[category_name].append({
                    "label": label_name,
                    "confidence": label_info.get("Confidence", 0)
                })
            
            objects.append({
                "name": label_name,
                "confidence": label_info.get("Confidence", 0),
                "categories": [c.get("Name", "") for c in categories]
            })
        
        # Determine primary scene type
        scene_type = self._determine_scene_type(scene_categories)
        
        # Get key objects (non-person objects with high confidence)
        key_objects = [
            obj for obj in objects 
            if obj["name"] not in ["Person", "People", "Human"] and obj["confidence"] > 80
        ]
        key_objects.sort(key=lambda x: x["confidence"], reverse=True)
        
        # Remove duplicates while preserving order (highest confidence first)
        unique_key_objects = []
        seen_objects = set()
        for obj in key_objects:
            if obj["name"] not in seen_objects:
                unique_key_objects.append(obj["name"])
                seen_objects.add(obj["name"])
        
        return {
            "scene_type": scene_type,
            "categories": dict(scene_categories),
            "key_objects": unique_key_objects,
            "environment_confidence": self._calculate_environment_confidence(scene_categories)
        }
    
    def _determine_scene_type(self, scene_categories: Dict) -> str:
        """Determine the primary scene type"""
        category_scores = {}
        
        for category, labels in scene_categories.items():
            if labels:
                avg_confidence = sum([l["confidence"] for l in labels]) / len(labels)
                category_scores[category] = avg_confidence * len(labels)
        
        if not category_scores:
            return "Unknown"
        
        return max(category_scores, key=category_scores.get)
    
    def _create_temporal_summary(self, labels: List[Dict]) -> List[Dict]:
        """Create temporal summary grouped by time windows"""
        
        if not labels:
            return []
        
        # Group labels by time windows
        time_groups = defaultdict(list)
        
        for label_entry in labels:
            timestamp = label_entry.get("Timestamp", 0)
            time_window = (timestamp // self.temporal_window) * self.temporal_window
            time_groups[time_window].append(label_entry)
        
        # Create summary for each time window
        temporal_summary = []
        for time_window in sorted(time_groups.keys()):
            window_labels = time_groups[time_window]
            
            # Count people in this window
            person_count = 0
            actions_in_window = set()
            
            for label_entry in window_labels:
                label_info = label_entry.get("Label", {})
                label_name = label_info.get("Name", "")
                
                if label_name == "Person":
                    person_count += len(label_info.get("Instances", []))
                elif label_name in ["Walking", "Running", "Dancing", "Sitting", "Standing"]:
                    actions_in_window.add(label_name)
            
            temporal_summary.append({
                "time_window_start_ms": time_window,
                "time_window_end_ms": time_window + self.temporal_window,
                "person_detections": person_count,
                "activities": list(actions_in_window),
                "total_labels": len(window_labels),
                "key_labels": [
                    label_entry.get("Label", {}).get("Name", "") 
                    for label_entry in window_labels[:5]  # Top 5 labels
                ]
            })
        
        return temporal_summary
    
    def _get_high_confidence_labels(self, labels: List[Dict]) -> List[Dict]:
        """Get labels with very high confidence (90%+)"""
        
        high_confidence = []
        
        for label_entry in labels:
            label_info = label_entry.get("Label", {})
            if label_info.get("Confidence", 0) >= 90:
                high_confidence.append({
                    "label": label_info.get("Name", ""),
                    "confidence": label_info.get("Confidence", 0),
                    "timestamp": label_entry.get("Timestamp", 0),
                    "instances": len(label_info.get("Instances", []))
                })
        
        return sorted(high_confidence, key=lambda x: x["confidence"], reverse=True)[:20]  # Top 20
    
    def _extract_key_timestamps(self, labels: List[Dict]) -> Dict[str, Any]:
        """Extract key timestamps where important events happen"""
        
        key_timestamps = set()
        priority_events = []
        
        for label_entry in labels:
            label_info = label_entry.get("Label", {})
            label_name = label_info.get("Name", "")
            timestamp = label_entry.get("Timestamp", 0)
            confidence = label_info.get("Confidence", 0)
            
            # Mark timestamps with person detections or priority actions
            if (label_name in self.priority_labels or 
                confidence >= 95 or
                len(label_info.get("Instances", [])) > 0):
                key_timestamps.add(timestamp)
                
                # Track high-priority events
                if confidence >= 95 and label_name in self.priority_labels:
                    priority_events.append({
                        "timestamp": timestamp,
                        "event": label_name,
                        "confidence": confidence
                    })
        
        timestamps_list = sorted(list(key_timestamps))
        
        return {
            "total_key_moments": len(timestamps_list),
            "first_key_moment": min(timestamps_list) if timestamps_list else 0,
            "last_key_moment": max(timestamps_list) if timestamps_list else 0,
            "priority_events": priority_events[:5]  # Top 5 priority events
        }
    
    def _create_action_timeline(self, actions_detected: Dict) -> List[Dict]:
        """Create a timeline of actions"""
        timeline = []
        
        for action, detections in actions_detected.items():
            for detection in detections:
                timeline.append({
                    "timestamp": detection["timestamp"],
                    "action": action,
                    "confidence": detection["confidence"]
                })
        
        return sorted(timeline, key=lambda x: x["timestamp"])
    
    def _calculate_environment_confidence(self, scene_categories: Dict) -> float:
        """Calculate overall confidence in environment detection"""
        if not scene_categories:
            return 0.0
        
        all_confidences = []
        for labels in scene_categories.values():
            all_confidences.extend([l["confidence"] for l in labels])
        
        return sum(all_confidences) / len(all_confidences) if all_confidences else 0.0