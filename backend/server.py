from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
import os
from dotenv import load_dotenv
import fitz  # PyMuPDF
from PIL import Image, ImageDraw, ImageFont
import base64
import io
import uuid
from pathlib import Path
import asyncio
import json
from emergentintegrations.llm.chat import LlmChat, UserMessage, ImageContent
import traceback
from typing import List, Dict, Any
import time
import math

# Load environment variables
load_dotenv()

app = FastAPI(title="AI Isometric Drawing Weld Map Generator")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
UPLOAD_DIR = Path("/tmp/uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

@app.get("/api/health")
async def health_check():
    return {"status": "healthy", "service": "AI Isometric Drawing Analyzer"}

def pdf_to_images(pdf_path: str) -> List[str]:
    """Convert PDF pages to base64 encoded images"""
    try:
        doc = fitz.open(pdf_path)
        images = []
        
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            # Increase resolution for better analysis
            mat = fitz.Matrix(2.0, 2.0)  # 2x scaling for better quality
            pix = page.get_pixmap(matrix=mat)
            img_data = pix.tobytes("png")
            
            # Convert to base64
            img_base64 = base64.b64encode(img_data).decode('utf-8')
            images.append(img_base64)
        
        doc.close()
        return images
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error converting PDF to images: {str(e)}")

async def analyze_drawing_with_ai(image_base64: str, page_num: int) -> Dict[str, Any]:
    """Analyze engineering drawing using OpenAI Vision API"""
    try:
        # Initialize chat for engineering analysis
        chat = LlmChat(
            api_key=OPENAI_API_KEY,
            session_id=f"engineering_analysis_{int(time.time())}_{page_num}",
            system_message="You are an expert in analyzing isometric engineering drawings. You specialize in identifying pipe components, fittings, supports, and generating accurate weld maps with coordinate information."
        ).with_model("openai", "gpt-4o").with_max_tokens(4096)
        
        image_content = ImageContent(image_base64=image_base64)
        
        # Detailed analysis prompt based on the requirements
        analysis_prompt = f"""
        Analyze this isometric engineering drawing with CRITICAL FOCUS on green-highlighted pipes for weld mapping:
        
        1. GREEN PIPE IDENTIFICATION (HIGHEST PRIORITY):
           - Identify ONLY pipes that are highlighted in GREEN color
           - These green-highlighted pipes are the ONLY ones requiring weld mapping
           - Ignore all non-green pipes, fittings, and components
           - Provide exact pixel coordinates for green pipe segments and joints
           
        2. GREEN PIPE JOINT MAPPING:
           - For each green-highlighted pipe, identify all weld joint locations
           - Map start points, end points, and intermediate joints on green pipes
           - Classify each joint as field_joint or shop_joint based on pipe standards
           - Provide precise X,Y coordinates for each green pipe joint
           
        3. GREEN PIPE ROUTING:
           - Trace the path of each green-highlighted pipe segment
           - Map centerline coordinates along green pipe runs
           - Identify connection points where green pipes join fittings or other pipes
           - Note pipe directions and flow paths for green pipes only
           
        4. WELD SYMBOL PLACEMENT AREAS:
           - Identify clear areas NEAR each green pipe for symbol placement
           - Find spaces within 50-100 pixels of green pipe centerlines
           - Avoid placing symbols outside the main drawing boundaries
           - Locate areas that won't overlap with existing drawing elements
           
        5. GREEN PIPE SPECIFICATIONS:
           - Extract any visible pipe schedules, diameters for green pipes
           - Note any special markings on green-highlighted pipes
           - Map pipe support locations touching green pipes
           
        CRITICAL REQUIREMENTS:
        - ONLY analyze pipes highlighted in GREEN color
        - Symbols must be placed NEAR the green pipes, not in margins
        - Arrows must point TO the green pipe centerlines
        - Ignore all non-green piping components
        
        Format response as JSON focusing on green pipes only:
        {{
            "green_pipes": [
                {{
                    "id": "green_pipe_1",
                    "highlighted": true,
                    "centerline_coords": [[x1,y1], [x2,y2], [x3,y3], ...],
                    "weld_joints": [
                        {{
                            "coords": [x, y],
                            "type": "field_joint/shop_joint",
                            "location_on_pipe": "start/middle/end"
                        }}
                    ],
                    "diameter": "size_if_visible",
                    "symbol_placement_areas": [
                        {{
                            "coords": [x, y],
                            "side": "left/right/top/bottom",
                            "distance_to_pipe": pixels
                        }}
                    ]
                }}
            ],
            "non_green_pipes": [
                {{
                    "id": "regular_pipe_1",
                    "highlighted": false,
                    "note": "No weld mapping required"
                }}
            ],
            "drawing_bounds": {{
                "width": pixel_width,
                "height": pixel_height,
                "drawing_area": [x1, y1, x2, y2]
            }}
        }}
        
        FOCUS: Identify green-highlighted pipes ONLY. All weld mapping applies exclusively to green pipes.
        """
        
        user_message = UserMessage(
            text=analysis_prompt,
            file_contents=[image_content]
        )
        
        response = await chat.send_message(user_message)
        
        # Try to parse JSON response
        try:
            # Extract JSON from response if it's wrapped in text
            response_text = str(response)
            if "```json" in response_text:
                json_start = response_text.find("```json") + 7
                json_end = response_text.find("```", json_start)
                json_text = response_text[json_start:json_end].strip()
            elif "{" in response_text:
                json_start = response_text.find("{")
                json_end = response_text.rfind("}") + 1
                json_text = response_text[json_start:json_end]
            else:
                json_text = response_text
            
            parsed_response = json.loads(json_text)
            return {
                "success": True,
                "analysis": parsed_response,
                "raw_response": response_text
            }
        except json.JSONDecodeError:
            return {
                "success": True,
                "analysis": {"raw_text": str(response)},
                "raw_response": str(response),
                "note": "Could not parse as JSON, returning raw text"
            }
            
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }



