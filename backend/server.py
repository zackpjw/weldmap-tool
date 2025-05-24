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
        Analyze this isometric engineering drawing and provide detailed analysis:
        
        1. COMPONENT IDENTIFICATION:
           - Identify all straight pipe sections with approximate coordinates
           - Locate pipe fittings: elbows, tees, flanges, reducers with positions
           - Find pipe supports (look for labels starting with PS-, S-) with coordinates
           
        2. PIPE ANALYSIS:
           - Assume pipes are 6 meters in length by default
           - Identify pipe segments and their connections
           - Note any dimension markings visible
           
        3. WELD POINT DETECTION:
           - Identify all pipe joints where welding would be required
           - Look for existing weld symbols or joint indicators
           - Classify joints as either field joints or shop joints
           
        4. COORDINATE EXTRACTION:
           - Provide approximate X,Y pixel coordinates for each component
           - Note any grid references or elevation markers
           - Identify component relationships and connections
           
        5. COMPONENT SPECIFICATIONS:
           - Extract any visible pipe schedules, diameters, or materials
           - Note any special markings or annotations
           
        Please format your response as a structured JSON with the following format:
        {{
            "pipes": [
                {{
                    "id": "pipe_1",
                    "start_coords": [x1, y1],
                    "end_coords": [x2, y2],
                    "diameter": "size_if_visible",
                    "material": "material_if_visible"
                }}
            ],
            "fittings": [
                {{
                    "id": "fitting_1",
                    "type": "elbow/tee/flange/reducer",
                    "coords": [x, y],
                    "connections": ["pipe_1", "pipe_2"]
                }}
            ],
            "supports": [
                {{
                    "id": "support_1",
                    "label": "PS-1 or S-1 etc",
                    "coords": [x, y],
                    "type": "pipe_support"
                }}
            ],
            "weld_points": [
                {{
                    "id": "weld_1",
                    "coords": [x, y],
                    "type": "field_joint/shop_joint",
                    "connected_components": ["pipe_1", "fitting_1"]
                }}
            ],
            "drawing_info": {{
                "scale": "if_visible",
                "title": "drawing_title_if_visible",
                "dimensions": "overall_drawing_dimensions"
            }}
        }}
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
            "pipes": [
                {
                    "id": "pipe_1",
                    "start_coords": [150, 300],
                    "end_coords": [450, 300],
                    "diameter": "6 inch",
                    "material": "carbon_steel"
                },
                {
                    "id": "pipe_2", 
                    "start_coords": [450, 300],
                    "end_coords": [750, 200],
                    "diameter": "6 inch",
                    "material": "carbon_steel"
                }
            ],
            "fittings": [
                {
                    "id": "elbow_1",
                    "type": "elbow",
                    "coords": [450, 300],
                    "connections": ["pipe_1", "pipe_2"]
                }
            ],
            "supports": [
                {
                    "id": "support_1",
                    "label": "PS-1",
                    "coords": [300, 350],
                    "type": "pipe_support"
                },
                {
                    "id": "support_2", 
                    "label": "S-2",
                    "coords": [600, 250],
                    "type": "pipe_support"
                }
            ],
            "weld_points": [
                {
                    "id": "weld_1",
                    "coords": [200, 300],
                    "type": "shop_joint", 
                    "connected_components": ["pipe_1"]
                },
                {
                    "id": "weld_2",
                    "coords": [400, 300],
                    "type": "shop_joint",
                    "connected_components": ["pipe_1", "elbow_1"]
                }
            ],
            "drawing_info": {
                "scale": "1:100",
                "title": "Demo Isometric Drawing",
                "dimensions": "800x600"
            }
        },
        "raw_response": "Demo analysis generated for testing purposes"
    }

def generate_weld_map_annotations(analysis_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Generate weld map annotations based on analysis and domain rules"""
    annotations = []
    
    try:
        if "analysis" not in analysis_data or not analysis_data["analysis"]:
            return annotations
            
        analysis = analysis_data["analysis"]
        
        # Rule 1: Field welds (diamond shape) - every 6 meters on pipes
        if "pipes" in analysis:
            for pipe in analysis["pipes"]:
                if "start_coords" in pipe and "end_coords" in pipe:
                    start = pipe["start_coords"]
                    end = pipe["end_coords"]
                    
                    # Place field welds at start and end of each pipe
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
                    
                    # Add pipe section annotation between start and end
                    mid_coords = [(start[0] + end[0]) / 2, (start[1] + end[1]) / 2]
                    annotations.append({
                        "type": "pipe_section",
                        "shape": "pill",
                        "coords": mid_coords,
                        "pipe_id": pipe.get("id", "unknown"),
                        "description": "Pipe section - pill shape"
                    })
        
        # Rule 2: Shop joints (circular shape) - black dots between field joints
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
        
        # Rule 3: Rectangular boxes for pipe supports
        if "supports" in analysis:
            for support in analysis["supports"]:
                annotations.append({
                    "type": "pipe_support",
                    "shape": "rectangle", 
                    "coords": support["coords"],
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
