import React, { useState, useRef } from 'react';
import './App.css';

const API_BASE_URL = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8001';

function App() {
  const [selectedFile, setSelectedFile] = useState(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [results, setResults] = useState(null);
  const [error, setError] = useState(null);
  const [aiTestResult, setAiTestResult] = useState(null);
  const fileInputRef = useRef(null);

  const testAIConnection = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/test-ai`);
      const data = await response.json();
      setAiTestResult(data);
    } catch (err) {
      setAiTestResult({ success: false, error: 'Failed to connect to API' });
    }
  };

  const handleFileSelect = (event) => {
    const file = event.target.files[0];
    if (file && file.type === 'application/pdf') {
      setSelectedFile(file);
      setError(null);
      setResults(null);
    } else {
      setError('Please select a valid PDF file');
      setSelectedFile(null);
    }
  };

  const handleUpload = async (demoMode = false) => {
    if (!selectedFile) {
      setError('Please select a PDF file first');
      return;
    }

    setIsProcessing(true);
    setError(null);
    setResults(null);

    try {
      const formData = new FormData();
      formData.append('file', selectedFile);

      const endpoint = demoMode ? '/api/demo-upload' : '/api/upload-pdf';
      const response = await fetch(`${API_BASE_URL}${endpoint}`, {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        throw new Error(`Upload failed: ${response.statusText}`);
      }

      const data = await response.json();
      setResults(data);
    } catch (err) {
      setError(`Error: ${err.message}`);
    } finally {
      setIsProcessing(false);
    }
  };

  const clearAll = () => {
    setSelectedFile(null);
    setResults(null);
    setError(null);
    setAiTestResult(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const getAnnotationColor = (type) => {
    switch (type) {
      case 'field_weld': return '#ff6b6b';
      case 'shop_weld': return '#4ecdc4';
      case 'pipe_section': return '#45b7d1';
      case 'pipe_support': return '#96ceb4';
      default: return '#feca57';
    }
  };

  const getShapeIcon = (shape) => {
    switch (shape) {
      case 'diamond': return '♦';
      case 'circle': return '●';
      case 'rectangle': return '■';
      case 'pill': return '⬭';
      default: return '▲';
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100">
      {/* Header */}
      <div className="bg-white shadow-sm border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center py-6">
            <div>
              <h1 className="text-3xl font-bold text-gray-900">
                AI Isometric Drawing Analyzer
              </h1>
              <p className="text-gray-600 mt-1">
                Automatically generate weld maps from engineering drawings
              </p>
            </div>
            <div className="flex space-x-4">
              <button
                onClick={testAIConnection}
                className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors"
              >
                Test AI Connection
              </button>
              <button
                onClick={clearAll}
                className="px-4 py-2 bg-gray-600 text-white rounded-lg hover:bg-gray-700 transition-colors"
              >
                Clear All
              </button>
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* AI Test Result */}
        {aiTestResult && (
          <div className={`mb-6 p-4 rounded-lg ${
            aiTestResult.success ? 'bg-green-50 border border-green-200' : 'bg-red-50 border border-red-200'
          }`}>
            <div className="flex items-center">
              <span className={`text-2xl mr-3 ${aiTestResult.success ? 'text-green-600' : 'text-red-600'}`}>
                {aiTestResult.success ? '✅' : '❌'}
              </span>
              <div>
                <p className={`font-medium ${aiTestResult.success ? 'text-green-800' : 'text-red-800'}`}>
                  {aiTestResult.success ? 'AI Connection Successful!' : 'AI Connection Failed'}
                </p>
                <p className={`text-sm ${aiTestResult.success ? 'text-green-600' : 'text-red-600'}`}>
                  {aiTestResult.message || aiTestResult.error}
                </p>
              </div>
            </div>
          </div>
        )}

        {/* Upload Section */}
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
              <p className="text-sm text-gray-500">
                Upload your isometric engineering drawing in PDF format
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
                      Processing...
                    </div>
                  ) : (
                    'Analyze Drawing'
                  )}
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Error Display */}
        {error && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-8">
            <div className="flex items-center">
              <span className="text-red-600 text-xl mr-3">⚠️</span>
              <p className="text-red-800 font-medium">{error}</p>
            </div>
          </div>
        )}

        {/* Results Section */}
        {results && (
          <div className="space-y-6">
            <div className="bg-white rounded-xl shadow-lg p-6">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-xl font-semibold text-gray-800">
                  Analysis Results
                </h2>
                <div className="flex items-center space-x-4">
                  <span className="text-sm text-gray-600">
                    File: {results.filename}
                  </span>
                  <span className="px-3 py-1 bg-green-100 text-green-800 rounded-full text-sm">
                    {results.total_pages} page{results.total_pages !== 1 ? 's' : ''}
                  </span>
                </div>
              </div>

              {/* Page Results */}
              {results.results && results.results.map((pageResult, index) => (
                <div key={index} className="border rounded-lg mb-6 overflow-hidden">
                  <div className="bg-gray-50 px-4 py-3 border-b">
                    <h3 className="font-medium text-gray-800">
                      Page {pageResult.page}
                      <span className={`ml-3 px-2 py-1 text-xs rounded ${
                        pageResult.processed 
                          ? 'bg-green-100 text-green-800' 
                          : 'bg-red-100 text-red-800'
                      }`}>
                        {pageResult.processed ? 'Processed' : 'Failed'}
                      </span>
                    </h3>
                  </div>

                  <div className="p-4">
                    {/* Drawing Image */}
                    {pageResult.image_base64 && (
                      <div className="mb-6">
                        <h4 className="font-medium text-gray-700 mb-3">Original Drawing:</h4>
                        <div className="relative border rounded-lg overflow-hidden bg-gray-50">
                          <img
                            src={`data:image/png;base64,${pageResult.image_base64}`}
                            alt={`Page ${pageResult.page}`}
                            className="w-full h-auto max-h-96 object-contain"
                          />
                        </div>
                      </div>
                    )}

                    {/* Weld Annotations */}
                    {pageResult.weld_annotations && pageResult.weld_annotations.length > 0 && (
                      <div className="mb-6">
                        <h4 className="font-medium text-gray-700 mb-3">
                          Generated Weld Map Annotations ({pageResult.weld_annotations.length}):
                        </h4>
                        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                          {pageResult.weld_annotations.map((annotation, idx) => (
                            <div
                              key={idx}
                              className="p-3 border rounded-lg"
                              style={{ borderColor: getAnnotationColor(annotation.type) }}
                            >
                              <div className="flex items-center mb-2">
                                <span 
                                  className="text-lg mr-2"
                                  style={{ color: getAnnotationColor(annotation.type) }}
                                >
                                  {getShapeIcon(annotation.shape)}
                                </span>
                                <span className="font-medium text-sm text-gray-800">
                                  {annotation.type.replace('_', ' ').toUpperCase()}
                                </span>
                              </div>
                              <p className="text-xs text-gray-600 mb-1">
                                Coordinates: [{Math.round(annotation.coords[0])}, {Math.round(annotation.coords[1])}]
                              </p>
                              <p className="text-xs text-gray-500">
                                {annotation.description}
                              </p>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* AI Analysis Details */}
                    {pageResult.analysis && pageResult.analysis.success && (
                      <div className="mb-4">
                        <h4 className="font-medium text-gray-700 mb-3">AI Analysis Summary:</h4>
                        <div className="bg-gray-50 rounded-lg p-4">
                          {pageResult.analysis.analysis && typeof pageResult.analysis.analysis === 'object' ? (
                            <div className="space-y-3">
                              {pageResult.analysis.analysis.pipes && (
                                <div>
                                  <span className="font-medium text-sm text-blue-600">
                                    Pipes Detected: {pageResult.analysis.analysis.pipes.length}
                                  </span>
                                </div>
                              )}
                              {pageResult.analysis.analysis.fittings && (
                                <div>
                                  <span className="font-medium text-sm text-green-600">
                                    Fittings Detected: {pageResult.analysis.analysis.fittings.length}
                                  </span>
                                </div>
                              )}
                              {pageResult.analysis.analysis.supports && (
                                <div>
                                  <span className="font-medium text-sm text-purple-600">
                                    Supports Detected: {pageResult.analysis.analysis.supports.length}
                                  </span>
                                </div>
                              )}
                              {pageResult.analysis.analysis.weld_points && (
                                <div>
                                  <span className="font-medium text-sm text-red-600">
                                    Weld Points Detected: {pageResult.analysis.analysis.weld_points.length}
                                  </span>
                                </div>
                              )}
                            </div>
                          ) : (
                            <p className="text-sm text-gray-600">
                              {pageResult.analysis.analysis?.raw_text || 'Analysis completed successfully'}
                            </p>
                          )}
                        </div>
                      </div>
                    )}

                    {/* Error Details */}
                    {pageResult.analysis && !pageResult.analysis.success && (
                      <div className="bg-red-50 border border-red-200 rounded-lg p-4">
                        <p className="text-red-800 font-medium mb-2">Analysis Error:</p>
                        <p className="text-red-600 text-sm">{pageResult.analysis.error}</p>
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Legend */}
        <div className="bg-white rounded-xl shadow-lg p-6">
          <h3 className="text-lg font-semibold text-gray-800 mb-4">Weld Map Symbol Legend</h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="flex items-center space-x-3">
              <span className="text-xl text-red-500">♦</span>
              <div>
                <p className="font-medium text-sm">Field Weld</p>
                <p className="text-xs text-gray-500">Diamond shape - every 6m</p>
              </div>
            </div>
            <div className="flex items-center space-x-3">
              <span className="text-xl text-teal-500">●</span>
              <div>
                <p className="font-medium text-sm">Shop Weld</p>
                <p className="text-xs text-gray-500">Circular shape</p>
              </div>
            </div>
            <div className="flex items-center space-x-3">
              <span className="text-xl text-blue-500">⬭</span>
              <div>
                <p className="font-medium text-sm">Pipe Section</p>
                <p className="text-xs text-gray-500">Pill shape between welds</p>
              </div>
            </div>
            <div className="flex items-center space-x-3">
              <span className="text-xl text-green-500">■</span>
              <div>
                <p className="font-medium text-sm">Pipe Support</p>
                <p className="text-xs text-gray-500">Rectangle for PS-, S- labels</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default App;
