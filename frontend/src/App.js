import React, { useState, useRef, useCallback } from 'react';
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
  const fileInputRef = useRef(null);
  const canvasRef = useRef(null);

  // Weld symbol types with updated colors
  const symbolTypes = {
    field_weld: { name: 'Field Weld', shape: '♦', color: '#0066FF', description: 'Diamond - Field welds' },
    shop_weld: { name: 'Shop Weld', shape: '●', color: '#0066FF', description: 'Circle - Shop welds' },
    pipe_section: { name: 'Pipe Section', shape: '⬭', color: '#0066FF', description: 'Pill - Pipe sections' },
    pipe_support: { name: 'Pipe Support', shape: '■', color: '#FF0000', description: 'Rectangle - Pipe supports' },
    flange_joint: { name: 'Flange Joint', shape: '⬢', color: '#0066FF', description: 'Hexagon - Flange joints' }
  };

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
    if (!canvasRef.current) return;

    const canvas = canvasRef.current;
    const rect = canvas.getBoundingClientRect();
    const x = event.clientX - rect.left;
    const y = event.clientY - rect.top;

    // Check if clicking on existing symbol (for removal in line drawing mode)
    if (isDrawingMode) {
      const clickedSymbol = currentPageSymbols.find(symbol => {
        const distance = Math.sqrt(Math.pow(x - symbol.x, 2) + Math.pow(y - symbol.y, 2));
        return distance <= 15; // 15px tolerance
      });
      
      if (clickedSymbol) {
        removeSymbol(clickedSymbol.id);
        return;
      }
    }

    // Add new symbol at click position (only if not in drawing mode)
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
  }, [selectedSymbolType, currentPage, isDrawingMode, currentPageSymbols]);

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
    const x = event.clientX - rect.left;
    const y = event.clientY - rect.top;

    setPlacedSymbols(prev => 
      prev.map(symbol => 
        symbol.id === draggedSymbol 
          ? { ...symbol, x, y }
          : symbol
      )
    );
  }, [draggedSymbol]);

  const removeSymbol = (symbolId) => {
    setPlacedSymbols(prev => prev.filter(symbol => symbol.id !== symbolId));
  };

  const clearAllSymbols = () => {
    setPlacedSymbols([]);
  };

  const exportDrawing = async () => {
    if (pdfImages.length === 0 || !canvasRef.current) return;

    try {
      const canvas = canvasRef.current;
      const dataURL = canvas.toDataURL('image/png');
      
      // Create download link
      const link = document.createElement('a');
      link.download = `weld_map_page_${currentPage + 1}.png`;
      link.href = dataURL;
      link.click();
    } catch (err) {
      setError('Error exporting drawing');
    }
  };

  const currentPageSymbols = placedSymbols.filter(symbol => symbol.page === currentPage);

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
            <div className="flex space-x-4">
              {pdfImages.length > 0 && (
                <>
                  <button
                    onClick={exportDrawing}
                    className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors"
                  >
                    Export Page
                  </button>
                  <button
                    onClick={clearAllSymbols}
                    className="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors"
                  >
                    Clear All
                  </button>
                </>
              )}
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Upload Section */}
        {pdfImages.length === 0 && (
          <div className="bg-white rounded-xl shadow-lg p-6 mb-8">
            <h2 className="text-xl font-semibold text-gray-800 mb-4">
              Upload Isometric Drawing (PDF)
            </h2>
            
            <div className="border-2 border-dashed border-gray-300 rounded-lg p-8 text-center hover:border-blue-400 transition-colors">
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

        {/* Interactive Workspace */}
        {pdfImages.length > 0 && (
          <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
            {/* Symbol Palette */}
            <div className="lg:col-span-1">
              <div className="bg-white rounded-xl shadow-lg p-6 sticky top-8">
                <h3 className="text-lg font-semibold text-gray-800 mb-4">Weld Symbol Palette</h3>
                
                <div className="space-y-3 mb-6">
                  {Object.entries(symbolTypes).map(([key, symbol]) => (
                    <button
                      key={key}
                      onClick={() => setSelectedSymbolType(key)}
                      className={`w-full p-3 rounded-lg border-2 transition-all ${
                        selectedSymbolType === key
                          ? 'border-blue-500 bg-blue-50'
                          : 'border-gray-200 hover:border-gray-300'
                      }`}
                    >
                      <div className="flex items-center space-x-3">
                        <span 
                          className="text-2xl"
                          style={{ color: symbol.color }}
                        >
                          {symbol.shape}
                        </span>
                        <div className="text-left">
                          <p className="font-medium text-sm text-gray-800">{symbol.name}</p>
                          <p className="text-xs text-gray-600">{symbol.description}</p>
                        </div>
                      </div>
                    </button>
                  ))}
                </div>

                <div className="border-t pt-4">
                  <h4 className="font-medium text-gray-700 mb-2">Instructions:</h4>
                  <ul className="text-sm text-gray-600 space-y-1">
                    <li>• Select symbol type</li>
                    <li>• Click on drawing to place</li>
                    <li>• Drag symbols to move</li>
                    <li>• Double-click to remove</li>
                  </ul>
                </div>

                {currentPageSymbols.length > 0 && (
                  <div className="border-t pt-4 mt-4">
                    <h4 className="font-medium text-gray-700 mb-2">
                      Current Page Symbols ({currentPageSymbols.length})
                    </h4>
                    <div className="space-y-2 max-h-40 overflow-y-auto">
                      {currentPageSymbols.map((symbol) => (
                        <div 
                          key={symbol.id}
                          className="flex items-center justify-between p-2 bg-gray-50 rounded"
                        >
                          <div className="flex items-center space-x-2">
                            <span style={{ color: symbolTypes[symbol.type].color }}>
                              {symbolTypes[symbol.type].shape}
                            </span>
                            <span className="text-xs text-gray-600">
                              ({Math.round(symbol.x)}, {Math.round(symbol.y)})
                            </span>
                          </div>
                          <button
                            onClick={() => removeSymbol(symbol.id)}
                            className="text-red-500 hover:text-red-700 text-xs"
                          >
                            ✕
                          </button>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* Drawing Canvas */}
            <div className="lg:col-span-3">
              <div className="bg-white rounded-xl shadow-lg p-6">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-lg font-semibold text-gray-800">
                    Drawing Canvas
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

                <div className="relative border-2 border-gray-200 rounded-lg overflow-hidden">
                  <canvas
                    ref={canvasRef}
                    width={800}
                    height={600}
                    className="w-full h-auto cursor-crosshair"
                    onClick={handleCanvasClick}
                    onDragOver={handleCanvasDragOver}
                    onDrop={handleCanvasDrop}
                    style={{
                      backgroundImage: pdfImages[currentPage] ? `url(data:image/png;base64,${pdfImages[currentPage]})` : 'none',
                      backgroundSize: 'contain',
                      backgroundRepeat: 'no-repeat',
                      backgroundPosition: 'center'
                    }}
                  />
                  
                  {/* Render placed symbols */}
                  {currentPageSymbols.map((symbol) => (
                    <div
                      key={symbol.id}
                      className="absolute cursor-move hover:scale-110 transition-transform"
                      style={{
                        left: symbol.x - 15,
                        top: symbol.y - 15,
                        color: symbolTypes[symbol.type].color,
                        fontSize: '24px',
                        fontWeight: 'bold',
                        textShadow: '1px 1px 2px rgba(0,0,0,0.5)',
                        zIndex: 10
                      }}
                      draggable
                      onDragStart={(e) => handleSymbolDragStart(e, symbol.id)}
                      onDragEnd={handleSymbolDragEnd}
                      onDoubleClick={() => removeSymbol(symbol.id)}
                      title={`${symbolTypes[symbol.type].name} - Double-click to remove`}
                    >
                      {symbolTypes[symbol.type].shape}
                    </div>
                  ))}
                </div>

                <div className="mt-4 text-sm text-gray-600">
                  <p>
                    <strong>Selected:</strong> {symbolTypes[selectedSymbolType].name} - 
                    Click anywhere on the drawing to place symbols
                  </p>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default App;