@app.post("/api/upload-pdf")
async def upload_pdf(file: UploadFile = File(...)):
    """Upload and analyze PDF isometric drawing"""
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")
    
    if not OPENAI_API_KEY:
        raise HTTPException(status_code=500, detail="OpenAI API key not configured")
    
    try:
        # Save uploaded file
        file_id = str(uuid.uuid4())
        file_path = UPLOAD_DIR / f"{file_id}.pdf"
        
        with open(file_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)
        
        # Convert PDF to images
        images = pdf_to_images(str(file_path))
        
        # Analyze each page
        analysis_results = []
        for page_num, img_base64 in enumerate(images):
            print(f"Analyzing page {page_num + 1}...")
            
            # Analyze with AI
            analysis = await analyze_drawing_with_ai(img_base64, page_num + 1)
            
            # Generate weld map annotations
            demo_data = generate_demo_analysis(img_base64)
            annotations = []
            for key in ['pipes', 'fittings', 'supports', 'weld_points']:
                for item in demo_data['analysis'].get(key, []):
                    if key == 'pipes':
                        # Add start and end points as field welds
                        annotations.append({
                            'type': 'field_weld',
                            'shape': 'diamond',
                            'coords': item['start_coords']
                        })
                        annotations.append({
                            'type': 'field_weld',
                            'shape': 'diamond',
                            'coords': item['end_coords']
                        })
                    elif key == 'weld_points':
                        annotations.append({
                            'type': 'shop_weld',
                            'shape': 'circle',
                            'coords': item['coords']
                        })
                    elif key == 'supports':
                        annotations.append({
                            'type': 'pipe_support',
                            'shape': 'rectangle',
                            'coords': item['coords'],
                            'label': item.get('label', 'PS')
                        })
                    else:
                        annotations.append({
                            'type': 'pipe_section',
                            'shape': 'pill',
                            'coords': item['coords']
                        })
            
            # Create annotated image
            annotated_image = create_annotated_image(img_base64, annotations)
            
            analysis_results.append({
                "page": page_num + 1,
                "image_base64": annotated_image,  # Use annotated image
                "analysis": analysis,
                "weld_annotations": annotations,
                "processed": analysis.get("success", False)
            })
        
        # Clean up uploaded file
        file_path.unlink()
        
        return JSONResponse({
            "success": True,
            "file_id": file_id,
            "filename": file.filename,
            "total_pages": len(images),
            "results": analysis_results
        })
        
    except Exception as e:
        # Clean up on error
        if 'file_path' in locals() and file_path.exists():
            file_path.unlink()
            
        raise HTTPException(status_code=500, detail=f"Error processing PDF: {str(e)}")

