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
    """Export annotated drawing as PDF with placed symbols"""
    try:
        filename = project_data.get('filename', 'weld_mapping')
        symbols = project_data.get('symbols', [])
        images = project_data.get('images', [])
        
        if not images:
            raise HTTPException(status_code=400, detail="No images to export")
        
        # Create PDF buffer
        buffer = io.BytesIO()
        pdf_canvas = canvas.Canvas(buffer, pagesize=letter)
        page_width, page_height = letter
        
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
            
            # Resize image to fit page
            img_ratio = img.width / img.height
            page_ratio = page_width / page_height
            
            if img_ratio > page_ratio:
                # Image is wider, fit to width
                new_width = page_width
                new_height = page_width / img_ratio
            else:
                # Image is taller, fit to height
                new_height = page_height
                new_width = page_height * img_ratio
            
            img = img.resize((int(new_width), int(new_height)), Image.Resampling.LANCZOS)
            
            # Save as temporary file for PDF
            temp_file = f"/tmp/temp_img_{page_num}.png"
            img.save(temp_file, "PNG")
            
            # Draw background image
            pdf_canvas.drawImage(temp_file, 0, 0, new_width, new_height)
            
            # Clean up temp file
            try:
                os.remove(temp_file)
            except:
                pass
            
            # Draw symbols for this page
            page_symbols = [s for s in symbols if s.get('page', 0) == page_num]
            
            for symbol in page_symbols:
                x = symbol.get('x', 0) * (page_width / 800)  # Scale from canvas to PDF
                y = (600 - symbol.get('y', 0)) * (page_height / 600)  # Flip Y and scale
                symbol_type = symbol.get('type', 'field_weld')
                
                # Set color
                color = symbol_colors.get(symbol_type, (0, 0, 1))
                pdf_canvas.setStrokeColorRGB(*color)
                pdf_canvas.setFillColorRGB(*color)
                
                # Draw symbol based on type
                if symbol_type == 'field_weld':
                    # Diamond
                    size = 10
                    pdf_canvas.polygon([(x, y+size), (x+size, y), (x, y-size), (x-size, y)], 
                                     stroke=1, fill=0)
                elif symbol_type == 'shop_weld':
                    # Circle
                    pdf_canvas.circle(x, y, 8, stroke=1, fill=0)
                elif symbol_type == 'pipe_section':
                    # Pill shape (rounded rectangle)
                    pdf_canvas.roundRect(x-12, y-5, 24, 10, 5, stroke=1, fill=0)
                elif symbol_type == 'pipe_support':
                    # Rectangle
                    pdf_canvas.rect(x-10, y-6, 20, 12, stroke=1, fill=0)
                elif symbol_type == 'flange_joint':
                    # Hexagon
                    size = 8
                    hex_points = []
                    for i in range(6):
                        angle = i * math.pi / 3
                        px = x + size * math.cos(angle)
                        py = y + size * math.sin(angle)
                        hex_points.append((px, py))
                    pdf_canvas.polygon(hex_points, stroke=1, fill=0)
                    # Line through center
                    pdf_canvas.line(x-size, y, x+size, y)
            
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
