#!/usr/bin/env python3
"""
Simple test script to verify the video analysis integration
"""

import requests
import json
import sys

def test_integration():
    """Test the integrated video analysis service"""
    base_url = "http://localhost:8000"
    
    print("🧪 Testing Video Analysis Integration")
    print("=" * 50)
    
    # Test 1: Main API health
    try:
        response = requests.get(f"{base_url}/health", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print("✅ Main API health check: PASSED")
            print(f"   Services: {data.get('services', {})}")
        else:
            print(f"❌ Main API health check: FAILED ({response.status_code})")
            return False
    except Exception as e:
        print(f"❌ Main API health check: FAILED - {e}")
        return False
    
    # Test 2: Root endpoint with service overview
    try:
        response = requests.get(f"{base_url}/", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print("✅ Root endpoint: PASSED")
            if "video_analysis" in data.get("available_endpoints", {}):
                print("   Video analysis endpoints detected")
            else:
                print("   Video analysis endpoints not available")
        else:
            print(f"❌ Root endpoint: FAILED ({response.status_code})")
    except Exception as e:
        print(f"❌ Root endpoint: FAILED - {e}")
    
    # Test 3: Video analysis health check
    try:
        response = requests.get(f"{base_url}/video-analysis/health", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print("✅ Video analysis health check: PASSED")
            print(f"   Status: {data.get('status')}")
        else:
            print(f"❌ Video analysis health check: FAILED ({response.status_code})")
    except Exception as e:
        print(f"❌ Video analysis health check: FAILED - {e}")
    
    # Test 4: Video analysis root endpoint
    try:
        response = requests.get(f"{base_url}/video-analysis/", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print("✅ Video analysis root endpoint: PASSED")
            print(f"   Service: {data.get('service')}")
        else:
            print(f"❌ Video analysis root endpoint: FAILED ({response.status_code})")
    except Exception as e:
        print(f"❌ Video analysis root endpoint: FAILED - {e}")
    
    # Test 5: List filtered files endpoint
    try:
        response = requests.get(f"{base_url}/video-analysis/files/filtered", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print("✅ List filtered files: PASSED")
            print(f"   Files found: {len(data.get('files', []))}")
        else:
            print(f"❌ List filtered files: FAILED ({response.status_code})")
    except Exception as e:
        print(f"❌ List filtered files: FAILED - {e}")
    
    # Test 6: Original Sherlock functionality
    try:
        response = requests.get(f"{base_url}/enabled_models", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print("✅ Sherlock enabled models: PASSED")
            print(f"   Models available: {len(data.get('models', []))}")
        else:
            print(f"❌ Sherlock enabled models: FAILED ({response.status_code})")
    except Exception as e:
        print(f"❌ Sherlock enabled models: FAILED - {e}")
    
    print("\n" + "=" * 50)
    print("🎉 Integration test completed!")
    print("\n📋 Next steps:")
    print("1. Test video upload: Use a video file with the /video-analysis/upload endpoint")
    print("2. Configure AWS credentials for full functionality")
    print("3. Test with frontend application")
    
    return True

if __name__ == "__main__":
    print("Starting integration test...")
    print("Make sure the main API is running on http://localhost:8000\n")
    
    try:
        success = test_integration()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
        sys.exit(1)