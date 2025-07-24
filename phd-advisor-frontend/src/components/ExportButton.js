import React, { useState } from 'react';
import { Download, FileText, FileType, File, Check, X, Loader2 } from 'lucide-react';
import '../styles/ExportButton.css';

const ExportButton = ({ hasMessages = false, currentSessionId = null, authToken = null }) => {
  const [showDropdown, setShowDropdown] = useState(false);
  const [isExporting, setIsExporting] = useState(false);
  const [exportStatus, setExportStatus] = useState(null);
  const [selectedType, setSelectedType] = useState('chat');

  const exportTypes = [
    {
      id: 'chat',
      name: 'Full Chat',
      description: 'Complete conversation history',
      endpoint: 'export-chat'
    },
    {
      id: 'summary',
      name: 'Chat Summary',
      description: 'AI-generated conversation summary',
      endpoint: 'chat-summary'
    }
  ];

  const exportFormats = [
    {
      id: 'txt',
      name: 'Text File',
      description: 'Plain text format (.txt)',
      icon: FileText,
      extension: '.txt'
    },
    {
      id: 'docx',
      name: 'Word Document',
      description: 'Microsoft Word format (.docx)',
      icon: FileType,
      extension: '.docx'
    },
    {
      id: 'pdf',
      name: 'PDF Document',
      description: 'Portable Document Format (.pdf)',
      icon: File,
      extension: '.pdf'
    }
  ];

  const handleExportClick = () => {
    if (!hasMessages) return;
    setShowDropdown(!showDropdown);
    setExportStatus(null);
  };

  const handleFormatSelect = async (format) => {
    setIsExporting(true);
    setShowDropdown(false);
    setExportStatus(null);

    try {
      const selectedTypeData = exportTypes.find(t => t.id === selectedType);
      const endpoint = selectedTypeData.endpoint;
      
      // Build the URL with session ID if available
      let url = `http://localhost:8000/${endpoint}?format=${format}`;
      if (currentSessionId) {
        url += `&chat_session_id=${currentSessionId}`;
      }
      
      // Build headers - include auth token if available (needed for specific session export)
      const headers = {
        'Content-Type': 'application/json',
      };
      
      if (authToken && currentSessionId) {
        headers['Authorization'] = `Bearer ${authToken}`;
      }
      
      const response = await fetch(url, {
        method: 'GET',
        headers: headers,
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.error || `Export failed with status ${response.status}`);
      }

      // Get the filename from the Content-Disposition header
      const contentDisposition = response.headers.get('Content-Disposition');
      let filename = `${selectedType}_export.${format}`;
      
      if (contentDisposition) {
        const filenameMatch = contentDisposition.match(/filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/);
        if (filenameMatch && filenameMatch[1]) {
          filename = filenameMatch[1].replace(/['"]/g, '');
        }
      }

      // Create blob and download
      const blob = await response.blob();
      const url_blob = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url_blob;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url_blob);

      setExportStatus('success');
      setTimeout(() => setExportStatus(null), 3000);

    } catch (error) {
      console.error('Export error:', error);
      setExportStatus('error');
      setTimeout(() => setExportStatus(null), 5000);
    } finally {
      setIsExporting(false);
    }
  };

  const handleClickOutside = (e) => {
    if (!e.target.closest('.export-button-container')) {
      setShowDropdown(false);
    }
  };

  React.useEffect(() => {
    if (showDropdown) {
      document.addEventListener('click', handleClickOutside);
      return () => document.removeEventListener('click', handleClickOutside);
    }
  }, [showDropdown]);

  const getButtonIcon = () => {
    if (isExporting) return <Loader2 size={16} className="spinning" />;
    if (exportStatus === 'success') return <Check size={16} />;
    if (exportStatus === 'error') return <X size={16} />;
    return <Download size={16} />;
  };

  const getButtonClass = () => {
    let baseClass = 'export-button';
    if (!hasMessages) baseClass += ' disabled';
    if (showDropdown) baseClass += ' active';
    if (exportStatus === 'success') baseClass += ' success';
    if (exportStatus === 'error') baseClass += ' error';
    return baseClass;
  };

  const getButtonTitle = () => {
    if (!hasMessages) return 'No messages to export';
    if (isExporting) return 'Exporting chat...';
    if (exportStatus === 'success') return 'Export successful!';
    if (exportStatus === 'error') return 'Export failed - click to retry';
    
    // Show whether we're exporting current session or specific saved chat
    const sessionInfo = currentSessionId ? 'this saved chat' : 'current session';
    return `Export ${sessionInfo}`;
  };

  return (
    <div className="export-button-container">
      <button
        onClick={handleExportClick}
        className={getButtonClass()}
        disabled={!hasMessages || isExporting}
        title={getButtonTitle()}
      >
        {getButtonIcon()}
        <span className="export-text">Export</span>
      </button>

      {showDropdown && (
        <div className="export-dropdown">
          <div className="export-dropdown-header">
            <h4>Export Options</h4>
            <p>
              {currentSessionId 
                ? 'Export this saved chat conversation' 
                : 'Export current session'
              }
            </p>
          </div>
          
          {/* Export Type Selection */}
          <div className="export-type-section">
            <h5>What to export:</h5>
            <div className="export-type-buttons">
              {exportTypes.map((type) => (
                <button
                  key={type.id}
                  onClick={() => setSelectedType(type.id)}
                  className={`export-type-button ${selectedType === type.id ? 'active' : ''}`}
                  disabled={isExporting}
                >
                  <div className="type-info">
                    <div className="type-name">{type.name}</div>
                    <div className="type-description">{type.description}</div>
                  </div>
                </button>
              ))}
            </div>
          </div>
          
          {/* Format Selection */}
          <div className="export-format-section">
            <h5>Format:</h5>
            <div className="export-format-list">
              {exportFormats.map((format) => {
                const Icon = format.icon;
                return (
                  <button
                    key={format.id}
                    onClick={() => handleFormatSelect(format.id)}
                    className="export-format-button"
                    disabled={isExporting}
                  >
                    <div className="format-icon">
                      <Icon size={20} />
                    </div>
                    <div className="format-info">
                      <div className="format-name">{format.name}</div>
                      <div className="format-description">{format.description}</div>
                    </div>
                    <div className="format-extension">{format.extension}</div>
                  </button>
                );
              })}
            </div>
          </div>
          
          <div className="export-dropdown-footer">
            <span>
              {selectedType === 'chat' 
                ? 'Full conversation history will be included' 
                : 'AI will generate a concise summary of your conversation'
              }
            </span>
          </div>
        </div>
      )}

      {exportStatus && (
        <div className={`export-status ${exportStatus}`}>
          {exportStatus === 'success' && 'Chat exported successfully!'}
          {exportStatus === 'error' && 'Export failed. Please try again.'}
        </div>
      )}
    </div>
  );
};

export default ExportButton;