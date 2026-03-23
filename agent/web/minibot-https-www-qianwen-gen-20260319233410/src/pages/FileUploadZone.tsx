import React, { useState, useRef, useCallback } from 'react';

interface FileUploadZoneProps {
  onFileUpload: (fileId: string, filename: string) => void;
}

const FileUploadZone: React.FC<FileUploadZoneProps> = ({ onFileUpload }) => {
  const [isDragging, setIsDragging] = useState(false);
  const [preview, setPreview] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback(() => {
    setIsDragging(false);
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragging(false);

      const files = e.dataTransfer.files;
      if (files.length > 0) {
        const file = files[0];
        const reader = new FileReader();
        reader.onload = () => {
          setPreview(reader.result as string);
          // Simulate upload and get fileId
          const fileId = `file_${Date.now()}`;
          onFileUpload(fileId, file.name);
        };
        reader.readAsDataURL(file);
      }
    },
    [onFileUpload]
  );

  const handleFileSelect = useCallback(() => {
    const files = fileInputRef.current?.files;
    if (files && files.length > 0) {
      const file = files[0];
      const reader = new FileReader();
      reader.onload = () => {
        setPreview(reader.result as string);
        // Simulate upload and get fileId
        const fileId = `file_${Date.now()}`;
        onFileUpload(fileId, file.name);
      };
      reader.readAsDataURL(file);
    }
  }, [onFileUpload]);

  return (
    <div
      className={`border-2 border-dashed rounded-lg p-6 text-center cursor-pointer transition-colors ${
        isDragging ? 'border-blue-500 bg-blue-50' : 'border-gray-300 hover:border-gray-400'
      }`}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
      onClick={() => fileInputRef.current?.click()}
    >
      <input
        type="file"
        ref={fileInputRef}
        onChange={handleFileSelect}
        className="hidden"
        accept=".pdf,.docx,.pptx,.txt,.mp3,.mp4,.jpg,.png"
      />
      <div className="flex flex-col items-center justify-center">
        <svg
          width="48"
          height="48"
          viewBox="0 0 24 24"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
          className="mx-auto text-gray-400"
        >
          <path
            d="M12 16L16 12M12 16L8 12M12 16V4M20 16V20C20 20.5304 19.7893 21.0391 19.4142 21.4142C19.0391 21.7893 18.5304 22 18 22H6C5.46957 22 4.96086 21.7893 4.58579 21.4142C4.21071 21.0391 4 20.5304 4 20V16M20 16H4"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
        <p className="mt-2 text-sm font-medium text-gray-700">
          Drag & drop or click to upload
        </p>
        <p className="text-xs text-gray-500 mt-1">
          Supports PDF, DOCX, PPTX, TXT, MP3, MP4, JPG, PNG
        </p>
      </div>
      {preview && (
        <div className="mt-4 flex items-center justify-center gap-2">
          <div className="w-8 h-8 rounded bg-gray-200 flex items-center justify-center">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M14 12L16 14L10 20L8 18L14 12Z" fill="currentColor" />
              <path d="M12 16L14 18L8 24L6 22L12 16Z" fill="currentColor" />
              <path d="M10 20L12 22L6 28L4 26L10 20Z" fill="currentColor" />
            </svg>
          </div>
          <span className="text-xs text-gray-600 truncate max-w-xs">{preview.split(',')[0].includes('image') ? 'Image preview' : 'File uploaded'}</span>
        </div>
      )}
    </div>
  );
};

export default FileUploadZone;