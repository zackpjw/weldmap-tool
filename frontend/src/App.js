import React, { useState, useRef, useCallback, useEffect } from 'react';
import './App.css';

const API_BASE_URL = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8001';

function App() {
  const [selectedFile, setSelectedFile] = useState(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [pdfImages, setPdfImages] = useState([]);
  const [currentPage, setCurrentPage] = useState(0);
  const [error, setError] = useState(null);
  const [placedSymbols, setPlacedSymbols] = useState([]);
  const [isDragging, setIsDragging] = useState(false);
  const [draggedSymbol, setDraggedSymbol] = useState(null);
  const [selectedSymbolType, setSelectedSymbolType] = useState('field_weld');
  const [isDrawingMode, setIsDrawingMode] = useState(false);
  const [savedProjects, setSavedProjects] = useState([]);
  const [projectName, setProjectName] = useState('');
  const [showSaveDialog, setShowSaveDialog] = useState(false);
  const [showLoadDialog, setShowLoadDialog] = useState(false);
  const [zoomLevel, setZoomLevel] = useState(1);
  const [panOffset, setPanOffset] = useState({ x: 0, y: 0 });
  const [isPanning, setIsPanning] = useState(false);
  const [lastPanPoint, setLastPanPoint] = useState({ x: 0, y: 0 });
  const [selectedSymbolId, setSelectedSymbolId] = useState(null);
  const [isDragOver, setIsDragOver] = useState(false);
  const [isMouseOverPDF, setIsMouseOverPDF] = useState(false);
  
  // New states for line drawing functionality
  const [isDrawingLine, setIsDrawingLine] = useState(false);
  const [lineStart, setLineStart] = useState(null);
  const [currentLineEnd, setCurrentLineEnd] = useState(null);
  const [previewLine, setPreviewLine] = useState(null);
  
  const fileInputRef = useRef(null);
  const canvasRef = useRef(null);

  // Weld symbol types with proper SVG shapes and descriptions
  const symbolTypes = {
    field_weld: { name: 'Field Weld', shape: '◊', color: '#0066FF', description: 'Diamond - Field welds' },
    shop_weld: { name: 'Shop Weld', shape: '○', color: '#0066FF', description: 'Circle - Shop welds' },
    pipe_section: { name: 'Pipe Section', shape: '▭', color: '#0066FF', description: 'Rectangle - Pipe sections' },
    pipe_support: { name: 'Pipe Support', shape: '▭', color: '#FF0000', description: 'Rectangle - Pipe supports' },
    flange_joint: { name: 'Flange Joint', shape: '⬡', color: '#0066FF', description: 'Hexagon - Flange joints' }
  };

  // Zoom functionality
  const zoomIn = () => {
    setZoomLevel(prev => Math.min(prev * 1.5, 5)); // Max zoom 5x
  };

  const zoomOut = () => {
    setZoomLevel(prev => Math.max(prev / 1.5, 0.2)); // Min zoom 0.2x
  };

  const resetZoom = () => {
    setZoomLevel(1);
    setPanOffset({ x: 0, y: 0 });
  };

  const handleWheel = useCallback((event) => {
    // Only prevent default scrolling if mouse is over the PDF canvas area
    if (isMouseOverPDF) {
      event.preventDefault();
      const delta = event.deltaY > 0 ? 0.9 : 1.1;
      setZoomLevel(prev => Math.min(Math.max(prev * delta, 0.2), 5));
    }
    // If mouse is not over PDF, allow normal page scrolling
  }, [isMouseOverPDF]);

  // Handle mouse enter/leave for PDF area to control scroll behavior
  const handlePDFMouseEnter = useCallback(() => {
    setIsMouseOverPDF(true);
  }, []);

  const handlePDFMouseLeave = useCallback(() => {
    setIsMouseOverPDF(false);
  }, []);

  // Get current page symbols
  const currentPageSymbols = placedSymbols.filter(symbol => symbol.page === currentPage);

  // Clear all symbols from current page
  const clearAllSymbols = () => {
    setPlacedSymbols(prev => prev.filter(symbol => symbol.page !== currentPage));
    setSelectedSymbolId(null);
  };

  // Remove specific symbol
  const removeSymbol = (symbolId) => {
    setPlacedSymbols(prev => prev.filter(symbol => symbol.id !== symbolId));
    setSelectedSymbolId(null);
  };

  // File handling functions
  const handleFileSelect = (event) => {
    const file = event.target.files[0];
    if (file && file.type === 'application/pdf') {
      setSelectedFile(file);
      setError(null);
    } else {
      setError('Please select a valid PDF file');
    }
  };

  const handleDragEnter = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(true);
  }, []);

  const handleDragLeave = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(false);
  }, []);

  const handleDragOver = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
  }, []);

  const handleDrop = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(false);
    
    const files = e.dataTransfer.files;
    if (files.length > 0) {
      const file = files[0];
      if (file.type === 'application/pdf') {
        setSelectedFile(file);
        setError(null);
      } else {
        setError('Please drop a valid PDF file');
      }
    }
  }, []);

  const handleUpload = async () => {
    if (!selectedFile) return;

    setIsProcessing(true);
    setError(null);

    const formData = new FormData();
    formData.append('file', selectedFile);

    try {
      const response = await fetch(`${API_BASE_URL}/api/upload-pdf-only`, {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        throw new Error(`Upload failed: ${response.statusText}`);
      }

      const data = await response.json();
      setPdfImages(data.images);
      setCurrentPage(0);
      setPlacedSymbols([]);
      setSelectedSymbolId(null);
      setZoomLevel(1);
      setPanOffset({ x: 0, y: 0 });

    } catch (error) {
      console.error('Upload error:', error);
      setError(`Failed to process PDF: ${error.message}`);
    } finally {
      setIsProcessing(false);
    }
  };

  // Canvas interaction functions
  const getCanvasCoordinates = (event) => {
    const canvas = canvasRef.current;
    if (!canvas) return { x: 0, y: 0 };

    const rect = canvas.getBoundingClientRect();
    
    // Get raw coordinates relative to canvas
    const rawX = event.clientX - rect.left;
    const rawY = event.clientY - rect.top;
    
    // Convert to canvas space accounting for zoom and pan
    const x = (rawX - panOffset.x) / zoomLevel;
    const y = (rawY - panOffset.y) / zoomLevel;

    return { x, y };
  };

  // Calculate connection point on shape based on line direction
  const getShapeConnectionPoint = (lineStart, lineEnd, shapeType) => {
    const dx = lineEnd.x - lineStart.x;
    const dy = lineEnd.y - lineStart.y;
    
    // Determine which side of the shape to connect to
    const angle = Math.atan2(dy, dx);
    const shapeSize = 35; // Base size for connection calculation
    
    let offsetX = 0;
    let offsetY = 0;
    
    // Calculate offset based on shape type and direction
    switch (shapeType) {
      case 'pipe_section': // Blue rectangle with rounded edges
      case 'pipe_support': // Red rectangle
        const width = shapeSize * 1.2; // 20% wider
        const height = shapeSize * 1.1; // 10% taller
        
        if (Math.abs(dx) > Math.abs(dy)) {
          // Horizontal line - connect to left or right side
          offsetX = dx > 0 ? -width/2 : width/2;
          offsetY = 0;
        } else {
          // Vertical line - connect to top or bottom side
          offsetX = 0;
          offsetY = dy > 0 ? -height/2 : height/2;
        }
        break;
        
      default: // Circular/diamond shapes
        const radius = shapeSize/2;
        offsetX = -Math.cos(angle) * radius;
        offsetY = -Math.sin(angle) * radius;
        break;
    }
    
    return {
      x: lineEnd.x + offsetX,
      y: lineEnd.y + offsetY
    };
  };

  const handleCanvasClick = (event) => {
    if (event.ctrlKey || event.metaKey || isPanning) {
      return; // Let panning handle this
    }

    const { x, y } = getCanvasCoordinates(event);

    // Check if clicking on an existing symbol
    const clickedSymbol = currentPageSymbols.find(symbol => {
      if (!symbol.symbolPosition) return false;
      const distance = Math.sqrt(
        Math.pow(symbol.symbolPosition.x - x, 2) + 
        Math.pow(symbol.symbolPosition.y - y, 2)
      );
      return distance < 30; // 30px click tolerance
    });

    if (clickedSymbol) {
      if (isDrawingMode) {
        removeSymbol(clickedSymbol.id);
      } else {
        setSelectedSymbolId(clickedSymbol.id);
      }
      return;
    }

    // If in drawing mode and not clicking on symbol, deselect
    if (isDrawingMode) {
      setSelectedSymbolId(null);
      return;
    }

    // Start line drawing
    if (!isDrawingLine) {
      setIsDrawingLine(true);
      setLineStart({ x, y });
      setCurrentLineEnd({ x, y });
      setPreviewLine({ start: { x, y }, end: { x, y } });
    }
  };

  // Handle mouse move for line drawing preview
  const handleCanvasMouseMove = (event) => {
    const { x, y } = getCanvasCoordinates(event);

    // Handle panning
    if (isPanning) {
      const deltaX = x - lastPanPoint.x;
      const deltaY = y - lastPanPoint.y;
      
      setPanOffset(prev => ({
        x: prev.x + deltaX,
        y: prev.y + deltaY
      }));
      
      setLastPanPoint({ x, y });
      event.preventDefault();
      return;
    }

    // Handle line drawing preview
    if (isDrawingLine && lineStart) {
      setCurrentLineEnd({ x, y });
      setPreviewLine({ start: lineStart, end: { x, y } });
    }
  };

  // Handle mouse up for completing line drawing
  const handleCanvasMouseUp = (event) => {
    if (isPanning) {
      setIsPanning(false);
      return;
    }

    if (isDrawingLine && lineStart) {
      const { x, y } = getCanvasCoordinates(event);
      
      // Only create line if it's long enough (minimum 10px)
      const lineLength = Math.sqrt(
        Math.pow(x - lineStart.x, 2) + 
        Math.pow(y - lineStart.y, 2)
      );

      if (lineLength > 10) {
        // Create new annotation with line and symbol
        const newAnnotation = {
          id: Date.now(),
          type: selectedSymbolType,
          page: currentPage,
          lineStart: lineStart,
          lineEnd: { x, y },
          symbolPosition: { x, y } // Symbol at end of line
        };

        setPlacedSymbols(prev => [...prev, newAnnotation]);
      }

      // Reset line drawing state
      setIsDrawingLine(false);
      setLineStart(null);
      setCurrentLineEnd(null);
      setPreviewLine(null);
      setSelectedSymbolId(null);
    }
  };

  // Panning functionality
  const handleMouseDown = (event) => {
    if (event.ctrlKey || event.metaKey) {
      setIsPanning(true);
      const { x, y } = getCanvasCoordinates(event);
      setLastPanPoint({ x, y });
      event.preventDefault();
    }
  };

  const handleMouseMove = (event) => {
    handleCanvasMouseMove(event);
  };

  const handleMouseUp = useCallback(() => {
    if (isPanning) {
      setIsPanning(false);
    }
  }, [isPanning]);

  // Canvas drag and drop for symbols
  const handleCanvasDragOver = (event) => {
    event.preventDefault();
  };

  const handleCanvasDrop = (event) => {
    event.preventDefault();
    if (draggedSymbol) {
      const { x, y } = getCanvasCoordinates(event);
      const newSymbol = {
        id: Date.now(),
        type: draggedSymbol,
        x,
        y,
        page: currentPage
      };
      setPlacedSymbols(prev => [...prev, newSymbol]);
      setDraggedSymbol(null);
    }
  };

  // Project management functions
  const saveProject = () => {
    if (!projectName.trim()) {
      alert('Please enter a project name');
      return;
    }

    const project = {
      id: Date.now(),
      name: projectName,
      symbols: placedSymbols,
      pdfImages: pdfImages,
      createdAt: new Date().toISOString()
    };

    const updated = [...savedProjects, project];
    setSavedProjects(updated);
    localStorage.setItem('weldMappingProjects', JSON.stringify(updated));
    
    setShowSaveDialog(false);
    setProjectName('');
    alert(`Project "${project.name}" saved successfully!`);
  };

  const loadProject = (projectId) => {
    const project = savedProjects.find(p => p.id.toString() === projectId);
    if (project) {
      setPlacedSymbols(project.symbols);
      setPdfImages(project.pdfImages);
      setCurrentPage(0);
      setSelectedSymbolId(null);
      setZoomLevel(1);
      setPanOffset({ x: 0, y: 0 });
      setShowLoadDialog(false);
    }
  };

  const deleteProject = (projectId) => {
    if (window.confirm('Are you sure you want to delete this project?')) {
      const updated = savedProjects.filter(p => p.id !== projectId);
      setSavedProjects(updated);
      localStorage.setItem('weldMappingProjects', JSON.stringify(updated));
    }
  };

  const startNewProject = () => {
    setPlacedSymbols([]);
    setPdfImages([]);
    setSelectedFile(null);
    setCurrentPage(0);
    setSelectedSymbolId(null);
    setZoomLevel(1);
    setPanOffset({ x: 0, y: 0 });
    setError(null);
  };

  // Export functionality
  const exportPDF = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/export-pdf`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          symbols: placedSymbols,
          images: pdfImages,
          filename: 'weld_mapping'
        }),
      });

      if (!response.ok) {
        throw new Error('Export failed');
      }

      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = 'annotated_drawing.pdf';
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);

    } catch (error) {
      console.error('Export error:', error);
      setError('Failed to export PDF. Please try again.');
    }
  };

  // Load saved projects on component mount and add keyboard listener
  useEffect(() => {
    const saved = JSON.parse(localStorage.getItem('weldMappingProjects') || '[]');
    setSavedProjects(saved);

    // Add keyboard event listener for delete
    const handleKeyDown = (event) => {
      if ((event.key === 'Delete' || event.key === 'Backspace') && selectedSymbolId) {
        event.preventDefault();
        removeSymbol(selectedSymbolId);
        setSelectedSymbolId(null);
      }
      if (event.key === 'Escape') {
        setSelectedSymbolId(null);
      }
    };

    // Add global wheel event listener for better scroll control
    const handleGlobalWheel = (event) => {
      // Let the handleWheel function handle PDF area zooming
      // This ensures smooth integration with page scrolling
      handleWheel(event);
    };

    document.addEventListener('keydown', handleKeyDown);
    window.addEventListener('wheel', handleGlobalWheel, { passive: false });
    
    return () => {
      document.removeEventListener('keydown', handleKeyDown);
      window.removeEventListener('wheel', handleGlobalWheel);
    };
  }, [selectedSymbolId, handleWheel]);

  return (
    <div className="min-h-screen bg-gray-100">
      {/* Header Section */}
      <div className="bg-white shadow-md border-b h-[50px] flex items-center px-6">
        <div className="flex items-center justify-between w-full">
          <div className="flex items-center space-x-4">
            <h1 className="text-xl font-bold text-gray-800">🔧 Interactive Weld Mapping Tool</h1>
            
            {/* File Upload */}
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf"
              onChange={handleFileSelect}
              className="hidden"
            />
            <button
              onClick={() => fileInputRef.current?.click()}
              className="px-3 py-1.5 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors text-sm font-medium"
            >
              📁 Upload PDF
            </button>
          </div>

          <div className="flex items-center space-x-3">
            {/* Zoom Controls */}
            {pdfImages.length > 0 && (
              <>
                <div className="flex items-center space-x-2 bg-gray-100 rounded-lg px-3 py-1">
                  <button
                    onClick={() => setZoomLevel(prev => Math.max(prev * 0.8, 0.2))}
                    className="px-2 py-0.5 bg-white rounded text-xs hover:bg-gray-50"
                  >
                    -
                  </button>
                  <span className="text-xs text-gray-700 min-w-[60px] text-center">
                    {Math.round(zoomLevel * 100)}%
                  </span>
                  <button
                    onClick={() => setZoomLevel(prev => Math.min(prev * 1.2, 5))}
                    className="px-2 py-0.5 bg-white rounded text-xs hover:bg-gray-50"
                  >
                    +
                  </button>
                </div>
                <button
                  onClick={resetZoom}
                  className="px-2 py-1 bg-gray-200 text-gray-700 rounded text-xs hover:bg-gray-300"
                >
                  Reset
                </button>
              </>
            )}

            {/* Drawing Mode Toggle */}
            {pdfImages.length > 0 && (
              <button
                onClick={() => setIsDrawingMode(!isDrawingMode)}
                className={`px-2 py-1 rounded text-xs font-medium transition-colors ${
                  isDrawingMode 
                    ? 'bg-red-600 text-white hover:bg-red-700' 
                    : 'bg-green-600 text-white hover:bg-green-700'
                }`}
              >
                {isDrawingMode ? '✂️ Remove' : '✏️ Place'}
              </button>
            )}

            {/* Save/Load Project */}
            {pdfImages.length > 0 && (
              <div className="flex space-x-2">
                <button
                  onClick={() => setShowSaveDialog(true)}
                  className="px-2 py-1 bg-purple-600 text-white rounded text-xs hover:bg-purple-700"
                >
                  💾 Save
                </button>
                
                {savedProjects.length > 0 && (
                  <select
                    onChange={(e) => e.target.value && loadProject(e.target.value)}
                    className="px-2 py-1 border border-gray-300 rounded text-xs"
                    value=""
                  >
                    <option value="">📂 Load Project</option>
                    {savedProjects.map((project) => (
                      <option key={project.id} value={project.id}>
                        {project.name}
                      </option>
                    ))}
                  </select>
                )}
              </div>
            )}

            {/* Export */}
            {pdfImages.length > 0 && (
              <button
                onClick={exportPDF}
                className="px-2 py-1 bg-orange-600 text-white rounded text-xs hover:bg-orange-700"
              >
                📤 Export PDF
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Main Content Container - Expanded workspace */}
      <div className="h-[calc(100vh-50px)] flex flex-col">
        {pdfImages.length === 0 ? (
          /* Upload Section */
          <div className="flex-1 flex items-center justify-center">
            <div className="bg-white rounded-xl shadow-lg p-8 max-w-md w-full mx-4">
              <div 
                className={`border-2 border-dashed rounded-lg p-8 text-center transition-colors ${
                  isDragOver 
                    ? 'border-blue-500 bg-blue-50' 
                    : 'border-gray-300 hover:border-gray-400'
                }`}
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                onDrop={handleDrop}
              >
                <div className="text-6xl mb-4">📄</div>
                <h3 className="text-xl font-semibold text-gray-800 mb-2">
                  Upload PDF Drawing
                </h3>
                <p className="text-gray-600 mb-4">
                  Drag and drop your engineering PDF here, or click to browse
                </p>
                <button
                  onClick={() => fileInputRef.current?.click()}
                  className="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors font-medium"
                >
                  Choose PDF File
                </button>
              </div>
            </div>
          </div>
        ) : (
          /* PDF Editor Interface */
          <div className="flex-1 flex flex-col p-6">
            {/* Symbol Palette - Above PDF Editor */}
            <div className="bg-white rounded-xl shadow-lg p-4 mb-4">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-semibold text-gray-800">Weld Symbol Palette</h3>
                <div className="text-sm text-gray-600">
                  Select a symbol type to place on the drawing
                </div>
              </div>
              
              <div className="flex flex-wrap gap-3">
                {Object.entries(symbolTypes).map(([type, config]) => (
                  <button
                    key={type}
                    onClick={() => setSelectedSymbolType(type)}
                    className={`flex items-center space-x-3 p-3 rounded-lg border-2 transition-all ${
                      selectedSymbolType === type
                        ? 'border-blue-500 bg-blue-50 shadow-md'
                        : 'border-gray-200 hover:border-gray-300 hover:bg-gray-50'
                    }`}
                  >
                    <span className="text-2xl" style={{ color: config.color }}>
                      {config.shape}
                    </span>
                    <div className="text-left">
                      <p className="font-medium text-sm text-gray-800">{config.name}</p>
                      <p className="text-xs text-gray-600">{config.description}</p>
                    </div>
                  </button>
                ))}
              </div>
              
              <div className="mt-4 px-4 py-2 bg-gray-50 rounded-lg text-xs text-gray-600">
                💡 Instructions: 
                Select symbol type • Click and drag to draw line • Symbol appears at line end • Click existing symbols to select • Delete/Backspace to remove
              </div>
            </div>

            {/* Main Editor Area - Full height workspace */}
            <div className="flex space-x-4 flex-1 min-h-0">
              {/* PDF Editor Canvas - Left Side */}
              <div className="flex-1 bg-white rounded-xl shadow-lg flex flex-col">
                <div className="p-4 border-b border-gray-200 flex-shrink-0">
                  <div className="flex items-center justify-between">
                    <h3 className="text-lg font-semibold text-gray-800">
                      PDF Editor
                    </h3>
                    {pdfImages.length > 1 && (
                      <div className="flex items-center space-x-2">
                        <button
                          onClick={() => setCurrentPage(Math.max(0, currentPage - 1))}
                          disabled={currentPage === 0}
                          className="px-3 py-1 bg-gray-200 text-gray-700 rounded disabled:opacity-50"
                        >
                          Previous
                        </button>
                        <span className="text-sm text-gray-600">
                          Page {currentPage + 1} of {pdfImages.length}
                        </span>
                        <button
                          onClick={() => setCurrentPage(Math.min(pdfImages.length - 1, currentPage + 1))}
                          disabled={currentPage === pdfImages.length - 1}
                          className="px-3 py-1 bg-gray-200 text-gray-700 rounded disabled:opacity-50"
                        >
                          Next
                        </button>
                      </div>
                    )}
                  </div>
                </div>

                <div className="flex-1 p-4 overflow-hidden">
                  <div 
                    className="relative border border-gray-200 rounded-lg overflow-hidden bg-gray-50 pdf-editor-canvas h-full"
                    onMouseEnter={handlePDFMouseEnter}
                    onMouseLeave={handlePDFMouseLeave}
                  >
                    <canvas
                      ref={canvasRef}
                      width={800}
                      height={600}
                      className="w-full h-full object-contain"
                      onClick={handleCanvasClick}
                      onDragOver={handleCanvasDragOver}
                      onDrop={handleCanvasDrop}
                      onMouseDown={handleMouseDown}
                      onMouseMove={handleMouseMove}
                      onMouseUp={handleCanvasMouseUp}
                      style={{
                        backgroundImage: pdfImages[currentPage] ? `url(data:image/png;base64,${pdfImages[currentPage]})` : 'none',
                        backgroundSize: `${100 * zoomLevel}%`,
                        backgroundRepeat: 'no-repeat',
                        backgroundPosition: `${panOffset.x}px ${panOffset.y}px`,
                        cursor: isPanning ? 'grabbing' : isDrawingMode ? 'crosshair' : isDrawingLine ? 'crosshair' : 'pointer'
                      }}
                    />
                    
                    {/* Render placed annotations with lines and symbols */}
                    {currentPageSymbols.map((annotation) => {
                      const symbolConfig = symbolTypes[annotation.type];
                      
                      // Handle both old format (x, y) and new format (symbolPosition)
                      const symbolPos = annotation.symbolPosition || { x: annotation.x, y: annotation.y };
                      const scaledSymbolX = symbolPos.x * zoomLevel + panOffset.x;
                      const scaledSymbolY = symbolPos.y * zoomLevel + panOffset.y;
                      const symbolSize = 29 * zoomLevel; // 20% larger than original 24px
                      
                      return (
                        <div key={annotation.id}>
                          {/* Render line if it exists */}
                          {annotation.lineStart && annotation.lineEnd && (
                            <svg
                              className="absolute top-0 left-0 w-full h-full pointer-events-none"
                              style={{ zIndex: 1 }}
                            >
                              <line
                                x1={annotation.lineStart.x * zoomLevel + panOffset.x}
                                y1={annotation.lineStart.y * zoomLevel + panOffset.y}
                                x2={annotation.lineEnd.x * zoomLevel + panOffset.x}
                                y2={annotation.lineEnd.y * zoomLevel + panOffset.y}
                                stroke={symbolConfig.color}
                                strokeWidth={2 * zoomLevel}
                                className={selectedSymbolId === annotation.id ? 'opacity-100' : 'opacity-80'}
                              />
                            </svg>
                          )}
                          
                          {/* Render symbol */}
                          <div
                            className={`absolute pointer-events-none select-none transition-all ${
                              selectedSymbolId === annotation.id ? 'ring-2 ring-blue-500 ring-offset-2 bg-blue-50 rounded' : ''
                            }`}
                            style={{
                              left: `${scaledSymbolX - 18}px`, // Adjusted for larger size
                              top: `${scaledSymbolY - 18}px`,
                              fontSize: `${symbolSize}px`,
                              color: 'transparent',
                              WebkitTextStroke: `2px ${symbolConfig.color}`, // Outline only
                              textStroke: `2px ${symbolConfig.color}`,
                              fontWeight: 'bold',
                              zIndex: selectedSymbolId === annotation.id ? 10 : 5,
                              filter: 'drop-shadow(1px 1px 2px rgba(0,0,0,0.3))'
                            }}
                          >
                            {symbolConfig.shape}
                          </div>
                        </div>
                      );
                    })}

                    {/* Render preview line while drawing */}
                    {previewLine && (
                      <svg
                        className="absolute top-0 left-0 w-full h-full pointer-events-none"
                        style={{ zIndex: 20 }}
                      >
                        <line
                          x1={previewLine.start.x * zoomLevel + panOffset.x}
                          y1={previewLine.start.y * zoomLevel + panOffset.y}
                          x2={previewLine.end.x * zoomLevel + panOffset.x}
                          y2={previewLine.end.y * zoomLevel + panOffset.y}
                          stroke={symbolTypes[selectedSymbolType].color}
                          strokeWidth={2 * zoomLevel}
                          strokeDasharray="5,5"
                          opacity="0.7"
                        />
                        
                        {/* Preview symbol at end of line */}
                        <text
                          x={previewLine.end.x * zoomLevel + panOffset.x}
                          y={previewLine.end.y * zoomLevel + panOffset.y}
                          fontSize={29 * zoomLevel}
                          fill="transparent"
                          stroke={symbolTypes[selectedSymbolType].color}
                          strokeWidth="2"
                          textAnchor="middle"
                          dominantBaseline="central"
                          opacity="0.7"
                        >
                          {symbolTypes[selectedSymbolType].shape}
                        </text>
                      </svg>
                    )}
                  </div>
                </div>

                <div className="p-4 border-t border-gray-200 flex-shrink-0">
                  <div className="text-sm text-gray-600">
                    <div className="flex justify-between items-center">
                      <p>
                        <strong>Mode:</strong> {isDrawingMode ? 'Remove Mode - Click symbols to remove them' : `Drawing Mode - Click and drag to draw line with ${symbolTypes[selectedSymbolType].name}`}
                      </p>
                      <p>
                        <strong>Zoom:</strong> {Math.round(zoomLevel * 100)}% | <strong>Annotations:</strong> {currentPageSymbols.length}
                      </p>
                    </div>
                    <div className="flex justify-between items-center mt-1">
                      <p className="text-xs text-gray-500">
                        💡 Tip: Mouse wheel to zoom (inside PDF area), Ctrl+click to pan, Click and drag to draw line
                      </p>
                      {selectedSymbolId && (
                        <p className="text-xs text-blue-600 font-medium">
                          ✨ Annotation selected - Press Delete/Backspace to remove, Esc to deselect
                        </p>
                      )}
                      {isDrawingLine && (
                        <p className="text-xs text-green-600 font-medium">
                          🎯 Drawing line - Drag to desired end point and release
                        </p>
                      )}
                    </div>
                  </div>
                </div>
              </div>

              {/* Right Panel - Current Symbols */}
              <div className="w-80 bg-white rounded-xl shadow-lg flex flex-col h-full">
                <div className="p-4 border-b border-gray-200 flex-shrink-0">
                  <h3 className="text-lg font-semibold text-gray-800">
                    Current Page Annotations ({currentPageSymbols.length})
                  </h3>
                </div>
                
                <div className="flex-1 p-4 overflow-hidden">
                  {currentPageSymbols.length === 0 ? (
                    <div className="text-center text-gray-500 py-8">
                      <div className="text-4xl mb-2">📐</div>
                      <p>No annotations placed</p>
                      <p className="text-xs">Select a symbol type and click-drag on the drawing to create line annotations</p>
                    </div>
                  ) : (
                    <div className="space-y-2 h-full overflow-y-auto">
                      {currentPageSymbols.map((annotation, index) => {
                        // Handle both old format (x, y) and new format (symbolPosition)
                        const symbolPos = annotation.symbolPosition || { x: annotation.x, y: annotation.y };
                        const hasLine = annotation.lineStart && annotation.lineEnd;
                        
                        return (
                          <div 
                            key={annotation.id}
                            className={`flex items-center justify-between p-3 rounded-lg border transition-colors ${
                              selectedSymbolId === annotation.id 
                                ? 'border-blue-500 bg-blue-50' 
                                : 'border-gray-200 hover:border-gray-300'
                            }`}
                          >
                            <div className="flex items-center space-x-3">
                              <span 
                                className="text-lg"
                                style={{ color: symbolTypes[annotation.type].color }}
                              >
                                {symbolTypes[annotation.type].shape}
                              </span>
                              <div>
                                <p className="font-medium text-sm text-gray-800">
                                  {symbolTypes[annotation.type].name}
                                </p>
                                <p className="text-xs text-gray-600">
                                  {hasLine ? 'Line + Symbol' : 'Symbol only'}
                                </p>
                                <p className="text-xs text-gray-500">
                                  Position: ({Math.round(symbolPos.x)}, {Math.round(symbolPos.y)})
                                </p>
                              </div>
                            </div>
                            <div className="flex space-x-1">
                              <button
                                onClick={() => setSelectedSymbolId(annotation.id)}
                                className="px-2 py-1 text-xs bg-gray-100 hover:bg-gray-200 rounded"
                                title="Select annotation"
                              >
                                Select
                              </button>
                              <button
                                onClick={() => removeSymbol(annotation.id)}
                                className="px-2 py-1 text-xs bg-red-100 text-red-700 hover:bg-red-200 rounded"
                                title="Remove annotation"
                              >
                                ✕
                              </button>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  )}

                  {/* Annotation Management Actions */}
                  {currentPageSymbols.length > 0 && (
                    <div className="mt-4 pt-4 border-t border-gray-200">
                      <button
                        onClick={clearAllSymbols}
                        className="w-full px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors text-sm"
                      >
                        🗑️ Clear All Annotations
                      </button>
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Selected File Display (only when no PDF loaded) */}
        {selectedFile && pdfImages.length === 0 && (
          <div className="mx-6 mb-6">
            <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-blue-800">
                    Selected: {selectedFile.name}
                  </p>
                  <p className="text-sm text-blue-600">
                    Size: {(selectedFile.size / 1024 / 1024).toFixed(2)} MB
                  </p>
                </div>
                <button
                  onClick={handleUpload}
                  disabled={isProcessing}
                  className={`px-6 py-2 rounded-lg font-medium transition-all ${
                    isProcessing
                      ? 'bg-gray-400 text-gray-700 cursor-not-allowed'
                      : 'bg-blue-600 text-white hover:bg-blue-700 hover:scale-105'
                  }`}
                >
                  {isProcessing ? (
                    <div className="flex items-center">
                      <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-white mr-2"></div>
                      Loading...
                    </div>
                  ) : (
                    'Load Drawing'
                  )}
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Error Display */}
        {error && (
          <div className="mx-6 mb-6">
            <div className="bg-red-50 border border-red-200 rounded-lg p-4">
              <div className="flex items-center">
                <span className="text-red-600 text-xl mr-3">⚠️</span>
                <p className="text-red-800 font-medium">{error}</p>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Save Project Dialog */}
      {showSaveDialog && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 w-96">
            <h3 className="text-lg font-semibold mb-4">Save Project</h3>
            <input
              type="text"
              value={projectName}
              onChange={(e) => setProjectName(e.target.value)}
              placeholder="Enter project name..."
              className="w-full p-2 border border-gray-300 rounded mb-4"
            />
            <div className="flex space-x-2">
              <button
                onClick={saveProject}
                className="flex-1 bg-blue-600 text-white py-2 rounded hover:bg-blue-700"
              >
                Save
              </button>
              <button
                onClick={() => setShowSaveDialog(false)}
                className="flex-1 bg-gray-300 text-gray-700 py-2 rounded hover:bg-gray-400"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Load Project Dialog */}
      {showLoadDialog && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 w-96 max-h-96 overflow-y-auto">
            <h3 className="text-lg font-semibold mb-4">Load Project</h3>
            {savedProjects.length === 0 ? (
              <p className="text-gray-500 text-center py-4">No saved projects found</p>
            ) : (
              <div className="space-y-2">
                {savedProjects.map((project) => (
                  <div key={project.id} className="border border-gray-200 rounded p-3">
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="font-medium">{project.name}</p>
                        <p className="text-sm text-gray-500">
                          {new Date(project.createdAt).toLocaleDateString()}
                        </p>
                        <p className="text-xs text-gray-400">
                          {project.symbols.length} symbols
                        </p>
                      </div>
                      <div className="flex space-x-2">
                        <button
                          onClick={() => loadProject(project.id.toString())}
                          className="px-3 py-1 bg-blue-600 text-white rounded text-sm hover:bg-blue-700"
                        >
                          Load
                        </button>
                        <button
                          onClick={() => deleteProject(project.id)}
                          className="px-3 py-1 bg-red-600 text-white rounded text-sm hover:bg-red-700"
                        >
                          Delete
                        </button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
            <div className="mt-4">
              <button
                onClick={() => setShowLoadDialog(false)}
                className="w-full bg-gray-300 text-gray-700 py-2 rounded hover:bg-gray-400"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default App;