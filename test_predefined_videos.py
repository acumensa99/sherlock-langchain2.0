#!/usr/bin/env python3
"""
Test script for predefined video feature
This script verifies that all components are properly configured
"""

import os
import sys
import json
import yaml
from pathlib import Path

def test_config_file():
    """Test if pd_videos.yml exists and is valid"""
    print("✓ Testing configuration file...")
    config_path = Path(__file__).parent / "config" / "pd_videos.yml"
    
    if not config_path.exists():
        print("  ❌ Config file not found:", config_path)
        return False
    
    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
            videos = config.get('predefined_videos', [])
            print(f"  ✅ Found {len(videos)} predefined videos:")
            for video in videos:
                print(f"     - {video}")
            return True
    except Exception as e:
        print(f"  ❌ Error reading config: {e}")
        return False

def test_pd_directory():
    """Test if pd directory exists with JSON files"""
    print("\n✓ Testing predefined videos directory...")
    pd_dir = Path(__file__).parent / "processed-videos" / "pd"
    
    if not pd_dir.exists():
        print("  ❌ Directory not found:", pd_dir)
        return False
    
    json_files = list(pd_dir.glob("*.json"))
    print(f"  ✅ Found {len(json_files)} JSON files:")
    
    for json_file in json_files:
        print(f"     - {json_file.name}")
    
    return len(json_files) > 0

def test_json_structure():
    """Test if JSON files have correct structure"""
    print("\n✓ Testing JSON file structure...")
    pd_dir = Path(__file__).parent / "processed-videos" / "pd"
    json_files = list(pd_dir.glob("*.json"))
    
    required_fields = {
        'metadata': ['video_info', 'total_filtered_labels', 'video_duration_ms'],
        'summary': ['total_unique_people', 'scene_type'],
        'labels': [],
        'story': []
    }
    
    all_valid = True
    for json_file in json_files:
        if json_file.name == "README.md":
            continue
            
        try:
            with open(json_file, 'r') as f:
                data = json.load(f)
            
            # Check required top-level fields
            for field in required_fields.keys():
                if field not in data:
                    print(f"  ❌ {json_file.name}: Missing '{field}' field")
                    all_valid = False
                    continue
                
                # Check nested fields
                if isinstance(required_fields[field], list) and len(required_fields[field]) > 0:
                    for subfield in required_fields[field]:
                        if subfield not in data[field]:
                            print(f"  ❌ {json_file.name}: Missing '{field}.{subfield}'")
                            all_valid = False
            
            if all_valid:
                story_length = len(data.get('story', ''))
                labels_count = len(data.get('labels', []))
                print(f"  ✅ {json_file.name}: Valid structure")
                print(f"     Story: {story_length} characters")
                print(f"     Labels: {labels_count} items")
                print(f"     People: {data['summary']['total_unique_people']}")
                print(f"     Scene: {data['summary']['scene_type']}")
                
        except json.JSONDecodeError as e:
            print(f"  ❌ {json_file.name}: Invalid JSON - {e}")
            all_valid = False
        except Exception as e:
            print(f"  ❌ {json_file.name}: Error - {e}")
            all_valid = False
    
    return all_valid

def test_filtered_directory():
    """Test if filtered directory exists"""
    print("\n✓ Testing filtered videos directory...")
    filtered_dir = Path(__file__).parent / "processed-videos" / "filtered"
    
    if not filtered_dir.exists():
        print("  ⚠️  Filtered directory not found (will be created on first use)")
        return True
    
    json_files = list(filtered_dir.glob("*.json"))
    print(f"  ✅ Filtered directory exists with {len(json_files)} files")
    return True

def test_config_loader():
    """Test if config_manager can load predefined videos"""
    print("\n✓ Testing config_manager integration...")
    
    try:
        sys.path.insert(0, str(Path(__file__).parent / "rekogniton-webhook-service"))
        from config_manager import ConfigManager
        
        config_mgr = ConfigManager()
        predefined_videos = config_mgr.get_predefined_videos()
        
        print(f"  ✅ Config manager loaded {len(predefined_videos)} videos:")
        for video in predefined_videos:
            print(f"     - {video}")
        
        return len(predefined_videos) > 0
        
    except Exception as e:
        print(f"  ❌ Error loading config manager: {e}")
        return False

def main():
    """Run all tests"""
    print("=" * 60)
    print("Predefined Video Feature - Test Suite")
    print("=" * 60)
    
    tests = [
        ("Configuration File", test_config_file),
        ("Predefined Directory", test_pd_directory),
        ("JSON Structure", test_json_structure),
        ("Filtered Directory", test_filtered_directory),
        ("Config Manager", test_config_loader)
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"\n❌ Test '{test_name}' failed with exception: {e}")
            results.append((test_name, False))
    
    print("\n" + "=" * 60)
    print("Test Results Summary")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {test_name}")
    
    print("=" * 60)
    print(f"Total: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed! Predefined video feature is ready.")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed. Please review the errors above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
