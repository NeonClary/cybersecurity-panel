import React, { useState, useRef } from 'react';
import { Upload, FileText, File, X, CheckCircle, AlertCircle } from 'lucide-react';
import { useTheme } from '../contexts/ThemeContext';
import '../styles/FileUpload.css'

const FileUpload = ({ onFileUploaded, isUploading, onUploadStart, currentChatSessionId = null, authToken = null  }) => {
  const [dragActive, setDragActive] = useState(false);
  const [uploadStatus, setUploadStatus] = useState(null); // 'success', 'error', null
  const [uploadMessage, setUploadMessage] = useState('');
  const [selectedFile, setSelectedFile] = useState(null);
  const fileInputRef = useRef(null);
  const { isDark } = useTheme();

  const supportedTypes = {
    'application/pdf': { ext: 'PDF', icon: FileText, color: '#EF4444' },
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document': { ext: 'DOCX', icon: File, color: '#3B82F6' },
    'text/plain': { ext: 'TXT', icon: FileText, color: '#10B981' }
  };

  const validateFile = (file) => {
    if (!supportedTypes[file.type]) {
      return { valid: false, error: 'Only PDF, DOCX, and TXT files are supported.' };
    }
    
    if (file.size > 10 * 1024 * 1024) { // 10MB limit
      return { valid: false, error: 'File size must be less than 10MB.' };
    }
    
    return { valid: true };
  };

  const uploadFile = async (file) => {
    const validation = validateFile(file);
    if (!validation.valid) {
      setUploadStatus('error');
      setUploadMessage(validation.error);
      return;
    }

    setSelectedFile(file);
    onUploadStart && onUploadStart();
    
    const formData = new FormData();
    formData.append('file', file);

    try {
      // FIXED: Build URL with chat_session_id parameter if available
      let uploadUrl = 'http://localhost:8000/upload-document';
      if (currentChatSessionId) {
        uploadUrl += `?chat_session_id=${currentChatSessionId}`;
        console.log(`Uploading to specific chat session: ${currentChatSessionId}`);
      } else {
        console.log('Uploading to new/current session');
      }

      // FIXED: Include auth token in headers if available
      const headers = {};
      if (authToken) {
        headers['Authorization'] = `Bearer ${authToken}`;
      }

      const response = await fetch(uploadUrl, {
        method: 'POST',
        headers: headers, // Add auth headers
        body: formData,
      });

      if (response.ok) {
        const data = await response.json();
        setUploadStatus('success');
        setUploadMessage(`${file.name} uploaded successfully and added to context.`);
        onFileUploaded && onFileUploaded(file, data);
        
        // FIXED: Log upload result for debugging
        console.log('Document upload result:', {
          filename: data.filename,
          session_id: data.session_id,
          chat_session_id: data.chat_session_id,
          chunks_created: data.chunks_created
        });
        
        // Auto-clear success message after 5 seconds
        setTimeout(() => {
          setUploadStatus(null);
          setSelectedFile(null);
          setUploadMessage('');
        }, 5000);
      } else {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Upload failed');
      }
    } catch (error) {
      setUploadStatus('error');
      setUploadMessage(`Upload failed: ${error.message}`);
      console.error('Upload error:', error);
    }
  };

  const handleDrag = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    
    if (isUploading) return;
    
    const files = Array.from(e.dataTransfer.files);
    if (files.length > 0) {
      uploadFile(files[0]);
    }
  };

  const handleFileSelect = (e) => {
    const files = Array.from(e.target.files);
    if (files.length > 0) {
      uploadFile(files[0]);
    }
  };

  const openFileDialog = () => {
    if (!isUploading) {
      fileInputRef.current?.click();
    }
  };

  const clearStatus = () => {
    setUploadStatus(null);
    setSelectedFile(null);
    setUploadMessage('');
  };

  const getFileIcon = (file) => {
    const fileInfo = supportedTypes[file.type];
    if (fileInfo) {
      const Icon = fileInfo.icon;
      return <Icon size={16} style={{ color: fileInfo.color }} />;
    }
    return <File size={16} />;
  };

  return (
    <div className="file-upload-container">
      {/* Upload Status Banner */}
      {uploadStatus && (
        <div className={`upload-status ${uploadStatus}`}>
          <div className="status-content">
            {uploadStatus === 'success' ? (
              <CheckCircle size={16} className="status-icon success" />
            ) : (
              <AlertCircle size={16} className="status-icon error" />
            )}
            <span className="status-message">{uploadMessage}</span>
            <button onClick={clearStatus} className="status-close">
              <X size={14} />
            </button>
          </div>
        </div>
      )}

      {/* Upload Area */}
      <div 
        className={`file-upload-area ${dragActive ? 'drag-active' : ''} ${isUploading ? 'uploading' : ''}`}
        onDragEnter={handleDrag}
        onDragLeave={handleDrag}
        onDragOver={handleDrag}
        onDrop={handleDrop}
        onClick={openFileDialog}
      >
        <input
          ref={fileInputRef}
          type="file"
          onChange={handleFileSelect}
          accept=".pdf,.docx,.txt"
          style={{ display: 'none' }}
          disabled={isUploading}
        />
        
        <div className="upload-content">
          {isUploading ? (
            <>
              <div className="upload-spinner">
                <div className="spinner"></div>
              </div>
              <p className="upload-text">Uploading {selectedFile?.name}...</p>
            </>
          ) : (
            <>
              <Upload size={24} className="upload-icon" />
              <p className="upload-text">
                <span className="upload-primary">Click to upload</span> or drag and drop
              </p>
              <p className="upload-secondary">PDF, DOCX, or TXT files only</p>
            </>
          )}
        </div>
      </div>
      
      {/* Supported File Types */}
      <div className="supported-types">
        {Object.entries(supportedTypes).map(([mimeType, info]) => {
          const Icon = info.icon;
          return (
            <div key={mimeType} className="file-type-chip">
              <Icon size={12} style={{ color: info.color }} />
              <span>{info.ext}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default FileUpload;