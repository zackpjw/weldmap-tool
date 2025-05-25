#!/usr/bin/env python3
"""
Backend API Testing for Enhanced Interactive Weld Mapping Tool
Tests all API endpoints including the new PDF export functionality
"""

import requests
import sys
import json
import base64
import io
from datetime import datetime
from pathlib import Path

class WeldMappingAPITester:
    def __init__(self, base_url="https://76bc3e74-4f74-46aa-beb2-e7031504ecb0.preview.emergentagent.com"):
        self.base_url = base_url
        self.tests_run = 0
        self.tests_passed = 0
        self.session = requests.Session()
        self.test_images = []
        self.test_filename = ""

    def log_test(self, name, success, details=""):
        """Log test results"""
        self.tests_run += 1
        if success:
            self.tests_passed += 1
            print(f"✅ {name} - PASSED {details}")
        else:
            print(f"❌ {name} - FAILED {details}")
        return success

    def create_test_pdf(self):
        """Create a simple test PDF for upload testing"""
        try:
            from reportlab.pdfgen import canvas
            from reportlab.lib.pagesizes import letter
            
            buffer = io.BytesIO()
            pdf_canvas = canvas.Canvas(buffer, pagesize=letter)
            pdf_canvas.drawString(100, 750, "Test Weld Mapping Drawing")
            pdf_canvas.drawString(100, 700, "This is a test PDF for symbol placement")
            pdf_canvas.line(100, 650, 500, 650)  # Simple line drawing
            pdf_canvas.save()
            buffer.seek(0)
            return buffer.getvalue()
        except ImportError:
            # Fallback: create minimal PDF content
            pdf_content = b"""%PDF-1.4
1 0 obj
<<
/Type /Catalog
/Pages 2 0 R
>>
endobj

2 0 obj
<<
/Type /Pages
/Kids [3 0 R]
/Count 1
>>
endobj

3 0 obj
<<
/Type /Page
/Parent 2 0 R
/MediaBox [0 0 612 792]
/Contents 4 0 R
>>
endobj

4 0 obj
<<
/Length 44
>>
stream
BT
/F1 12 Tf
100 700 Td
(Test PDF) Tj
ET
endstream
endobj

xref
0 5
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
0000000206 00000 n 
trailer
<<
/Size 5
/Root 1 0 R
>>
startxref
300
%%EOF"""
            return pdf_content

    def test_health_check(self):
        """Test the health check endpoint"""
        try:
            response = self.session.get(f"{self.base_url}/api/health", timeout=10)
            success = response.status_code == 200
            
            if success:
                data = response.json()
                expected_keys = ["status", "service"]
                has_keys = all(key in data for key in expected_keys)
                success = has_keys and data.get("status") == "healthy"
                details = f"- Status: {data.get('status')}, Service: {data.get('service')}"
            else:
                details = f"- Status Code: {response.status_code}"
                
            return self.log_test("Health Check", success, details)
            
        except Exception as e:
            return self.log_test("Health Check", False, f"- Error: {str(e)}")

    def test_pdf_upload(self):
        """Test PDF upload and conversion to images"""
        try:
            # Create test PDF
            pdf_content = self.create_test_pdf()
            
            # Prepare multipart form data
            files = {
                'file': ('test_drawing.pdf', pdf_content, 'application/pdf')
            }
            
            response = self.session.post(
                f"{self.base_url}/api/upload-pdf-only",
                files=files,
                timeout=30
            )
            
            success = response.status_code == 200
            
            if success:
                data = response.json()
                required_keys = ["success", "file_id", "filename", "total_pages", "images"]
                has_keys = all(key in data for key in required_keys)
                
                if has_keys:
                    success = (
                        data.get("success") == True and
                        data.get("total_pages") > 0 and
                        len(data.get("images", [])) > 0
                    )
                    details = f"- Pages: {data.get('total_pages')}, Images: {len(data.get('images', []))}"
                    
                    # Store for later tests
                    self.test_images = data.get("images", [])
                    self.test_filename = data.get("filename", "test_drawing.pdf")
                else:
                    success = False
                    details = f"- Missing required keys: {[k for k in required_keys if k not in data]}"
            else:
                details = f"- Status Code: {response.status_code}, Response: {response.text[:200]}"
                
            return self.log_test("PDF Upload", success, details)
            
        except Exception as e:
            return self.log_test("PDF Upload", False, f"- Error: {str(e)}")

    def test_pdf_export(self):
        """Test NEW PDF export with symbols functionality"""
        try:
            # Need images from upload test
            if not self.test_images:
                return self.log_test("PDF Export", False, "- No test images available (upload test must pass first)")
            
            # Create test project data with all 5 symbol types
            test_symbols = [
                {
                    "id": 1,
                    "type": "field_weld",
                    "x": 100,
                    "y": 100,
                    "page": 0
                },
                {
                    "id": 2,
                    "type": "shop_weld",
                    "x": 200,
                    "y": 150,
                    "page": 0
                },
                {
                    "id": 3,
                    "type": "pipe_section",
                    "x": 300,
                    "y": 200,
                    "page": 0
                },
                {
                    "id": 4,
                    "type": "pipe_support",
                    "x": 400,
                    "y": 250,
                    "page": 0
                },
                {
                    "id": 5,
                    "type": "flange_joint",
                    "x": 500,
                    "y": 300,
                    "page": 0
                }
            ]
            
            project_data = {
                "filename": "test_weld_mapping",
                "symbols": test_symbols,
                "images": self.test_images
            }
            
            response = self.session.post(
                f"{self.base_url}/api/export-pdf",
                json=project_data,
                timeout=30
            )
            
            success = response.status_code == 200
            
            if success:
                # Check if response is PDF
                content_type = response.headers.get('content-type', '')
                is_pdf = 'application/pdf' in content_type
                
                if is_pdf:
                    pdf_size = len(response.content)
                    details = f"- PDF generated successfully, Size: {pdf_size} bytes, Symbols: {len(test_symbols)}"
                    success = pdf_size > 1000  # Reasonable PDF size check
                else:
                    success = False
                    details = f"- Wrong content type: {content_type}"
            else:
                details = f"- Status Code: {response.status_code}, Response: {response.text[:200]}"
                
            return self.log_test("PDF Export with Symbols", success, details)
            
        except Exception as e:
            return self.log_test("PDF Export with Symbols", False, f"- Error: {str(e)}")

    def test_export_annotations(self):
        """Test annotations export endpoint"""
        try:
            test_annotations = {
                "symbols": [
                    {"id": 1, "type": "field_weld", "x": 100, "y": 100},
                    {"id": 2, "type": "shop_weld", "x": 200, "y": 200}
                ],
                "project_name": "test_annotations"
            }
            
            response = self.session.post(
                f"{self.base_url}/api/export-annotations",
                json=test_annotations,
                timeout=10
            )
            
            success = response.status_code == 200
            
            if success:
                data = response.json()
                expected_keys = ["success", "message", "symbols_count"]
                has_keys = all(key in data for key in expected_keys)
                
                if has_keys:
                    success = (
                        data.get("success") == True and
                        data.get("symbols_count") == 2
                    )
                    details = f"- Symbols processed: {data.get('symbols_count')}"
                else:
                    success = False
                    details = f"- Missing keys: {[k for k in expected_keys if k not in data]}"
            else:
                details = f"- Status Code: {response.status_code}"
                
            return self.log_test("Export Annotations", success, details)
            
        except Exception as e:
            return self.log_test("Export Annotations", False, f"- Error: {str(e)}")

    def test_invalid_requests(self):
        """Test error handling for invalid requests"""
        tests = [
            {
                "name": "Invalid PDF Upload (non-PDF file)",
                "method": "POST",
                "endpoint": "/api/upload-pdf-only",
                "files": {'file': ('test.txt', b'not a pdf', 'text/plain')},
                "expected_status": 400
            },
            {
                "name": "PDF Export without data",
                "method": "POST", 
                "endpoint": "/api/export-pdf",
                "json": {},
                "expected_status": 400
            },
            {
                "name": "Invalid endpoint",
                "method": "GET",
                "endpoint": "/api/nonexistent",
                "expected_status": 404
            }
        ]
        
        passed = 0
        for test in tests:
            try:
                if test["method"] == "POST":
                    if "files" in test:
                        response = self.session.post(
                            f"{self.base_url}{test['endpoint']}",
                            files=test["files"],
                            timeout=10
                        )
                    else:
                        response = self.session.post(
                            f"{self.base_url}{test['endpoint']}",
                            json=test.get("json", {}),
                            timeout=10
                        )
                elif test["method"] == "GET":
                    response = self.session.get(
                        f"{self.base_url}{test['endpoint']}",
                        timeout=10
                    )
                
                success = response.status_code == test["expected_status"]
                details = f"- Expected: {test['expected_status']}, Got: {response.status_code}"
                
                if self.log_test(test["name"], success, details):
                    passed += 1
                    
            except Exception as e:
                self.log_test(test["name"], False, f"- Error: {str(e)}")
        
        return passed == len(tests)

    def run_all_tests(self):
        """Run all backend API tests"""
        print("🚀 Starting Enhanced Weld Mapping Tool Backend API Tests")
        print("=" * 60)
        
        # Test sequence - order matters for dependencies
        tests = [
            ("Health Check", self.test_health_check),
            ("PDF Upload", self.test_pdf_upload),
            ("PDF Export with Symbols", self.test_pdf_export),
            ("Export Annotations", self.test_export_annotations),
            ("Invalid Requests", self.test_invalid_requests)
        ]
        
        for test_name, test_func in tests:
            print(f"\n🔍 Running: {test_name}")
            test_func()
        
        # Summary
        print("\n" + "=" * 60)
        print(f"📊 Test Results: {self.tests_passed}/{self.tests_run} tests passed")
        
        if self.tests_passed == self.tests_run:
            print("🎉 All backend tests PASSED! API is working correctly.")
            return True
        else:
            print(f"⚠️  {self.tests_run - self.tests_passed} tests FAILED. Check the issues above.")
            return False

def main():
    """Main test execution"""
    tester = WeldMappingAPITester()
    success = tester.run_all_tests()
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())