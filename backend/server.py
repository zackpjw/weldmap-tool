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
async def export_pdf(export_data: dict):
    """COMPLETELY REWRITTEN: Export PDF with EXACT shape retention and NO gaps"""
    try:
        print("Starting PDF export with new system...")
        
        filename = export_data.get('filename', 'weld_mapping_export')
        symbols = export_data.get('symbols', [])
        images = export_data.get('images', [])
        canvas_info = export_data.get('canvasInfo', {})
        shape_specs = export_data.get('shapeSpecs', {})
        
        if not images:
            raise HTTPException(status_code=400, detail="No images to export")
        
        print(f"Processing {len(symbols)} symbols for export")
        
        # Create PDF buffer
        buffer = io.BytesIO()
        
        # Get the original image dimensions
        first_img_data = base64.b64decode(images[0])
        first_img = Image.open(io.BytesIO(first_img_data))
        original_width, original_height = first_img.size
        
        # PDF dimensions - maintain exact aspect ratio
        pdf_width = original_width * 0.75  # Convert to points
        pdf_height = original_height * 0.75
        
        pdf_canvas = canvas.Canvas(buffer, pagesize=(pdf_width, pdf_height))
        
        # Get canvas dimensions for precise coordinate transformation
        canvas_width = canvas_info.get('elementWidth', 800)
        canvas_height = canvas_info.get('elementHeight', 600)
        
        # Calculate exact scale factors
        scale_x = pdf_width / canvas_width
        scale_y = pdf_height / canvas_height
        
        print(f"Scale factors: x={scale_x}, y={scale_y}")
        print(f"PDF dimensions: {pdf_width} x {pdf_height}")
        print(f"Canvas dimensions: {canvas_width} x {canvas_height}")
        
        # Shape specifications from frontend
        base_size_pdf = (shape_specs.get('baseSize', 35) * scale_x * 0.6)  # Scale to PDF
        uniform_size_pdf = base_size_pdf * 0.8
        
        # Color mapping
        colors = {
            'field_weld': (0, 0.4, 1),      # Blue
            'shop_weld': (0, 0.4, 1),       # Blue  
            'pipe_section': (0, 0.4, 1),    # Blue
            'pipe_support': (1, 0, 0),      # Red
            'flange_joint': (0, 0.4, 1)     # Blue
        }
        
        # Process each page
        for page_num, image_base64 in enumerate(images):
            print(f"Processing page {page_num + 1}")
            
            # Process background image
            img_data = base64.b64decode(image_base64)
            img = Image.open(io.BytesIO(img_data))
            
            if img.mode != 'RGB':
                img = img.convert('RGB')
            
            # Draw background image
            temp_file = f"/tmp/export_page_{page_num}.png"
            img.save(temp_file, "PNG", quality=95)
            pdf_canvas.drawImage(temp_file, 0, 0, pdf_width, pdf_height)
            
            try:
                os.remove(temp_file)
            except:
                pass
            
            # Draw annotations for this page with PERFECT positioning
            page_annotations = [s for s in symbols if s.get('page', 0) == page_num]
            print(f"Drawing {len(page_annotations)} annotations on page {page_num + 1}")
            
            for annotation in page_annotations:
                symbol_type = annotation.get('type', 'field_weld')
                color = colors.get(symbol_type, (0, 0, 1))
                
                # Set drawing properties
                pdf_canvas.setStrokeColorRGB(*color)
                pdf_canvas.setFillColorRGB(*color)
                pdf_canvas.setLineWidth(2)
                
                # Draw line if exists - EXACT positioning
                if annotation.get('lineStart') and annotation.get('lineEnd'):
                    line_start = annotation['lineStart']
                    line_end = annotation['lineEnd']
                    
                    # Transform coordinates EXACTLY
                    start_x = line_start['x'] * scale_x
                    start_y = pdf_height - (line_start['y'] * scale_y)
                    end_x = line_end['x'] * scale_x  
                    end_y = pdf_height - (line_end['y'] * scale_y)
                    
                    pdf_canvas.line(start_x, start_y, end_x, end_y)
                
                # Draw symbol at EXACT position - NO GAPS
                symbol_pos = annotation.get('symbolPosition')
                if symbol_pos:
                    sym_x = symbol_pos['x'] * scale_x
                    sym_y = pdf_height - (symbol_pos['y'] * scale_y)
                    
                    # Draw shape with EXACT specifications from frontend
                    if symbol_type == 'field_weld':
                        # Diamond - exact same size as frontend
                        size = uniform_size_pdf * 0.8
                        points = [
                            (sym_x, sym_y + size),
                            (sym_x + size, sym_y), 
                            (sym_x, sym_y - size),
                            (sym_x - size, sym_y)
                        ]
                        path = pdf_canvas.beginPath()
                        path.moveTo(points[0][0], points[0][1])
                        for point in points[1:]:
                            path.lineTo(point[0], point[1])
                        path.close()
                        pdf_canvas.drawPath(path, stroke=1, fill=0)
                        
                    elif symbol_type == 'shop_weld':
                        # Circle - exact same size as frontend
                        radius = uniform_size_pdf * 0.35
                        pdf_canvas.circle(sym_x, sym_y, radius, stroke=1, fill=0)
                        
                    elif symbol_type == 'pipe_section':
                        # Blue rectangle - exact same proportions as frontend
                        width = uniform_size_pdf * 1.4
                        height = uniform_size_pdf * 0.7
                        pdf_canvas.roundRect(
                            sym_x - width/2, sym_y - height/2, 
                            width, height, 
                            4, stroke=1, fill=0
                        )
                        
                    elif symbol_type == 'pipe_support':
                        # Red rectangle - exact same proportions as frontend
                        width = uniform_size_pdf * 1.4
                        height = uniform_size_pdf * 0.7
                        pdf_canvas.rect(
                            sym_x - width/2, sym_y - height/2,
                            width, height,
                            stroke=1, fill=0
                        )
                        
                    elif symbol_type == 'flange_joint':
                        # Hexagon with line - exact same as frontend
                        hex_radius = uniform_size_pdf/2 * 0.7
                        hex_points = []
                        for i in range(6):
                            angle = i * math.pi / 3
                            px = sym_x + hex_radius * math.cos(angle)
                            py = sym_y + hex_radius * math.sin(angle)
                            hex_points.append((px, py))
                        
                        # Draw hexagon
                        path = pdf_canvas.beginPath()
                        path.moveTo(hex_points[0][0], hex_points[0][1])
                        for point in hex_points[1:]:
                            path.lineTo(point[0], point[1])
                        path.close()
                        pdf_canvas.drawPath(path, stroke=1, fill=0)
                        
                        # Draw horizontal line inside
                        line_length = uniform_size_pdf * 0.25
                        pdf_canvas.line(
                            sym_x - line_length, sym_y,
                            sym_x + line_length, sym_y
                        )
            
            # Add new page if not last
            if page_num < len(images) - 1:
                pdf_canvas.showPage()
        
        pdf_canvas.save()
        buffer.seek(0)
        
        print("PDF export completed successfully")
        
        return Response(
            content=buffer.getvalue(),
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={filename}.pdf"}
        )
        
    except Exception as e:
        print(f"Export error: {str(e)}")
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
