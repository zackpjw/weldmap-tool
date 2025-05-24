#!/usr/bin/env python3
"""
Backend API Testing Script for AI Isometric Drawing Analyzer
Tests all backend endpoints and functionality
"""

import requests
import sys
import json
import base64
import io
from datetime import datetime
from pathlib import Path

class WeldMappingAPITester:
    def __init__(self, base_url="https://45b4a450-e70c-45ba-a028-4de54af09736.preview.emergentagent.com"):
        self.base_url = base_url
        self.tests_run = 0
        self.tests_passed = 0

    def run_test(self, name, method, endpoint, expected_status, data=None, files=None):
        """Run a single API test"""
        url = f"{self.base_url}/{endpoint}"
        headers = {}
        
        self.tests_run += 1
        print(f"\n🔍 Testing {name}...")
        print(f"   URL: {url}")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, timeout=30)
            elif method == 'POST':
                if files:
                    response = requests.post(url, files=files, timeout=60)
                else:
                    headers['Content-Type'] = 'application/json'
                    response = requests.post(url, json=data, headers=headers, timeout=30)

            success = response.status_code == expected_status
            if success:
                self.tests_passed += 1
                print(f"✅ Passed - Status: {response.status_code}")
                try:
                    response_data = response.json()
                    print(f"   Response keys: {list(response_data.keys()) if isinstance(response_data, dict) else 'Non-dict response'}")
                except:
                    print(f"   Response: {response.text[:200]}...")
            else:
                print(f"❌ Failed - Expected {expected_status}, got {response.status_code}")
                print(f"   Response: {response.text[:500]}...")

            return success, response.json() if success and response.content else {}

        except Exception as e:
            print(f"❌ Failed - Error: {str(e)}")
            return False, {}

    def create_test_pdf(self):
        """Create a simple test PDF for upload testing"""
        try:
            # Create a simple PDF-like content (this is a mock - in real scenario we'd use a proper PDF)
            # For testing purposes, we'll create a small binary file that mimics a PDF
            pdf_content = b"%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n/Pages 2 0 R\n>>\nendobj\n2 0 obj\n<<\n/Type /Pages\n/Kids [3 0 R]\n/Count 1\n>>\nendobj\n3 0 obj\n<<\n/Type /Page\n/Parent 2 0 R\n/MediaBox [0 0 612 792]\n>>\nendobj\nxref\n0 4\n0000000000 65535 f \n0000000009 00000 n \n0000000074 00000 n \n0000000120 00000 n \ntrailer\n<<\n/Size 4\n/Root 1 0 R\n>>\nstartxref\n179\n%%EOF"
            return pdf_content
        except Exception as e:
            print(f"Error creating test PDF: {e}")
            return None

    def test_health_check(self):
        """Test health check endpoint"""
        success, response = self.run_test(
            "Health Check",
            "GET",
            "api/health",
            200
        )
        if success:
            expected_keys = ['status', 'service']
            for key in expected_keys:
                if key not in response:
                    print(f"⚠️  Warning: Missing expected key '{key}' in health response")
        return success

    def test_pdf_upload_invalid_file(self):
        """Test PDF upload with invalid file type"""
        # Create a text file instead of PDF
        text_content = b"This is not a PDF file"
        files = {'file': ('test.txt', io.BytesIO(text_content), 'text/plain')}
        
        success, response = self.run_test(
            "PDF Upload - Invalid File Type",
            "POST",
            "api/upload-pdf-only",
            400,
            files=files
        )
        return success

    def test_pdf_upload_no_file(self):
        """Test PDF upload without file"""
        success, response = self.run_test(
            "PDF Upload - No File",
            "POST",
            "api/upload-pdf-only",
            422  # FastAPI validation error
        )
        return success

    def test_pdf_upload_valid_file(self):
        """Test PDF upload with valid PDF file"""
        pdf_content = self.create_test_pdf()
        if not pdf_content:
            print("❌ Could not create test PDF")
            return False
            
        files = {'file': ('test_drawing.pdf', io.BytesIO(pdf_content), 'application/pdf')}
        
        success, response = self.run_test(
            "PDF Upload - Valid PDF",
            "POST",
            "api/upload-pdf-only",
            200,
            files=files
        )
        
        if success:
            # Validate response structure
            expected_keys = ['success', 'file_id', 'filename', 'total_pages', 'images', 'message']
            for key in expected_keys:
                if key not in response:
                    print(f"⚠️  Warning: Missing expected key '{key}' in upload response")
                    return False
            
            # Validate response values
            if response.get('success') != True:
                print("⚠️  Warning: Success flag is not True")
                return False
                
            if not response.get('file_id'):
                print("⚠️  Warning: No file_id in response")
                return False
                
            if response.get('filename') != 'test_drawing.pdf':
                print("⚠️  Warning: Filename mismatch")
                
            if not isinstance(response.get('images'), list):
                print("⚠️  Warning: Images is not a list")
                return False
                
            print(f"   ✅ PDF processed successfully: {response.get('total_pages')} pages")
            print(f"   ✅ File ID: {response.get('file_id')}")
            print(f"   ✅ Images count: {len(response.get('images', []))}")
            
            return True
        
        return success

    def test_export_annotations(self):
        """Test export annotations endpoint"""
        test_annotations = {
            "symbols": [
                {"id": 1, "type": "field_weld", "x": 100, "y": 150, "page": 0},
                {"id": 2, "type": "shop_weld", "x": 200, "y": 250, "page": 0}
            ],
            "page": 0,
            "filename": "test_drawing.pdf"
        }
        
        success, response = self.run_test(
            "Export Annotations",
            "POST",
            "api/export-annotations",
            200,
            data=test_annotations
        )
        
        if success:
            expected_keys = ['success', 'message', 'symbols_count']
            for key in expected_keys:
                if key not in response:
                    print(f"⚠️  Warning: Missing expected key '{key}' in export response")
                    
            if response.get('symbols_count') != 2:
                print(f"⚠️  Warning: Expected 2 symbols, got {response.get('symbols_count')}")
                
        return success

    def test_invalid_endpoint(self):
        """Test invalid endpoint"""
        success, response = self.run_test(
            "Invalid Endpoint",
            "GET",
            "api/nonexistent",
            404
        )
        return success

def main():
    print("🚀 Starting Interactive Weld Mapping Tool API Tests")
    print("=" * 60)
    
    # Setup
    tester = WeldMappingAPITester()
    
    # Run all tests
    print("\n📋 Running Backend API Tests...")
    
    # Test 1: Health Check
    tester.test_health_check()
    
    # Test 2: Invalid file upload
    tester.test_pdf_upload_invalid_file()
    
    # Test 3: No file upload
    tester.test_pdf_upload_no_file()
    
    # Test 4: Valid PDF upload (main functionality)
    tester.test_pdf_upload_valid_file()
    
    # Test 5: Export annotations
    tester.test_export_annotations()
    
    # Test 6: Invalid endpoint
    tester.test_invalid_endpoint()
    
    # Print final results
    print("\n" + "=" * 60)
    print(f"📊 FINAL RESULTS: {tester.tests_passed}/{tester.tests_run} tests passed")
    
    if tester.tests_passed == tester.tests_run:
        print("🎉 All backend API tests PASSED!")
        return 0
    else:
        print(f"⚠️  {tester.tests_run - tester.tests_passed} tests FAILED")
        return 1

if __name__ == "__main__":
    sys.exit(main())