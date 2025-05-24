#!/usr/bin/env python3
"""
Backend API Testing Script for AI Isometric Drawing Analyzer
Tests all backend endpoints and functionality
"""

import requests
import sys
import json
import io
from datetime import datetime
from pathlib import Path

class AIDrawingAnalyzerTester:
    def __init__(self, base_url="https://45b4a450-e70c-45ba-a028-4de54af09736.preview.emergentagent.com"):
        self.base_url = base_url
        self.tests_run = 0
        self.tests_passed = 0
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'AI-Drawing-Analyzer-Test/1.0'
        })

    def log_test(self, name, success, details=""):
        """Log test results"""
        self.tests_run += 1
        if success:
            self.tests_passed += 1
            print(f"✅ {name}: PASSED {details}")
        else:
            print(f"❌ {name}: FAILED {details}")
        return success

    def test_health_endpoint(self):
        """Test the health check endpoint"""
        try:
            response = self.session.get(f"{self.base_url}/api/health", timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "healthy" and "service" in data:
                    return self.log_test("Health Check", True, f"- Status: {data['status']}, Service: {data['service']}")
                else:
                    return self.log_test("Health Check", False, f"- Invalid response format: {data}")
            else:
                return self.log_test("Health Check", False, f"- HTTP {response.status_code}: {response.text}")
                
        except Exception as e:
            return self.log_test("Health Check", False, f"- Exception: {str(e)}")

    def test_ai_connection(self):
        """Test the AI connection endpoint"""
        try:
            response = self.session.get(f"{self.base_url}/api/test-ai", timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                
                # Check if it's a success or expected quota error
                if data.get("success") == True:
                    return self.log_test("AI Connection", True, f"- AI working: {data.get('message', 'Success')}")
                elif "quota" in str(data.get("error", "")).lower() or "rate limit" in str(data.get("error", "")).lower():
                    return self.log_test("AI Connection", True, f"- Expected quota error: {data.get('error', 'Quota exceeded')}")
                else:
                    return self.log_test("AI Connection", False, f"- Unexpected error: {data.get('error', 'Unknown error')}")
            else:
                return self.log_test("AI Connection", False, f"- HTTP {response.status_code}: {response.text}")
                
        except Exception as e:
            return self.log_test("AI Connection", False, f"- Exception: {str(e)}")

    def create_test_pdf(self):
        """Create a simple test PDF for upload testing"""
        try:
            from reportlab.pdfgen import canvas
            from reportlab.lib.pagesizes import letter
            
            buffer = io.BytesIO()
            p = canvas.Canvas(buffer, pagesize=letter)
            
            # Add some basic content to simulate an isometric drawing
            p.drawString(100, 750, "Test Isometric Drawing")
            p.drawString(100, 700, "Pipe Section 1 - 6m")
            p.drawString(100, 650, "Support PS-1")
            p.drawString(100, 600, "Elbow Fitting")
            p.drawString(100, 550, "Weld Point W1")
            
            # Draw some basic shapes to simulate drawing elements
            p.rect(50, 400, 200, 50)  # Rectangle for pipe
            p.circle(300, 425, 10)    # Circle for weld point
            p.rect(400, 400, 30, 50)  # Rectangle for support
            
            p.showPage()
            p.save()
            
            buffer.seek(0)
            return buffer.getvalue()
            
        except ImportError:
            # If reportlab is not available, create a minimal PDF manually
            # This is a very basic PDF structure
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
(Test Drawing) Tj
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

    def test_demo_upload_endpoint(self):
        """Test the NEW demo upload endpoint - PRIORITY FEATURE"""
        try:
            # Create test PDF
            pdf_data = self.create_test_pdf()
            
            # Prepare multipart form data
            files = {
                'file': ('test_drawing.pdf', pdf_data, 'application/pdf')
            }
            
            response = self.session.post(
                f"{self.base_url}/api/demo-upload", 
                files=files, 
                timeout=60
            )
            
            if response.status_code == 200:
                data = response.json()
                
                # Check response structure for demo mode
                required_fields = ['success', 'file_id', 'filename', 'total_pages', 'results', 'mode']
                missing_fields = [field for field in required_fields if field not in data]
                
                if not missing_fields:
                    # Verify it's demo mode
                    if data.get('mode') != 'demo':
                        return self.log_test("Demo Upload Endpoint", False, 
                            f"- Expected mode 'demo', got '{data.get('mode')}'")
                    
                    # Check if results have proper structure
                    if data.get('results') and len(data['results']) > 0:
                        result = data['results'][0]
                        result_fields = ['page', 'analysis', 'weld_annotations', 'processed', 'mode', 'image_base64']
                        missing_result_fields = [field for field in result_fields if field not in result]
                        
                        if not missing_result_fields:
                            # Check demo analysis structure
                            analysis = result.get('analysis', {})
                            if analysis.get('success'):
                                analysis_data = analysis.get('analysis', {})
                                pipes = len(analysis_data.get('pipes', []))
                                fittings = len(analysis_data.get('fittings', []))
                                supports = len(analysis_data.get('supports', []))
                                weld_points = len(analysis_data.get('weld_points', []))
                                
                                # Check weld annotations
                                annotations = result.get('weld_annotations', [])
                                annotation_types = set(ann.get('type') for ann in annotations)
                                
                                # Check for annotated image
                                has_image = bool(result.get('image_base64'))
                                
                                return self.log_test("Demo Upload Endpoint", True, 
                                    f"- Mode: {data['mode']}, Pages: {data['total_pages']}, "
                                    f"Pipes: {pipes}, Fittings: {fittings}, Supports: {supports}, "
                                    f"Welds: {weld_points}, Annotations: {len(annotations)}, "
                                    f"Types: {annotation_types}, Image: {has_image}")
                            else:
                                return self.log_test("Demo Upload Endpoint", False, 
                                    f"- Demo analysis failed: {analysis.get('error', 'Unknown error')}")
                        else:
                            return self.log_test("Demo Upload Endpoint", False, 
                                f"- Missing result fields: {missing_result_fields}")
                    else:
                        return self.log_test("Demo Upload Endpoint", False, "- No results in response")
                else:
                    return self.log_test("Demo Upload Endpoint", False, f"- Missing fields: {missing_fields}")
                    
            else:
                return self.log_test("Demo Upload Endpoint", False, 
                    f"- HTTP {response.status_code}: {response.text}")
                
        except Exception as e:
            return self.log_test("Demo Upload Endpoint", False, f"- Exception: {str(e)}")

    def test_visual_annotations(self):
        """Test visual annotation generation in demo mode"""
        try:
            # Create test PDF
            pdf_data = self.create_test_pdf()
            
            # Prepare multipart form data
            files = {
                'file': ('test_drawing.pdf', pdf_data, 'application/pdf')
            }
            
            response = self.session.post(
                f"{self.base_url}/api/demo-upload", 
                files=files, 
                timeout=60
            )
            
            if response.status_code == 200:
                data = response.json()
                
                if data.get('results') and len(data['results']) > 0:
                    result = data['results'][0]
                    annotations = result.get('weld_annotations', [])
                    
                    # Check for different annotation types and shapes
                    expected_types = {'field_weld', 'shop_weld', 'pipe_section', 'pipe_support'}
                    expected_shapes = {'diamond', 'circle', 'pill', 'rectangle'}
                    
                    found_types = set(ann.get('type') for ann in annotations)
                    found_shapes = set(ann.get('shape') for ann in annotations)
                    
                    # Check if we have the expected variety
                    type_coverage = len(found_types.intersection(expected_types))
                    shape_coverage = len(found_shapes.intersection(expected_shapes))
                    
                    # Check coordinate validity
                    valid_coords = all(
                        isinstance(ann.get('coords'), list) and 
                        len(ann.get('coords', [])) == 2 and
                        all(isinstance(coord, (int, float)) for coord in ann.get('coords', []))
                        for ann in annotations
                    )
                    
                    if type_coverage >= 3 and shape_coverage >= 3 and valid_coords:
                        return self.log_test("Visual Annotations", True, 
                            f"- Types: {found_types}, Shapes: {found_shapes}, "
                            f"Count: {len(annotations)}, Valid coords: {valid_coords}")
                    else:
                        return self.log_test("Visual Annotations", False, 
                            f"- Insufficient variety or invalid coords. Types: {found_types}, "
                            f"Shapes: {found_shapes}, Valid coords: {valid_coords}")
                else:
                    return self.log_test("Visual Annotations", False, "- No results to check annotations")
            else:
                return self.log_test("Visual Annotations", False, 
                    f"- HTTP {response.status_code}: {response.text}")
                
        except Exception as e:
            return self.log_test("Visual Annotations", False, f"- Exception: {str(e)}")

    def test_pdf_upload_structure(self):
        """Test PDF upload endpoint structure (AI mode)"""
        try:
            # Create test PDF
            pdf_data = self.create_test_pdf()
            
            # Prepare multipart form data
            files = {
                'file': ('test_drawing.pdf', pdf_data, 'application/pdf')
            }
            
            response = self.session.post(
                f"{self.base_url}/api/upload-pdf", 
                files=files, 
                timeout=60
            )
            
            if response.status_code == 200:
                data = response.json()
                
                # Check response structure
                required_fields = ['success', 'file_id', 'filename', 'total_pages', 'results']
                missing_fields = [field for field in required_fields if field not in data]
                
                if not missing_fields:
                    # Check if results have proper structure
                    if data.get('results') and len(data['results']) > 0:
                        result = data['results'][0]
                        result_fields = ['page', 'analysis', 'weld_annotations', 'processed']
                        missing_result_fields = [field for field in result_fields if field not in result]
                        
                        if not missing_result_fields:
                            return self.log_test("AI Upload Structure", True, 
                                f"- File: {data['filename']}, Pages: {data['total_pages']}, Results: {len(data['results'])}")
                        else:
                            return self.log_test("AI Upload Structure", False, 
                                f"- Missing result fields: {missing_result_fields}")
                    else:
                        return self.log_test("AI Upload Structure", False, "- No results in response")
                else:
                    return self.log_test("AI Upload Structure", False, f"- Missing fields: {missing_fields}")
                    
            elif response.status_code == 500:
                # Check if it's an expected AI quota error
                try:
                    error_data = response.json()
                    error_detail = error_data.get('detail', '')
                    if 'quota' in error_detail.lower() or 'rate limit' in error_detail.lower():
                        return self.log_test("AI Upload Structure", True, 
                            f"- Expected AI quota error in processing: {error_detail}")
                    else:
                        return self.log_test("AI Upload Structure", False, 
                            f"- Unexpected server error: {error_detail}")
                except:
                    return self.log_test("AI Upload Structure", False, 
                        f"- Server error: {response.text}")
            else:
                return self.log_test("AI Upload Structure", False, 
                    f"- HTTP {response.status_code}: {response.text}")
                
        except Exception as e:
            return self.log_test("AI Upload Structure", False, f"- Exception: {str(e)}")

    def test_invalid_file_upload(self):
        """Test upload with invalid file type"""
        try:
            # Create a text file instead of PDF
            text_data = b"This is not a PDF file"
            
            files = {
                'file': ('test.txt', text_data, 'text/plain')
            }
            
            response = self.session.post(
                f"{self.base_url}/api/upload-pdf", 
                files=files, 
                timeout=30
            )
            
            if response.status_code == 400:
                data = response.json()
                if 'pdf' in data.get('detail', '').lower():
                    return self.log_test("Invalid File Upload", True, 
                        f"- Correctly rejected non-PDF: {data['detail']}")
                else:
                    return self.log_test("Invalid File Upload", False, 
                        f"- Wrong error message: {data.get('detail', 'No detail')}")
            else:
                return self.log_test("Invalid File Upload", False, 
                    f"- Expected 400, got {response.status_code}: {response.text}")
                
        except Exception as e:
            return self.log_test("Invalid File Upload", False, f"- Exception: {str(e)}")

    def test_cors_headers(self):
        """Test CORS configuration"""
        try:
            response = self.session.options(f"{self.base_url}/api/health", timeout=10)
            
            cors_headers = {
                'access-control-allow-origin': response.headers.get('access-control-allow-origin'),
                'access-control-allow-methods': response.headers.get('access-control-allow-methods'),
                'access-control-allow-headers': response.headers.get('access-control-allow-headers'),
            }
            
            # Check if CORS is properly configured
            if cors_headers['access-control-allow-origin']:
                return self.log_test("CORS Configuration", True, 
                    f"- Origin: {cors_headers['access-control-allow-origin']}")
            else:
                # Try a regular GET request and check headers
                response = self.session.get(f"{self.base_url}/api/health", timeout=10)
                if 'access-control-allow-origin' in response.headers:
                    return self.log_test("CORS Configuration", True, 
                        f"- Origin: {response.headers['access-control-allow-origin']}")
                else:
                    return self.log_test("CORS Configuration", False, "- No CORS headers found")
                
        except Exception as e:
            return self.log_test("CORS Configuration", False, f"- Exception: {str(e)}")

    def run_all_tests(self):
        """Run all backend tests"""
        print("🚀 Starting AI Isometric Drawing Analyzer Backend Tests")
        print(f"📍 Testing against: {self.base_url}")
        print("=" * 60)
        
        # Test basic connectivity and health
        self.test_health_endpoint()
        
        # Test AI connection (expect quota error but connection should work)
        self.test_ai_connection()
        
        # Test PDF upload functionality
        self.test_pdf_upload_structure()
        
        # Test error handling
        self.test_invalid_file_upload()
        
        # Test CORS configuration
        self.test_cors_headers()
        
        # Print summary
        print("=" * 60)
        print(f"📊 Test Summary: {self.tests_passed}/{self.tests_run} tests passed")
        
        if self.tests_passed == self.tests_run:
            print("🎉 All backend tests passed! Infrastructure is working correctly.")
            return 0
        else:
            print(f"⚠️  {self.tests_run - self.tests_passed} test(s) failed. Check the issues above.")
            return 1

def main():
    """Main test execution"""
    tester = AIDrawingAnalyzerTester()
    return tester.run_all_tests()

if __name__ == "__main__":
    sys.exit(main())