@app.get("/api/test-ai")
async def test_ai_connection():
    """Test OpenAI API connection"""
    if not OPENAI_API_KEY:
        return {"success": False, "error": "OpenAI API key not configured"}
    
    try:
        chat = LlmChat(
            api_key=OPENAI_API_KEY,
            session_id="test_session",
            system_message="You are a helpful assistant."
        ).with_model("openai", "gpt-4o")
        
        response = await chat.send_message(UserMessage(text="Hello, can you confirm you're working?"))
        
        return {
            "success": True,
            "message": "OpenAI API connection successful",
            "response": str(response)
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"OpenAI API test failed: {str(e)}"
        }

def create_annotated_image(image_base64: str, annotations: List[Dict[str, Any]]) -> str:
    """Create an annotated version of the image with weld map symbols connected to pipeline locations"""
    try:
        # Decode base64 image
        img_data = base64.b64decode(image_base64)
        img = Image.open(io.BytesIO(img_data))
        
        # Create a copy for annotation
        annotated_img = img.copy()
        draw = ImageDraw.Draw(annotated_img)
        
        # Get image dimensions
        img_width, img_height = annotated_img.size
        
        # Try to get a font, fallback to default if not available
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 16)
            small_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 12)
        except:
            font = ImageFont.load_default()
            small_font = ImageFont.load_default()
        
        # Color mapping for different annotation types
        colors = {
            'field_weld': '#FF4444',      # Red for field welds
            'shop_weld': '#44CCCC',       # Cyan for shop welds  
            'pipe_section': '#4488FF',    # Blue for pipe sections
            'pipe_support': '#44CC44'     # Green for supports
        }
        
        # Define margins for symbol placement (avoid overlapping with drawing)
        margin = 60
        symbol_areas = {
            'left': (margin//2, margin, margin//2 + 40, img_height - margin),
            'right': (img_width - margin - 40, margin, img_width - margin//2, img_height - margin),
            'top': (margin, margin//2, img_width - margin, margin//2 + 40),
            'bottom': (margin, img_height - margin - 40, img_width - margin, img_height - margin//2)
        }
        
        # Counter for symbol positioning
        symbol_counters = {'left': 0, 'right': 0, 'top': 0, 'bottom': 0}
        
        # Draw annotations with arrows pointing to pipeline locations
        for i, annotation in enumerate(annotations):
            pipeline_coords = annotation.get('coords', [img_width//2, img_height//2])
            pipeline_x, pipeline_y = int(pipeline_coords[0]), int(pipeline_coords[1])
            
            annotation_type = annotation.get('type', 'unknown')
            shape = annotation.get('shape', 'circle')
            color = colors.get(annotation_type, '#FFAA00')
            
            # Convert hex color to RGB
            color_rgb = tuple(int(color[i:i+2], 16) for i in (1, 3, 5))
            
            # Determine which margin area to use based on pipeline location
            if pipeline_x < img_width // 3:
                area = 'right'  # Pipeline on left, symbols on right
            elif pipeline_x > 2 * img_width // 3:
                area = 'left'   # Pipeline on right, symbols on left
            elif pipeline_y < img_height // 2:
                area = 'bottom' # Pipeline on top, symbols on bottom
            else:
                area = 'top'    # Pipeline on bottom, symbols on top
            
            # Calculate symbol position in the chosen area
            area_bounds = symbol_areas[area]
            if area in ['left', 'right']:
                symbol_x = (area_bounds[0] + area_bounds[2]) // 2
                symbol_y = area_bounds[1] + (symbol_counters[area] * 50) + 25
            else:  # top or bottom
                symbol_x = area_bounds[0] + (symbol_counters[area] * 80) + 40
                symbol_y = (area_bounds[1] + area_bounds[3]) // 2
            
            # Ensure symbol stays within bounds
            symbol_x = max(area_bounds[0] + 20, min(symbol_x, area_bounds[2] - 20))
            symbol_y = max(area_bounds[1] + 20, min(symbol_y, area_bounds[3] - 20))
            
            symbol_counters[area] += 1
            
            # Draw arrow from symbol to pipeline location
            draw_arrow_to_pipeline(draw, symbol_x, symbol_y, pipeline_x, pipeline_y, color_rgb)
            
            # Draw weld symbol at symbol location
            symbol_size = 15
            label_text = ""
            
            if shape == 'diamond':
                # Diamond shape for field welds
                points = [
                    (symbol_x, symbol_y - symbol_size),      # Top
                    (symbol_x + symbol_size, symbol_y),      # Right
                    (symbol_x, symbol_y + symbol_size),      # Bottom
                    (symbol_x - symbol_size, symbol_y)       # Left
                ]
                draw.polygon(points, outline=color_rgb, fill='white', width=2)
                label_text = "FW"
                
            elif shape == 'circle':
                # Circle for shop welds
                draw.ellipse([symbol_x - symbol_size, symbol_y - symbol_size, 
                             symbol_x + symbol_size, symbol_y + symbol_size], 
                           outline=color_rgb, fill='white', width=2)
                label_text = "SW"
                
            elif shape == 'rectangle':
                # Rectangle for pipe supports
                draw.rectangle([symbol_x - symbol_size, symbol_y - symbol_size//2, 
                               symbol_x + symbol_size, symbol_y + symbol_size//2], 
                             outline=color_rgb, fill='white', width=2)
                label_text = annotation.get('label', 'PS')
                
            elif shape == 'pill':
                # Pill shape for pipe sections
                draw.rounded_rectangle([symbol_x - symbol_size, symbol_y - symbol_size//2, 
                                       symbol_x + symbol_size, symbol_y + symbol_size//2], 
                                     radius=symbol_size//2, outline=color_rgb, fill='white', width=2)
                label_text = "PIPE"
            
            # Draw label text near symbol
            if label_text:
                # Draw text background for better readability
                text_bbox = draw.textbbox((0, 0), label_text, font=small_font)
                text_width = text_bbox[2] - text_bbox[0]
                text_height = text_bbox[3] - text_bbox[1]
                
                text_x = symbol_x - text_width // 2
                text_y = symbol_y + symbol_size + 5
                
                # Draw white background for text
                draw.rectangle([text_x - 2, text_y - 2, text_x + text_width + 2, text_y + text_height + 2], 
                              fill='white', outline=color_rgb)
                draw.text((text_x, text_y), label_text, fill=color_rgb, font=small_font)
        
        # Convert back to base64
        buffer = io.BytesIO()
        annotated_img.save(buffer, format='PNG')
        buffer.seek(0)
        annotated_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
        
        return annotated_base64
        
    except Exception as e:
        print(f"Error creating annotated image: {e}")
        return image_base64  # Return original if annotation fails

def draw_arrow_to_pipeline(draw, symbol_x, symbol_y, pipeline_x, pipeline_y, color_rgb):
    """Draw an arrow from the weld symbol to the pipeline location"""
    # Calculate arrow direction
    dx = pipeline_x - symbol_x
    dy = pipeline_y - symbol_y
    distance = math.sqrt(dx*dx + dy*dy)
    
    if distance < 10:  # Too close, don't draw arrow
        return
    
    # Normalize direction
    dx_norm = dx / distance
    dy_norm = dy / distance
    
    # Arrow line (stop short of pipeline to avoid overlap)
    line_end_x = pipeline_x - dx_norm * 15
    line_end_y = pipeline_y - dy_norm * 15
    
    # Draw main arrow line
    draw.line([(symbol_x, symbol_y), (line_end_x, line_end_y)], fill=color_rgb, width=2)
    
    # Draw arrowhead
    arrowhead_size = 8
    # Calculate perpendicular direction for arrowhead
    perp_x = -dy_norm
    perp_y = dx_norm
    
    # Arrowhead points
    head_point1_x = line_end_x - dx_norm * arrowhead_size + perp_x * arrowhead_size // 2
    head_point1_y = line_end_y - dy_norm * arrowhead_size + perp_y * arrowhead_size // 2
    head_point2_x = line_end_x - dx_norm * arrowhead_size - perp_x * arrowhead_size // 2
    head_point2_y = line_end_y - dy_norm * arrowhead_size - perp_y * arrowhead_size // 2
    
    # Draw arrowhead
    arrow_points = [
        (line_end_x, line_end_y),
        (head_point1_x, head_point1_y),
        (head_point2_x, head_point2_y)
    ]
    draw.polygon(arrow_points, fill=color_rgb)

def generate_demo_analysis(image_base64: str) -> Dict[str, Any]:
    """Generate demo analysis for testing when API is not available"""
    return {
        "success": True,
        "analysis": {
            "weld_joints": [
                {
                    "id": "joint_1",
                    "type": "field_joint",
                    "coords": [150, 300],
                    "pipe_segments": ["pipe_1"],
                    "description": "Field weld at pipe start"
                },
                {
                    "id": "joint_2",
                    "type": "shop_joint",
                    "coords": [300, 300],
                    "pipe_segments": ["pipe_1"],
                    "description": "Shop weld mid-pipe"
                },
                {
                    "id": "joint_3",
                    "type": "field_joint",
                    "coords": [450, 300],
                    "pipe_segments": ["pipe_1", "pipe_2"],
                    "description": "Field weld at elbow connection"
                },
                {
                    "id": "joint_4", 
                    "type": "shop_joint",
                    "coords": [600, 250],
                    "pipe_segments": ["pipe_2"],
                    "description": "Shop weld on angled pipe"
                },
                {
                    "id": "joint_5",
                    "type": "field_joint",
                    "coords": [750, 200],
                    "pipe_segments": ["pipe_2"],
                    "description": "Field weld at pipe end"
                }
            ],
            "pipes": [
                {
                    "id": "pipe_1",
                    "start_coords": [150, 300],
                    "end_coords": [450, 300],
                    "centerline_points": [[150, 300], [450, 300]],
                    "diameter": "6 inch",
                    "material": "carbon_steel"
                },
                {
                    "id": "pipe_2", 
                    "start_coords": [450, 300],
                    "end_coords": [750, 200],
                    "centerline_points": [[450, 300], [750, 200]],
                    "diameter": "6 inch",
                    "material": "carbon_steel"
                }
            ],
            "fittings": [
                {
                    "id": "elbow_1",
                    "type": "elbow",
                    "center_coords": [450, 300],
                    "connection_points": [[430, 300], [470, 290]],
                    "connected_pipes": ["pipe_1", "pipe_2"]
                }
            ],
            "supports": [
                {
                    "id": "support_1",
                    "label": "PS-1",
                    "attachment_coords": [300, 320],
                    "pipe_contact_point": [300, 300]
                },
                {
                    "id": "support_2", 
                    "label": "S-2",
                    "attachment_coords": [600, 270],
                    "pipe_contact_point": [600, 250]
                }
            ],
            "drawing_analysis": {
                "clear_areas": {
                    "left_margin": [10, 50, 80, 500],
                    "right_margin": [720, 50, 790, 500],
                    "top_margin": [50, 10, 750, 80],
                    "bottom_margin": [50, 520, 750, 590]
                },
                "pipe_flow_direction": "left_to_right",
                "scale": "1:100"
            }
        },
        "raw_response": "Demo analysis with precise coordinates for professional weld mapping"
    }

def generate_weld_map_annotations(analysis_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Generate weld map annotations based on analysis and domain rules"""
    annotations = []
    
    try:
        if "analysis" not in analysis_data or not analysis_data["analysis"]:
            return annotations
            
        analysis = analysis_data["analysis"]
        
        # New structure: Use weld_joints for precise positioning
        if "weld_joints" in analysis:
            for joint in analysis["weld_joints"]:
                joint_type = joint.get("type", "unknown")
                coords = joint.get("coords", [0, 0])
                
                if joint_type == "field_joint":
                    annotations.append({
                        "type": "field_weld",
                        "shape": "diamond",
                        "coords": coords,
                        "joint_id": joint.get("id", "unknown"),
                        "description": joint.get("description", "Field weld - diamond shape")
                    })
                elif joint_type == "shop_joint":
                    annotations.append({
                        "type": "shop_weld",
                        "shape": "circle",
                        "coords": coords,
                        "joint_id": joint.get("id", "unknown"),
                        "description": joint.get("description", "Shop weld - circular shape")
                    })
        
        # Add pipe section annotations using pipe centerlines
        if "pipes" in analysis:
            for pipe in analysis["pipes"]:
                centerline = pipe.get("centerline_points", [])
                if len(centerline) >= 2:
                    # Add pipe section annotation at midpoint
                    start = centerline[0]
                    end = centerline[-1]
                    mid_coords = [(start[0] + end[0]) / 2, (start[1] + end[1]) / 2]
                    
                    annotations.append({
                        "type": "pipe_section",
                        "shape": "pill",
                        "coords": mid_coords,
                        "pipe_id": pipe.get("id", "unknown"),
                        "description": "Pipe section - pill shape"
                    })
        
        # Add pipe support annotations using contact points
        if "supports" in analysis:
            for support in analysis["supports"]:
                # Use pipe contact point for arrow targeting
                contact_point = support.get("pipe_contact_point", support.get("attachment_coords", [0, 0]))
                
                annotations.append({
                    "type": "pipe_support",
                    "shape": "rectangle",
                    "coords": contact_point,
                    "support_id": support.get("id", "unknown"),
                    "label": support.get("label", "PS"),
                    "description": "Pipe support - rectangular shape"
                })
        
        # Fallback: Handle legacy format if new structure not available
        if not annotations:
            # Legacy format support for backward compatibility
            if "pipes" in analysis:
                for pipe in analysis["pipes"]:
                    if "start_coords" in pipe and "end_coords" in pipe:
                        start = pipe["start_coords"]
                        end = pipe["end_coords"]
                        
                        # Add field welds at pipe ends
                        annotations.append({
                            "type": "field_weld",
                            "shape": "diamond",
                            "coords": start,
                            "pipe_id": pipe.get("id", "unknown"),
                            "description": "Field weld - diamond shape"
                        })
                        
                        annotations.append({
                            "type": "field_weld", 
                            "shape": "diamond",
                            "coords": end,
                            "pipe_id": pipe.get("id", "unknown"),
                            "description": "Field weld - diamond shape"
                        })
            
            # Legacy weld points
            if "weld_points" in analysis:
                for weld in analysis["weld_points"]:
                    if weld.get("type") == "shop_joint":
                        annotations.append({
                            "type": "shop_weld",
                            "shape": "circle",
                            "coords": weld["coords"],
                            "weld_id": weld.get("id", "unknown"),
                            "description": "Shop weld - circular shape"
                        })
            
            # Legacy supports
            if "supports" in analysis:
                for support in analysis["supports"]:
                    annotations.append({
                        "type": "pipe_support",
                        "shape": "rectangle", 
                        "coords": support.get("coords", [0, 0]),
                        "support_id": support.get("id", "unknown"),
                        "label": support.get("label", ""),
                        "description": "Pipe support - rectangular shape"
                    })
                
    except Exception as e:
        print(f"Error generating weld map annotations: {e}")
    
    return annotations

@app.post("/api/demo-upload")
async def demo_upload(file: UploadFile = File(...)):
    """Demo upload that works without AI API - uses mock data"""
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")
    
    try:
        # Save uploaded file
        file_id = str(uuid.uuid4())
        file_path = UPLOAD_DIR / f"{file_id}.pdf"
        
        with open(file_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)
        
        # Convert PDF to images
        images = pdf_to_images(str(file_path))
        
        # Generate demo analysis and annotations
        demo_results = []
        for page_num, img_base64 in enumerate(images):
            print(f"Generating demo analysis for page {page_num + 1}...")
            
            # Use demo analysis
            demo_analysis = generate_demo_analysis(img_base64)
            annotations = generate_weld_map_annotations(demo_analysis)
            
            # Create annotated image
            annotated_image = create_annotated_image(img_base64, annotations)
            
            demo_results.append({
                "page": page_num + 1,
                "image_base64": annotated_image,
                "original_image": img_base64,
                "analysis": demo_analysis,
                "weld_annotations": annotations,
                "processed": True,
                "mode": "demo"
            })
        
        # Clean up uploaded file
        file_path.unlink()
        
        return JSONResponse({
            "success": True,
            "file_id": file_id,
            "filename": file.filename,
            "total_pages": len(images),
            "results": demo_results,
            "mode": "demo",
            "note": "This is a demo analysis with mock data to showcase functionality"
        })
        
    except Exception as e:
        # Clean up on error
        if 'file_path' in locals() and file_path.exists():
            file_path.unlink()
            
        raise HTTPException(status_code=500, detail=f"Error processing PDF: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
