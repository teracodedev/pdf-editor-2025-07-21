import React, { useState, useEffect } from 'react';
import { FileText, RotateCw, Trash2, Download, Upload } from 'lucide-react';
import { open, save } from '@tauri-apps/plugin-dialog';

// Tauri v2公式の環境判定
function isTauri() {
  return Boolean(import.meta.env.TAURI_PLATFORM);
}

interface PdfPage {
  page_number: number;
  width: number;
  height: number;
  rotation: number;
  thumbnail: string;
  deleted?: boolean;
}

interface PdfInfo {
  path: string;
  page_count: number;
  pages: PdfPage[];
}

export default function PdfEditor() {
  const [pdfInfo, setPdfInfo] = useState<PdfInfo | null>(null);
  const [pages, setPages] = useState<PdfPage[]>([]);
  const [selectedPages, setSelectedPages] = useState<Set<number>>(new Set());
  const [draggedPage, setDraggedPage] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [tauriAvailable, setTauriAvailable] = useState(false);

  useEffect(() => {
    setTauriAvailable(isTauri());
    console.log('Tauri available:', isTauri());
  }, []);

  const handleOpenPdf = async () => {
    try {
      setLoading(true);
      setError(null);
      if (!isTauri()) {
        setError('Tauri API is not available. Please run this in a Tauri application.');
        return;
      }
      const path = await open({ filters: [{ name: 'PDF', extensions: ['pdf'] }] });
      if (path) {
        // ここでinvoke('load_pdf', ...)などを呼び出す
        // 例: const info = await invoke('load_pdf', { path });
        // setPdfInfo(info as PdfInfo);
        // setPages((info as PdfInfo).pages.map((p: PdfPage) => ({ ...p, deleted: false })));
        // setSelectedPages(new Set());
      }
    } catch (err) {
      console.error('Error loading PDF:', err);
      setError(`Error loading PDF: ${err}`);
    } finally {
      setLoading(false);
    }
  };

  const handleRotatePage = (pageNum: number, direction: number = 90) => {
    setPages(pages.map(p => 
      p.page_number === pageNum 
        ? { ...p, rotation: (p.rotation + direction) % 360 }
        : p
    ));
  };

  const handleDeletePage = (pageNum: number) => {
    if (selectedPages.has(pageNum)) {
      setPages(pages.map(p => 
        selectedPages.has(p.page_number) ? { ...p, deleted: true } : p
      ));
      setSelectedPages(new Set());
    } else {
      setPages(pages.map(p => 
        p.page_number === pageNum ? { ...p, deleted: true } : p
      ));
    }
  };

  const handleToggleSelect = (pageNum: number) => {
    const newSelected = new Set(selectedPages);
    if (newSelected.has(pageNum)) {
      newSelected.delete(pageNum);
    } else {
      newSelected.add(pageNum);
    }
    setSelectedPages(newSelected);
  };

  const handleDragStart = (e: React.DragEvent, pageNum: number) => {
    setDraggedPage(pageNum);
    e.dataTransfer.effectAllowed = 'move';
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
  };

  const handleDrop = (e: React.DragEvent, targetPageNum: number) => {
    e.preventDefault();
    if (draggedPage && draggedPage !== targetPageNum) {
      const draggedIndex = pages.findIndex(p => p.page_number === draggedPage);
      const targetIndex = pages.findIndex(p => p.page_number === targetPageNum);
      const newPages = [...pages];
      const [removed] = newPages.splice(draggedIndex, 1);
      newPages.splice(targetIndex, 0, removed);
      setPages(newPages);
    }
    setDraggedPage(null);
  };

  const handleSave = async () => {
    if (!pdfInfo) return;
    try {
      setLoading(true);
      setError(null);
      if (!isTauri()) {
        setError('Tauri API is not available. Please run this in a Tauri application.');
        return;
      }
      const outputPath = await save({ filters: [{ name: 'PDF', extensions: ['pdf'] }] });
      if (outputPath) {
        const pageOrder = pages.filter(p => !p.deleted).map(p => p.page_number);
        const rotations: Record<number, number> = {};
        const deletedPages: number[] = [];
        pages.forEach(p => {
          if (p.rotation !== 0) rotations[p.page_number] = p.rotation;
          if (p.deleted) deletedPages.push(p.page_number);
        });
        // ここでinvoke('save_pdf', ...)などを呼び出す
        // 例: await invoke('save_pdf', {
        //   path: pdfInfo.path,
        //   output_path: outputPath,
        //   page_order: pageOrder,
        //   rotations,
        //   deleted_pages: deletedPages
        // });
        alert('PDF saved successfully!');
      }
    } catch (err) {
      console.error('Error saving PDF:', err);
      setError(`Error saving PDF: ${err}`);
    } finally {
      setLoading(false);
    }
  };

  const activePages = pages.filter(p => !p.deleted);

  return (
    <div 
      className="min-h-screen h-full bg-gray-50"
      style={{ 
        minHeight: '100vh', 
        height: '100%',
        display: 'flex',
        flexDirection: 'column'
      }}
    >
      {/* Debug info */}
      <div className="bg-yellow-100 p-2 text-sm">
        Debug: Tauri available: {tauriAvailable ? 'Yes' : 'No'} | 
        Body height: {typeof window !== 'undefined' ? window.getComputedStyle(document.body).height : 'N/A'} | 
        Root height: {typeof window !== 'undefined' ? window.getComputedStyle(document.getElementById('root') || document.body).height : 'N/A'}
      </div>
      <header className="bg-white shadow-sm border-b">
        <div className="px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <FileText className="w-8 h-8 text-blue-600" />
              <h1 className="text-2xl font-bold text-gray-900">PDF Editor</h1>
            </div>
            <div className="flex items-center space-x-3">
              <button
                onClick={handleOpenPdf}
                className="flex items-center space-x-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
                disabled={!tauriAvailable}
              >
                <Upload className="w-4 h-4" />
                <span>Open PDF</span>
              </button>
              {pdfInfo && (
                <button
                  onClick={handleSave}
                  disabled={loading || !tauriAvailable}
                  className="flex items-center space-x-2 px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors disabled:opacity-50"
                >
                  <Download className="w-4 h-4" />
                  <span>Save PDF</span>
                </button>
              )}
            </div>
          </div>
        </div>
      </header>
      <main className="p-6 flex-1" style={{ flex: 1 }}>
        {error && (
          <div className="mb-4 p-4 bg-red-100 border border-red-400 text-red-700 rounded">
            {error}
          </div>
        )}
        {loading && (
          <div className="flex items-center justify-center py-20">
            <div className="text-gray-500">Loading...</div>
          </div>
        )}
        {!loading && !pdfInfo && (
          <div className="max-w-md mx-auto mt-20 text-center">
            <FileText className="w-16 h-16 mx-auto text-gray-300 mb-4" />
            <h2 className="text-xl font-semibold text-gray-700 mb-2">No PDF loaded</h2>
            <p className="text-gray-500 mb-6">Open a PDF file to start editing</p>
            <button
              onClick={handleOpenPdf}
              className="inline-flex items-center space-x-2 px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
              disabled={!tauriAvailable}
            >
              <Upload className="w-5 h-5" />
              <span>Open PDF</span>
            </button>
            {!tauriAvailable && (
              <p className="mt-4 text-sm text-red-600">
                Tauri API is not available. This app needs to run in a Tauri environment.
              </p>
            )}
          </div>
        )}
        {!loading && pdfInfo && (
          <div>
            <div className="mb-6 flex items-center justify-between">
              <div>
                <h2 className="text-lg font-semibold text-gray-800">
                  {pdfInfo.path.split('/').pop()}
                </h2>
                <p className="text-sm text-gray-500">
                  {activePages.length} pages ({pages.length - activePages.length} deleted)
                </p>
              </div>
              {selectedPages.size > 0 && (
                <div className="text-sm text-blue-600">
                  {selectedPages.size} pages selected
                </div>
              )}
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4">
              {activePages.map((page) => (
                <div
                  key={page.page_number}
                  draggable
                  onDragStart={(e) => handleDragStart(e, page.page_number)}
                  onDragOver={handleDragOver}
                  onDrop={(e) => handleDrop(e, page.page_number)}
                  onClick={() => handleToggleSelect(page.page_number)}
                  className={`
                    relative group cursor-pointer rounded-lg overflow-hidden
                    border-2 transition-all
                    ${selectedPages.has(page.page_number) 
                      ? 'border-blue-500 shadow-lg' 
                      : 'border-gray-200 hover:border-gray-300'
                    }
                    ${draggedPage === page.page_number ? 'opacity-50' : ''}
                  `}
                >
                  <div className="aspect-[1/1.414] bg-white p-2">
                    <img
                      src={page.thumbnail}
                      alt={`Page ${page.page_number}`}
                      className="w-full h-full object-contain"
                      style={{
                        transform: `rotate(${page.rotation}deg)`,
                        transition: 'transform 0.3s'
                      }}
                    />
                  </div>
                  <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/60 to-transparent p-2">
                    <div className="flex items-center justify-between">
                      <span className="text-white text-sm font-medium">
                        Page {page.page_number}
                      </span>
                      <div className="flex space-x-1 opacity-0 group-hover:opacity-100 transition-opacity">
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            handleRotatePage(page.page_number);
                          }}
                          className="p-1 bg-white/20 backdrop-blur rounded hover:bg-white/30 transition-colors"
                          title="Rotate"
                        >
                          <RotateCw className="w-4 h-4 text-white" />
                        </button>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            handleDeletePage(page.page_number);
                          }}
                          className="p-1 bg-white/20 backdrop-blur rounded hover:bg-red-500/50 transition-colors"
                          title="Delete"
                        >
                          <Trash2 className="w-4 h-4 text-white" />
                        </button>
                      </div>
                    </div>
                  </div>
                  {selectedPages.has(page.page_number) && (
                    <div className="absolute top-2 right-2 w-6 h-6 bg-blue-500 rounded-full flex items-center justify-center">
                      <svg className="w-4 h-4 text-white" fill="currentColor" viewBox="0 0 20 20">
                        <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                      </svg>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}
      </main>
    </div>
  );
}