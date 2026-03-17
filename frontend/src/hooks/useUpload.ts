// === useUpload hook — manages file upload state ===

import { useState, useCallback } from 'react';
import { v4 as uuidv4 } from 'uuid';
import * as chatService from '../services/chatService';
import type { FileObject } from '../types/chat';

export function useUpload() {
  const [stagedFiles, setStagedFiles] = useState<FileObject[]>([]);
  const [isUploading, setIsUploading] = useState(false);

  /** Upload a file to the backend and stage it for the next query */
  const upload = useCallback(async (file: File) => {
    // Add a local placeholder immediately
    const localId = uuidv4();
    const placeholder: FileObject = {
      id: localId,
      name: file.name,
      size: file.size,
      type: file.type,
      uploadedAt: new Date(),
      file,
    };
    setStagedFiles(prev => [...prev, placeholder]);

    setIsUploading(true);
    try {
      const result = await chatService.uploadFile(file);
      // Update placeholder with the real remote ID
      setStagedFiles(prev =>
        prev.map(f =>
          f.id === localId ? { ...f, remoteId: result.fileId } : f
        )
      );
    } catch (err) {
      // Remove the failed placeholder
      setStagedFiles(prev => prev.filter(f => f.id !== localId));
      console.error('Upload failed:', err);
    } finally {
      setIsUploading(false);
    }
  }, []);

  /** Remove a staged file */
  const removeFile = useCallback((id: string) => {
    setStagedFiles(prev => prev.filter(f => f.id !== id));
  }, []);

  /** Clear all staged files (after sending a message) */
  const clearStaged = useCallback(() => {
    setStagedFiles([]);
  }, []);

  /** Get the remote file IDs for the current staged files */
  const getStagedIds = useCallback(() => {
    return stagedFiles
      .map(f => f.remoteId)
      .filter((id): id is string => !!id);
  }, [stagedFiles]);

  return {
    stagedFiles,
    isUploading,
    upload,
    removeFile,
    clearStaged,
    getStagedIds,
  };
}
