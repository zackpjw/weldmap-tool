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
  const fileInputRef = useRef(null);
  const canvasRef = useRef(null);

  // Weld symbol types with updated shapes and descriptions
  const symbolTypes = {
    field_weld: { name: 'Field Weld', shape: '⧫', color: '#0066FF', description: 'Rotated Square - Field welds' },
    shop_weld: { name: 'Shop Weld', shape: '●', color: '#0066FF', description: 'Circle - Shop welds' },
    pipe_section: { name: 'Pipe Section', shape: '▬', color: '#0066FF', description: 'Rounded Rectangle - Pipe sections' },
    pipe_support: { name: 'Pipe Support', shape: '▬', color: '#FF0000', description: 'Rectangle - Pipe supports' },
    flange_joint: { name: 'Flange Joint', shape: '⬢', color: '#0066FF', description: 'Rotated Hexagon - Flange joints' }
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
    // Only prevent default scrolling if mouse is over the canvas area
    if (event.target.closest('.pdf-editor-canvas')) {
      event.preventDefault();
      const delta = event.deltaY > 0 ? 0.9 : 1.1;
      setZoomLevel(prev => Math.min(Math.max(prev * delta, 0.2), 5));
    }
  }, []);

  const handleMouseDown = useCallback((event) => {
    if (event.button === 1 || (event.button === 0 && event.ctrlKey)) { // Middle mouse or Ctrl+left
      setIsPanning(true);
      setLastPanPoint({ x: event.clientX, y: event.clientY });
      event.preventDefault();
    }
  }, []);

  const handleMouseMove = useCallback((event) => {
    if (isPanning) {
      const deltaX = event.clientX - lastPanPoint.x;
      const deltaY = event.clientY - lastPanPoint.y;
      setPanOffset(prev => ({
        x: prev.x + deltaX,
        y: prev.y + deltaY
      }));
      setLastPanPoint({ x: event.clientX, y: event.clientY });
    }
  }, [isPanning, lastPanPoint]);

  const handleMouseUp = useCallback(() => {
    setIsPanning(false);
  }, []);

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

    document.addEventListener('keydown', handleKeyDown);
    
    return () => {
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [selectedSymbolId]);

  const currentPageSymbols = placedSymbols.filter(symbol => symbol.page === currentPage);

  const handleFileSelect = (event) => {
    const file = event.target.files[0];
    if (file && file.type === 'application/pdf') {
      setSelectedFile(file);
      setError(null);
      setPdfImages([]);
      setPlacedSymbols([]);
    } else {
      setError('Please select a valid PDF file');
      setSelectedFile(null);
    }
  };

  // Drag and drop handlers for file upload
  const handleDragEnter = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(true);
  };

  const handleDragLeave = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(false);
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    e.stopPropagation();
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(false);
    
    const files = e.dataTransfer.files;
    if (files.length > 0) {
      const file = files[0];
      if (file.type === 'application/pdf') {
        setSelectedFile(file);
        setError(null);
        setPdfImages([]);
        setPlacedSymbols([]);
      } else {
        setError('Please drop a valid PDF file');
      }
    }
  };

  const handleUpload = async () => {
    if (!selectedFile) {
      setError('Please select a PDF file first');
      return;
    }

    setIsProcessing(true);
    setError(null);

    try {
      const formData = new FormData();
      formData.append('file', selectedFile);

      const response = await fetch(`${API_BASE_URL}/api/upload-pdf-only`, {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        throw new Error(`Upload failed: ${response.statusText}`);
      }

      const data = await response.json();
      setPdfImages(data.images || []);
      setCurrentPage(0);
      setPlacedSymbols([]);
    } catch (err) {
      setError(`Error: ${err.message}`);
    } finally {
      setIsProcessing(false);
    }
  };

  const handleCanvasClick = useCallback((event) => {
    if (!canvasRef.current || isPanning) return;

    const canvas = canvasRef.current;
    const rect = canvas.getBoundingClientRect();
    
    // Account for zoom and pan
    const rawX = event.clientX - rect.left;
    const rawY = event.clientY - rect.top;
    
    // Convert to canvas coordinates considering zoom and pan
    const x = (rawX - panOffset.x) / zoomLevel;
    const y = (rawY - panOffset.y) / zoomLevel;

    // Check if clicking on existing symbol (for selection or removal) - more precise tolerance
    const clickedSymbol = currentPageSymbols.find(symbol => {
      const distance = Math.sqrt(Math.pow(x - symbol.x, 2) + Math.pow(y - symbol.y, 2));
      return distance <= 15; // Reduced tolerance for more precise selection
    });

    if (clickedSymbol) {
      if (isDrawingMode) {
        // Remove mode - delete symbol
        removeSymbol(clickedSymbol.id);
        setSelectedSymbolId(null);
        return;
      } else {
        // Select symbol (but allow placement of new symbols on top if not clicking exactly on a symbol)
        setSelectedSymbolId(clickedSymbol.id);
        return;
      }
    }

    // Clear selection if clicking on empty area
    setSelectedSymbolId(null);

    // Always allow symbol placement (even overlapping) - only prevent in drawing mode
    if (!isDrawingMode) {
      const newSymbol = {
        id: Date.now(),
        type: selectedSymbolType,
        x: x,
        y: y,
        page: currentPage
      };

      setPlacedSymbols(prev => [...prev, newSymbol]);
    }
  }, [selectedSymbolType, currentPage, isDrawingMode, currentPageSymbols, zoomLevel, panOffset, isPanning]);

  const handleSymbolDragStart = useCallback((event, symbolId) => {
    setIsDragging(true);
    setDraggedSymbol(symbolId);
    event.dataTransfer.effectAllowed = 'move';
  }, []);

  const handleSymbolDragEnd = useCallback(() => {
    setIsDragging(false);
    setDraggedSymbol(null);
  }, []);

  const handleCanvasDragOver = useCallback((event) => {
    event.preventDefault();
    event.dataTransfer.dropEffect = 'move';
  }, []);

  const handleCanvasDrop = useCallback((event) => {
    event.preventDefault();
    
    if (!canvasRef.current || !draggedSymbol) return;

    const canvas = canvasRef.current;
    const rect = canvas.getBoundingClientRect();
    
    // Account for zoom and pan
    const rawX = event.clientX - rect.left;
    const rawY = event.clientY - rect.top;
    
    // Convert to canvas coordinates considering zoom and pan
    const x = (rawX - panOffset.x) / zoomLevel;
    const y = (rawY - panOffset.y) / zoomLevel;

    setPlacedSymbols(prev => 
      prev.map(symbol => 
        symbol.id === draggedSymbol 
          ? { ...symbol, x, y }
          : symbol
      )
    );
  }, [draggedSymbol, zoomLevel, panOffset]);

  const removeSymbol = (symbolId) => {
    setPlacedSymbols(prev => prev.filter(symbol => symbol.id !== symbolId));
    setSelectedSymbolId(null);
  };

  const clearAllSymbols = () => {
    setPlacedSymbols([]);
    setSelectedSymbolId(null);
  };

  const startNewProject = () => {
    setPlacedSymbols([]);
    setSelectedSymbolId(null);
    setPdfImages([]);
    setSelectedFile(null);
    setCurrentPage(0);
    setZoomLevel(1);
    setPanOffset({ x: 0, y: 0 });
    setError(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const exportToPDF = async () => {
    if (pdfImages.length === 0) return;

    try {
      const projectData = {
        filename: selectedFile?.name || 'weld_mapping_project',
        pages: pdfImages.length,
        symbols: placedSymbols,
        images: pdfImages
      };

      const response = await fetch(`${API_BASE_URL}/api/export-pdf`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(projectData),
      });

      if (response.ok) {
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = `${projectData.filename}_annotated.pdf`;
        link.click();
        window.URL.revokeObjectURL(url);
      } else {
        throw new Error('Export failed');
      }
    } catch (err) {
      setError('Error exporting to PDF');
    }
  };

  const saveProject = () => {
    if (!projectName.trim()) {
      setError('Please enter a project name');
      return;
    }

    const project = {
      id: Date.now(),
      name: projectName.trim(),
      createdAt: new Date().toISOString(),
      filename: selectedFile?.name || 'unknown',
      symbols: placedSymbols,
      images: pdfImages,
      currentPage: currentPage
    };

    const saved = JSON.parse(localStorage.getItem('weldMappingProjects') || '[]');
    saved.push(project);
    localStorage.setItem('weldMappingProjects', JSON.stringify(saved));
    
    setSavedProjects(saved);
    setShowSaveDialog(false);
    setProjectName('');
  };

  const loadProject = (project) => {
    setPlacedSymbols(project.symbols || []);
    setPdfImages(project.images || []);
    setCurrentPage(project.currentPage || 0);
    setSelectedFile({ name: project.filename });
    setShowLoadDialog(false);
  };

  const deleteProject = (projectId) => {
    const saved = JSON.parse(localStorage.getItem('weldMappingProjects') || '[]');
    const updated = saved.filter(p => p.id !== projectId);
    localStorage.setItem('weldMappingProjects', JSON.stringify(updated));
    setSavedProjects(updated);
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100">
      {/* Header */}
      <div className="bg-white shadow-sm border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center py-6">
            <div>
              <h1 className="text-3xl font-bold text-gray-900">
                Interactive Weld Mapping Tool
              </h1>
              <p className="text-gray-600 mt-1">
                Drag and drop weld symbols exactly where you need them
              </p>
            </div>
            <div className="flex space-x-3">
              {pdfImages.length > 0 && (
                <>
                  {/* Zoom Controls */}
                  <div className="flex items-center space-x-2 bg-gray-100 rounded-lg px-3 py-2">
                    <button
                      onClick={zoomOut}
                      className="px-2 py-1 bg-white rounded hover:bg-gray-50 transition-colors"
                      title="Zoom Out"
                    >
                      🔍-
                    </button>
                    <span className="text-sm font-medium text-gray-700 min-w-[60px] text-center">
                      {Math.round(zoomLevel * 100)}%
                    </span>
                    <button
                      onClick={zoomIn}
                      className="px-2 py-1 bg-white rounded hover:bg-gray-50 transition-colors"
                      title="Zoom In"
                    >
                      🔍+
                    </button>
                    <button
                      onClick={resetZoom}
                      className="px-2 py-1 bg-blue-100 text-blue-700 rounded hover:bg-blue-200 transition-colors text-xs"
                      title="Reset Zoom"
                    >
                      Reset
                    </button>
                  </div>
                  
                  <button
                    onClick={() => setIsDrawingMode(!isDrawingMode)}
                    className={`px-4 py-2 rounded-lg transition-colors ${
                      isDrawingMode 
                        ? 'bg-red-600 text-white hover:bg-red-700' 
                        : 'bg-gray-600 text-white hover:bg-gray-700'
                    }`}
                  >
                    {isDrawingMode ? '✏️ Remove Mode' : '🎯 Place Mode'}
                  </button>
                  <button
                    onClick={() => setShowSaveDialog(true)}
                    className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
                  >
                    💾 Save Project
                  </button>
                  <button
                    onClick={exportToPDF}
                    className="px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 transition-colors"
                  >
                    📄 Export PDF
                  </button>
                  <button
                    onClick={clearAllSymbols}
                    className="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors"
                  >
                    🗑️ Clear All
                  </button>
                </>
              )}
              <button
                onClick={() => setShowLoadDialog(true)}
                className="px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors"
              >
                📂 Load Project
              </button>
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Upload Section */}
        {pdfImages.length === 0 && (
          <div className="bg-white rounded-xl shadow-lg p-6 mb-8">
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-xl font-semibold text-gray-800">
                Upload Isometric Drawing (PDF)
              </h2>
              {/* Show New Project button even when no PDF loaded for convenience */}
              <button
                onClick={startNewProject}
                className="px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors font-medium"
              >
                🆕 New Project
              </button>
            </div>
            
            <div 
              className={`border-2 border-dashed rounded-lg p-8 text-center transition-colors ${
                isDragOver 
                  ? 'border-blue-500 bg-blue-50' 
                  : 'border-gray-300 hover:border-blue-400'
              }`}
              onDragEnter={handleDragEnter}
              onDragLeave={handleDragLeave}
              onDragOver={handleDragOver}
              onDrop={handleDrop}
            >
              <input
                ref={fileInputRef}
                type="file"
                accept=".pdf"
                onChange={handleFileSelect}
                className="hidden"
                id="pdf-upload"
              />
              <label
                htmlFor="pdf-upload"
                className="cursor-pointer flex flex-col items-center"
              >
                <div className="text-6xl text-gray-400 mb-4">📄</div>
                <p className="text-lg text-gray-600 mb-2">
                  Click to select PDF file or drag and drop
                </p>
                <p className="text-sm text-gray-500 mb-3">
                  Upload your isometric engineering drawing for interactive weld mapping
                </p>
              </label>
            </div>

            {selectedFile && (
              <div className="mt-4 p-4 bg-blue-50 rounded-lg">
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
            )}
          </div>
        )}

        {/* Error Display */}
        {error && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-8">
            <div className="flex items-center">
              <span className="text-red-600 text-xl mr-3">⚠️</span>
              <p className="text-red-800 font-medium">{error}</p>
            </div>
          </div>
        )}

        {/* Professional PDF Editor Layout */}
        {pdfImages.length > 0 && (
          <div className="space-y-4">
            {/* Top Toolbar - Symbol Palette */}
            <div className="bg-white rounded-xl shadow-lg p-4">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-semibold text-gray-800">Weld Symbol Palette</h3>
                <button
                  onClick={startNewProject}
                  className="px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors font-medium"
                >
                  🆕 New Project
                </button>
              </div>
              
              {/* Horizontal Symbol Palette */}
              <div className="flex space-x-3">
                {Object.entries(symbolTypes).map(([key, symbol]) => (
                  <button
                    key={key}
                    onClick={() => setSelectedSymbolType(key)}
                    className={`p-3 rounded-lg border-2 transition-all ${
                      selectedSymbolType === key
                        ? 'border-blue-500 bg-blue-50'
                        : 'border-gray-200 hover:border-gray-300'
                    }`}
                  >
                    <div className="flex flex-col items-center space-y-1">
                      <span 
                        className="text-2xl"
                        style={{ color: symbol.color }}
                      >
                        {symbol.shape}
                      </span>
                      <p className="text-xs font-medium text-gray-800">{symbol.name}</p>
                    </div>
                  </button>
                ))}
              </div>

              {/* Quick Instructions */}
              <div className="mt-3 text-xs text-gray-600 text-center">
                Click to select symbol • Click on drawing to place • Symbols can overlap • Click symbol to select • Delete/Backspace to remove
              </div>
            </div>

            {/* Main Editor Area */}
            <div className="flex space-x-4">
              {/* PDF Editor Canvas - Left Side */}
              <div className="flex-1 bg-white rounded-xl shadow-lg">
                <div className="p-4 border-b border-gray-200">
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

                <div className="p-4">
                  <div className="relative border border-gray-200 rounded-lg overflow-hidden bg-gray-50 pdf-editor-canvas">
                    <canvas
                      ref={canvasRef}
                      width={800}
                      height={600}
                      className="w-full h-auto"
                      onClick={handleCanvasClick}
                      onDragOver={handleCanvasDragOver}
                      onDrop={handleCanvasDrop}
                      onWheel={handleWheel}
                      onMouseDown={handleMouseDown}
                      onMouseMove={handleMouseMove}
                      onMouseUp={handleMouseUp}
                      onMouseLeave={handleMouseUp}
                      style={{
                        backgroundImage: pdfImages[currentPage] ? `url(data:image/png;base64,${pdfImages[currentPage]})` : 'none',
                        backgroundSize: `${100 * zoomLevel}%`,
                        backgroundRepeat: 'no-repeat',
                        backgroundPosition: `${panOffset.x}px ${panOffset.y}px`,
                        cursor: isPanning ? 'grabbing' : isDrawingMode ? 'crosshair' : 'pointer',
                        width: '100%',
                        height: 'auto'
                      }}
                    />
                    
                    {/* Render placed symbols with zoom scaling */}
                    {currentPageSymbols.map((symbol) => {
                      // Create custom SVG symbols for proper shapes and sizes
                      const renderSymbol = (type, isSelected = false) => {
                        const baseSize = 25; // Base size
                        // Reduce size by 10% for all shapes except flange
                        const size = type === 'flange_joint' ? baseSize : baseSize * 0.9;
                        const strokeWidth = 3;
                        const color = symbolTypes[type].color;
                        
                        const getSymbolSVG = () => {
                          switch (type) {
                            case 'field_weld':
                              // Rotated square (45 degrees)
                              return (
                                <svg width={size * 2} height={size * 2} style={{ transform: 'rotate(45deg)' }}>
                                  <rect 
                                    x={size / 2} 
                                    y={size / 2} 
                                    width={size} 
                                    height={size} 
                                    fill="none" 
                                    stroke={color} 
                                    strokeWidth={strokeWidth}
                                  />
                                </svg>
                              );
                            case 'shop_weld':
                              // Circle
                              return (
                                <svg width={size * 2} height={size * 2}>
                                  <circle 
                                    cx={size} 
                                    cy={size} 
                                    r={size / 2} 
                                    fill="none" 
                                    stroke={color} 
                                    strokeWidth={strokeWidth}
                                  />
                                </svg>
                              );
                            case 'pipe_section':
                              // Rounded rectangle - stretched horizontally by 12%
                              const pipeWidth = size * 2.24; // 2 * 1.12 = 12% longer
                              return (
                                <svg width={pipeWidth} height={size}>
                                  <rect 
                                    x={strokeWidth / 2} 
                                    y={strokeWidth / 2} 
                                    width={pipeWidth - strokeWidth} 
                                    height={size - strokeWidth} 
                                    rx={8} 
                                    ry={8} 
                                    fill="none" 
                                    stroke={color} 
                                    strokeWidth={strokeWidth}
                                  />
                                </svg>
                              );
                            case 'pipe_support':
                              // Rectangle (not rounded) - stretched horizontally by 12%
                              const supportWidth = size * 2.24; // 2 * 1.12 = 12% longer
                              return (
                                <svg width={supportWidth} height={size}>
                                  <rect 
                                    x={strokeWidth / 2} 
                                    y={strokeWidth / 2} 
                                    width={supportWidth - strokeWidth} 
                                    height={size - strokeWidth} 
                                    fill="none" 
                                    stroke={color} 
                                    strokeWidth={strokeWidth}
                                  />
                                </svg>
                              );
                            case 'flange_joint':
                              // Hexagon rotated 90 degrees clockwise from previous (total 180 degrees) with horizontal center line, 10% larger
                              const flangeSize = size * 1.1; // 10% larger
                              return (
                                <svg width={flangeSize * 2} height={flangeSize * 2} style={{ transform: 'rotate(180deg)' }}>
                                  <polygon 
                                    points={`${flangeSize + flangeSize/2 * Math.cos(0)},${flangeSize + flangeSize/2 * Math.sin(0)} ${flangeSize + flangeSize/2 * Math.cos(Math.PI/3)},${flangeSize + flangeSize/2 * Math.sin(Math.PI/3)} ${flangeSize + flangeSize/2 * Math.cos(2*Math.PI/3)},${flangeSize + flangeSize/2 * Math.sin(2*Math.PI/3)} ${flangeSize + flangeSize/2 * Math.cos(Math.PI)},${flangeSize + flangeSize/2 * Math.sin(Math.PI)} ${flangeSize + flangeSize/2 * Math.cos(4*Math.PI/3)},${flangeSize + flangeSize/2 * Math.sin(4*Math.PI/3)} ${flangeSize + flangeSize/2 * Math.cos(5*Math.PI/3)},${flangeSize + flangeSize/2 * Math.sin(5*Math.PI/3)}`}
                                    fill="none" 
                                    stroke={color} 
                                    strokeWidth={strokeWidth}
                                  />
                                  <line 
                                    x1={flangeSize - flangeSize/2} 
                                    y1={flangeSize} 
                                    x2={flangeSize + flangeSize/2} 
                                    y2={flangeSize} 
                                    stroke={color} 
                                    strokeWidth={strokeWidth}
                                  />
                                </svg>
                              );
                            default:
                              return null;
                          }
                        };

                        return (
                          <div className="relative">
                            {getSymbolSVG()}
                            {isSelected && (
                              <div 
                                className="absolute inset-0 border border-black rounded"
                                style={{
                                  transform: 'translate(-3px, -3px)',
                                  width: 'calc(100% + 6px)',
                                  height: 'calc(100% + 6px)',
                                  borderWidth: '1px',
                                  borderStyle: 'solid',
                                  borderColor: 'black',
                                  backgroundColor: 'transparent',
                                  pointerEvents: 'none'
                                }}
                              />
                            )}
                          </div>
                        );
                      };

                      return (
                        <div
                          key={symbol.id}
                          className="absolute cursor-move hover:scale-110 transition-transform"
                          style={{
                            left: (symbol.x * zoomLevel + panOffset.x) - 25,
                            top: (symbol.y * zoomLevel + panOffset.y) - 25,
                            zIndex: 10,
                            pointerEvents: 'auto',
                            transform: `scale(${zoomLevel})`
                          }}
                          draggable
                          onDragStart={(e) => handleSymbolDragStart(e, symbol.id)}
                          onDragEnd={handleSymbolDragEnd}
                          onDoubleClick={() => removeSymbol(symbol.id)}
                          title={`${symbolTypes[symbol.type].name} - Double-click to remove`}
                        >
                          {renderSymbol(symbol.type, selectedSymbolId === symbol.id)}
                        </div>
                      );
                    })}
                  </div>

                  <div className="mt-4 text-sm text-gray-600">
                    <div className="flex justify-between items-center">
                      <p>
                        <strong>Mode:</strong> {isDrawingMode ? 'Remove Mode - Click symbols to remove them' : `Place Mode - Click to place ${symbolTypes[selectedSymbolType].name}`}
                      </p>
                      <p>
                        <strong>Zoom:</strong> {Math.round(zoomLevel * 100)}% | <strong>Symbols:</strong> {currentPageSymbols.length}
                      </p>
                    </div>
                    <div className="flex justify-between items-center mt-1">
                      <p className="text-xs text-gray-500">
                        💡 Tip: Use mouse wheel to zoom (inside PDF area), Ctrl+click to pan
                      </p>
                      {selectedSymbolId && (
                        <p className="text-xs text-blue-600 font-medium">
                          ✨ Symbol selected - Press Delete/Backspace to remove, Esc to deselect
                        </p>
                      )}
                    </div>
                  </div>
                </div>
              </div>

              {/* Right Panel - Current Symbols */}
              <div className="w-80 bg-white rounded-xl shadow-lg">
                <div className="p-4 border-b border-gray-200">
                  <h3 className="text-lg font-semibold text-gray-800">
                    Current Page Symbols ({currentPageSymbols.length})
                  </h3>
                </div>
                
                <div className="p-4">
                  {currentPageSymbols.length === 0 ? (
                    <div className="text-center text-gray-500 py-8">
                      <div className="text-4xl mb-2">📐</div>
                      <p>No symbols placed</p>
                      <p className="text-xs">Select a symbol type and click on the drawing to place it</p>
                    </div>
                  ) : (
                    <div className="space-y-2 max-h-96 overflow-y-auto">
                      {currentPageSymbols.map((symbol, index) => (
                        <div 
                          key={symbol.id}
                          className={`flex items-center justify-between p-3 rounded-lg border transition-colors ${
                            selectedSymbolId === symbol.id 
                              ? 'border-blue-500 bg-blue-50' 
                              : 'border-gray-200 hover:border-gray-300'
                          }`}
                        >
                          <div className="flex items-center space-x-3">
                            <span 
                              className="text-lg"
                              style={{ color: symbolTypes[symbol.type].color }}
                            >
                              {symbolTypes[symbol.type].shape}
                            </span>
                            <div>
                              <p className="font-medium text-sm text-gray-800">
                                {symbolTypes[symbol.type].name}
                              </p>
                              <p className="text-xs text-gray-600">
                                Position: ({Math.round(symbol.x)}, {Math.round(symbol.y)})
                              </p>
                            </div>
                          </div>
                          <div className="flex space-x-1">
                            <button
                              onClick={() => setSelectedSymbolId(symbol.id)}
                              className="px-2 py-1 text-xs bg-gray-100 hover:bg-gray-200 rounded"
                              title="Select symbol"
                            >
                              Select
                            </button>
                            <button
                              onClick={() => removeSymbol(symbol.id)}
                              className="px-2 py-1 text-xs bg-red-100 text-red-700 hover:bg-red-200 rounded"
                              title="Remove symbol"
                            >
                              ✕
                            </button>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}

                  {/* Symbol Management Actions */}
                  {currentPageSymbols.length > 0 && (
                    <div className="mt-4 pt-4 border-t border-gray-200">
                      <button
                        onClick={clearAllSymbols}
                        className="w-full px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors text-sm"
                      >
                        🗑️ Clear All Symbols
                      </button>
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Save Project Dialog */}
        {showSaveDialog && (
          <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
            <div className="bg-white rounded-lg p-6 w-96">
              <h3 className="text-lg font-semibold mb-4">Save Project</h3>
              <input
                type="text"
                placeholder="Enter project name"
                value={projectName}
                onChange={(e) => setProjectName(e.target.value)}
                className="w-full p-2 border border-gray-300 rounded mb-4"
              />
              <div className="flex space-x-3">
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
                <p className="text-gray-600">No saved projects found.</p>
              ) : (
                <div className="space-y-2">
                  {savedProjects.map((project) => (
                    <div key={project.id} className="border border-gray-200 rounded p-3">
                      <div className="flex items-center justify-between">
                        <div>
                          <p className="font-medium">{project.name}</p>
                          <p className="text-sm text-gray-600">
                            {project.filename} • {new Date(project.createdAt).toLocaleDateString()}
                          </p>
                          <p className="text-xs text-gray-500">
                            {project.symbols?.length || 0} symbols
                          </p>
                        </div>
                        <div className="flex space-x-2">
                          <button
                            onClick={() => loadProject(project)}
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
    </div>
  );
}

export default App;
