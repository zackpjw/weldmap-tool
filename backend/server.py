from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
import os
from dotenv import load_dotenv
import fitz  # PyMuPDF
from PIL import Image, ImageDraw, ImageFont
import base64
import io
import uuid
from pathlib import Path
from typing import List, Dict, Any
import traceback
import json
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
import math

# Load environment variables
load_dotenv()

app = FastAPI(title="Interactive Weld Mapping Tool")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration
UPLOAD_DIR = Path("/tmp/uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

@app.get("/api/health")
async def health_check():
    return {"status": "healthy", "service": "Interactive Weld Mapping Tool"}

def pdf_to_images(pdf_path: str) -> List[str]:
    """Convert PDF pages to base64 encoded images"""
    try:
        doc = fitz.open(pdf_path)
        images = []
        
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            # High resolution for precise symbol placement
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

@app.post("/api/upload-pdf-only")
async def upload_pdf_only(file: UploadFile = File(...)):
    """Upload PDF and convert to images for interactive annotation"""
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
        
        # Clean up uploaded file
        file_path.unlink()
        
        return JSONResponse({
            "success": True,
            "file_id": file_id,
            "filename": file.filename,
            "total_pages": len(images),
            "images": images,
            "message": "PDF loaded successfully. Use the interactive tool to place weld symbols."
        })
        
    except Exception as e:
        # Clean up on error
        if 'file_path' in locals() and file_path.exists():
            file_path.unlink()
            
        raise HTTPException(status_code=500, detail=f"Error processing PDF: {str(e)}")

@app.post("/api/export-pdf")
async def export_pdf(project_data: dict):
    """Export annotated drawing as PDF with placed symbols and lines"""
    try:
        filename = project_data.get('filename', 'weld_mapping')
        symbols = project_data.get('symbols', [])
        images = project_data.get('images', [])
        
        if not images:
            raise HTTPException(status_code=400, detail="No images to export")
        
        # Create PDF buffer
        buffer = io.BytesIO()
        
        # First, get the original dimensions from the first image to maintain exact size
        first_img_data = base64.b64decode(images[0])
        first_img = Image.open(io.BytesIO(first_img_data))
        img_width, img_height = first_img.size
        
        # Use original image dimensions for PDF to maintain exact size and quality
        page_width = img_width * 0.75  # Convert pixels to points (96 DPI to 72 DPI)
        page_height = img_height * 0.75
        
        pdf_canvas = canvas.Canvas(buffer, pagesize=(page_width, page_height))
        
        # Symbol colors mapping
        symbol_colors = {
            'field_weld': (0, 0.4, 1),      # Blue
            'shop_weld': (0, 0.4, 1),       # Blue
            'pipe_section': (0, 0.4, 1),    # Blue
            'pipe_support': (1, 0, 0),      # Red
            'flange_joint': (0, 0.4, 1)     # Blue
        }
        
        for page_num, image_base64 in enumerate(images):
            # Decode and process background image
            img_data = base64.b64decode(image_base64)
            img = Image.open(io.BytesIO(img_data))
            
            # Convert to RGB if necessary
            if img.mode != 'RGB':
                img = img.convert('RGB')
            
            # Maintain original image size and quality - draw at full resolution
            # Save as temporary file for PDF
            temp_file = f"/tmp/temp_img_{page_num}.png"
            img.save(temp_file, "PNG", quality=95, optimize=False)
            
            # Draw background image at full size to maintain quality
            pdf_canvas.drawImage(temp_file, 0, 0, page_width, page_height)
            
            # Clean up temp file
            try:
                os.remove(temp_file)
            except:
                pass
            
            # Draw annotations for this page
            page_symbols = [s for s in symbols if s.get('page', 0) == page_num]
            
            for annotation in page_symbols:
                # Handle both old format (x, y) and new format (symbolPosition, lineStart, lineEnd)
                symbol_pos = annotation.get('symbolPosition') or {'x': annotation.get('x', 0), 'y': annotation.get('y', 0)}
                
                # Transform coordinates from frontend canvas to PDF
                symbol_x = symbol_pos['x'] * (page_width / 800)  # Scale from 800px canvas width
                symbol_y = (600 - symbol_pos['y']) * (page_height / 600)  # Flip Y and scale from 600px canvas height
                
                symbol_type = annotation.get('type', 'field_weld')
                
                # Set color
                color = symbol_colors.get(symbol_type, (0, 0, 1))
                pdf_canvas.setStrokeColorRGB(*color)
                pdf_canvas.setFillColorRGB(*color)
                pdf_canvas.setLineWidth(2)
                
                # Draw line if it exists
                if annotation.get('lineStart') and annotation.get('lineEnd'):
                    line_start_x = annotation['lineStart']['x'] * (page_width / 800)
                    line_start_y = (600 - annotation['lineStart']['y']) * (page_height / 600)
                    line_end_x = annotation['lineEnd']['x'] * (page_width / 800)
                    line_end_y = (600 - annotation['lineEnd']['y']) * (page_height / 600)
                    
                    pdf_canvas.line(line_start_x, line_start_y, line_end_x, line_end_y)
                
                # Draw symbol based on type with new specifications
                base_size = 26  # Scaled down from 35px frontend to PDF points
                
                if symbol_type == 'field_weld':
                    # Diamond
                    size = base_size * 0.8
                    points = [(symbol_x, symbol_y+size), (symbol_x+size, symbol_y), 
                             (symbol_x, symbol_y-size), (symbol_x-size, symbol_y)]
                    path = pdf_canvas.beginPath()
                    path.moveTo(points[0][0], points[0][1])
                    for point in points[1:]:
                        path.lineTo(point[0], point[1])
                    path.close()
                    pdf_canvas.drawPath(path, stroke=1, fill=0)
                    
                elif symbol_type == 'shop_weld':
                    # Circle
                    radius = base_size * 0.35
                    pdf_canvas.circle(symbol_x, symbol_y, radius, stroke=1, fill=0)
                    
                elif symbol_type == 'pipe_section':
                    # Blue rectangle with rounded corners - 40% wider, 50% of height
                    width = base_size * 1.4
                    height = base_size * 0.55
                    pdf_canvas.roundRect(symbol_x-width/2, symbol_y-height/2, width, height, 
                                       7, stroke=1, fill=0)  # 7pt radius for rounded corners
                    
                elif symbol_type == 'pipe_support':
                    # Red rectangle with sharp corners - 40% wider, 50% of height
                    width = base_size * 1.4
                    height = base_size * 0.55
                    pdf_canvas.rect(symbol_x-width/2, symbol_y-height/2, width, height, 
                                  stroke=1, fill=0)
                    
                elif symbol_type == 'flange_joint':
                    # Hexagon with horizontal line inside - 10% larger
                    hex_size = base_size * 0.77
                    hex_points = []
                    for i in range(6):
                        angle = i * math.pi / 3
                        px = symbol_x + hex_size/2 * math.cos(angle)
                        py = symbol_y + hex_size/2 * math.sin(angle)
                        hex_points.append((px, py))
                    
                    # Draw hexagon outline
                    path = pdf_canvas.beginPath()
                    path.moveTo(hex_points[0][0], hex_points[0][1])
                    for point in hex_points[1:]:
                        path.lineTo(point[0], point[1])
                    path.close()
                    pdf_canvas.drawPath(path, stroke=1, fill=0)
                    
                    # Draw horizontal line inside hexagon
                    line_length = hex_size/3
                    pdf_canvas.line(symbol_x - line_length, symbol_y, 
                                  symbol_x + line_length, symbol_y)
            
            # Add new page if not the last page
            if page_num < len(images) - 1:
                pdf_canvas.showPage()
        
        pdf_canvas.save()
        buffer.seek(0)
        
        # Return PDF as response
        return Response(
            content=buffer.getvalue(),
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={filename}_annotated.pdf"}
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error exporting PDF: {str(e)}")

@app.post("/api/export-annotations")
async def export_annotations(annotations_data: dict):
    """Export annotated drawing with placed symbols"""
    try:
        # This endpoint could be used to generate final annotated PDFs
        # For now, frontend handles export via canvas
        return JSONResponse({
            "success": True,
            "message": "Annotations data received",
            "symbols_count": len(annotations_data.get("symbols", []))
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error exporting annotations: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
