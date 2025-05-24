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
