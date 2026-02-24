/**
 * Web File Upload Component
 *
 * Provides a streaming file upload interface with progress tracking
 * and drag-and-drop support for web mode.
 */

import React, { useCallback, useState, useRef } from 'react';
import { cn } from '@/lib/utils';
import {
	Upload,
	File,
	X,
	CheckCircle,
	AlertCircle,
	Loader2,
	FileText,
	FileImage,
	FileArchive,
	FileCode,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { useAuthStore } from '@/store/authStore';
import { getAppMode, isElectron } from '@/api/http';

export interface UploadedFile {
	file_id: string;
	filename: string;
	size: number;
	mime_type: string;
	checksum: string;
	created_at: string;
	url?: string;
}

export interface FileUploadProgress {
	filename: string;
	progress: number;
	status: 'pending' | 'uploading' | 'completed' | 'error';
	error?: string;
	result?: UploadedFile;
}

export interface WebFileUploadProps {
	/** Upload endpoint URL */
	uploadUrl?: string;
	/** Session ID for workspace isolation */
	sessionId?: string;
	/** Maximum file size in bytes */
	maxFileSize?: number;
	/** Allowed file extensions */
	allowedExtensions?: string[];
	/** Allow multiple files */
	multiple?: boolean;
	/** Enable drag and drop */
	dragDrop?: boolean;
	/** Container className */
	className?: string;
	/** Upload complete callback */
	onUploadComplete?: (files: UploadedFile[]) => void;
	/** Error callback */
	onError?: (error: string) => void;
}

// Get file icon based on mime type
const getFileIcon = (mimeType: string) => {
	if (mimeType.startsWith('image/')) return FileImage;
	if (mimeType.includes('zip') || mimeType.includes('tar') || mimeType.includes('archive'))
		return FileArchive;
	if (mimeType.includes('javascript') || mimeType.includes('typescript') || mimeType.includes('python'))
		return FileCode;
	if (mimeType.startsWith('text/')) return FileText;
	return File;
};

// Format file size
const formatFileSize = (bytes: number): string => {
	if (bytes === 0) return '0 Bytes';
	const k = 1024;
	const sizes = ['Bytes', 'KB', 'MB', 'GB'];
	const i = Math.floor(Math.log(bytes) / Math.log(k));
	return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
};

export const WebFileUpload: React.FC<WebFileUploadProps> = ({
	uploadUrl,
	sessionId,
	maxFileSize = 50 * 1024 * 1024, // 50MB default
	allowedExtensions,
	multiple = true,
	dragDrop = true,
	className,
	onUploadComplete,
	onError,
}) => {
	const [isDragging, setIsDragging] = useState(false);
	const [uploads, setUploads] = useState<FileUploadProgress[]>([]);
	const fileInputRef = useRef<HTMLInputElement>(null);
	const { getValidToken } = useAuthStore();

	// Get backend URL
	const getBackendUrl = () => {
		if (uploadUrl) return uploadUrl;
		if (isElectron()) {
			return '/files/upload'; // Will go through IPC
		}
		// In web mode, use relative URL to go through ingress proxy
		return `${import.meta.env.VITE_BACKEND_URL || '/api/backend'}/files/upload`;
	};

	// Validate file
	const validateFile = (file: File): string | null => {
		// Check size
		if (file.size > maxFileSize) {
			return `File ${file.name} exceeds maximum size of ${formatFileSize(maxFileSize)}`;
		}

		// Check extension
		if (allowedExtensions && allowedExtensions.length > 0) {
			const ext = '.' + file.name.split('.').pop()?.toLowerCase();
			if (!allowedExtensions.includes(ext)) {
				return `File type ${ext} not allowed`;
			}
		}

		return null;
	};

	// Upload single file with progress
	const uploadFile = async (file: File): Promise<UploadedFile | null> => {
		const error = validateFile(file);
		if (error) {
			setUploads((prev) =>
				prev.map((u) =>
					u.filename === file.name ? { ...u, status: 'error', error } : u
				)
			);
			onError?.(error);
			return null;
		}

		// Get valid token for authentication
		const token = await getValidToken();

		const formData = new FormData();
		formData.append('file', file);
		if (sessionId) {
			formData.append('session_id', sessionId);
		}

		try {
			// Use XMLHttpRequest for progress tracking
			return new Promise((resolve, reject) => {
				const xhr = new XMLHttpRequest();

				// Progress handler
				xhr.upload.addEventListener('progress', (e) => {
					if (e.lengthComputable) {
						const progress = Math.round((e.loaded / e.total) * 100);
						setUploads((prev) =>
							prev.map((u) =>
								u.filename === file.name ? { ...u, progress, status: 'uploading' } : u
							)
						);
					}
				});

				// Completion handler
				xhr.addEventListener('load', () => {
					if (xhr.status >= 200 && xhr.status < 300) {
						const result = JSON.parse(xhr.responseText) as UploadedFile;
						setUploads((prev) =>
							prev.map((u) =>
								u.filename === file.name
									? { ...u, progress: 100, status: 'completed', result }
									: u
							)
						);
						resolve(result);
					} else {
						const errorMsg = `Upload failed: ${xhr.statusText}`;
						setUploads((prev) =>
							prev.map((u) =>
								u.filename === file.name ? { ...u, status: 'error', error: errorMsg } : u
							)
						);
						reject(new Error(errorMsg));
					}
				});

				// Error handler
				xhr.addEventListener('error', () => {
					const errorMsg = 'Upload failed: Network error';
					setUploads((prev) =>
						prev.map((u) =>
							u.filename === file.name ? { ...u, status: 'error', error: errorMsg } : u
						)
					);
					reject(new Error(errorMsg));
				});

				xhr.open('POST', getBackendUrl());
				
				// Add auth header if token available
				if (token) {
					xhr.setRequestHeader('Authorization', `Bearer ${token}`);
				}

				xhr.send(formData);
			});
		} catch (error) {
			const errorMsg = error instanceof Error ? error.message : 'Upload failed';
			setUploads((prev) =>
				prev.map((u) =>
					u.filename === file.name ? { ...u, status: 'error', error: errorMsg } : u
				)
			);
			onError?.(errorMsg);
			return null;
		}
	};

	// Handle file selection
	const handleFiles = useCallback(
		async (files: FileList | File[]) => {
			const fileArray = Array.from(files);

			// Initialize upload state
			const newUploads: FileUploadProgress[] = fileArray.map((file) => ({
				filename: file.name,
				progress: 0,
				status: 'pending',
			}));
			setUploads((prev) => [...prev, ...newUploads]);

			// Upload files
			const results = await Promise.all(fileArray.map(uploadFile));

			// Filter successful uploads
			const successfulUploads = results.filter((r): r is UploadedFile => r !== null);

			if (successfulUploads.length > 0) {
				onUploadComplete?.(successfulUploads);
			}
		},
		[sessionId, maxFileSize, allowedExtensions]
	);

	// Drag and drop handlers
	const handleDragOver = useCallback((e: React.DragEvent) => {
		e.preventDefault();
		e.stopPropagation();
		if (dragDrop) {
			setIsDragging(true);
		}
	}, [dragDrop]);

	const handleDragLeave = useCallback((e: React.DragEvent) => {
		e.preventDefault();
		e.stopPropagation();
		setIsDragging(false);
	}, []);

	const handleDrop = useCallback(
		(e: React.DragEvent) => {
			e.preventDefault();
			e.stopPropagation();
			setIsDragging(false);

			if (dragDrop && e.dataTransfer.files.length > 0) {
				handleFiles(e.dataTransfer.files);
			}
		},
		[dragDrop, handleFiles]
	);

	// File input change handler
	const handleFileInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
		if (e.target.files && e.target.files.length > 0) {
			handleFiles(e.target.files);
		}
		// Reset input
		e.target.value = '';
	};

	// Remove upload from list
	const removeUpload = (filename: string) => {
		setUploads((prev) => prev.filter((u) => u.filename !== filename));
	};

	// Clear completed uploads
	const clearCompleted = () => {
		setUploads((prev) => prev.filter((u) => u.status !== 'completed'));
	};

	return (
		<div className={cn('space-y-4', className)}>
			{/* Drop zone */}
			<div
				className={cn(
					'relative border-2 border-dashed rounded-lg p-8 text-center transition-colors',
					isDragging
						? 'border-primary bg-primary/5'
						: 'border-muted-foreground/25 hover:border-primary/50',
					dragDrop && 'cursor-pointer'
				)}
				onDragOver={handleDragOver}
				onDragLeave={handleDragLeave}
				onDrop={handleDrop}
				onClick={() => fileInputRef.current?.click()}
			>
				<input
					ref={fileInputRef}
					type="file"
					multiple={multiple}
					accept={allowedExtensions?.join(',')}
					className="hidden"
					onChange={handleFileInputChange}
				/>

				<Upload className="mx-auto h-12 w-12 text-muted-foreground" />
				<p className="mt-2 text-sm text-muted-foreground">
					{dragDrop ? (
						<>
							Drag and drop files here, or{' '}
							<span className="text-primary font-medium">browse</span>
						</>
					) : (
						<span className="text-primary font-medium">Click to upload</span>
					)}
				</p>
				<p className="mt-1 text-xs text-muted-foreground">
					Max file size: {formatFileSize(maxFileSize)}
				</p>
			</div>

			{/* Upload list */}
			{uploads.length > 0 && (
				<div className="space-y-2">
					<div className="flex items-center justify-between">
						<span className="text-sm font-medium">Uploads</span>
						{uploads.some((u) => u.status === 'completed') && (
							<Button variant="ghost" size="sm" onClick={clearCompleted}>
								Clear completed
							</Button>
						)}
					</div>

					<div className="space-y-2 max-h-60 overflow-y-auto">
						{uploads.map((upload) => {
							const FileIcon = getFileIcon(upload.result?.mime_type || 'application/octet-stream');

							return (
								<div
									key={upload.filename}
									className="flex items-center gap-3 p-3 bg-muted/50 rounded-lg"
								>
									<FileIcon className="h-8 w-8 text-muted-foreground flex-shrink-0" />

									<div className="flex-1 min-w-0">
										<p className="text-sm font-medium truncate">{upload.filename}</p>

										{upload.status === 'uploading' && (
											<div className="mt-1">
												<Progress value={upload.progress} className="h-1" />
												<p className="text-xs text-muted-foreground mt-1">
													{upload.progress}%
												</p>
											</div>
										)}

										{upload.status === 'completed' && upload.result && (
											<p className="text-xs text-muted-foreground">
												{formatFileSize(upload.result.size)}
											</p>
										)}

										{upload.status === 'error' && (
											<p className="text-xs text-destructive">{upload.error}</p>
										)}
									</div>

									<div className="flex-shrink-0">
										{upload.status === 'pending' && (
											<Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
										)}
										{upload.status === 'uploading' && (
											<Loader2 className="h-5 w-5 animate-spin text-primary" />
										)}
										{upload.status === 'completed' && (
											<CheckCircle className="h-5 w-5 text-green-500" />
										)}
										{upload.status === 'error' && (
											<AlertCircle className="h-5 w-5 text-destructive" />
										)}
									</div>

									<Button
										variant="ghost"
										size="icon"
										className="h-8 w-8 flex-shrink-0"
										onClick={(e) => {
											e.stopPropagation();
											removeUpload(upload.filename);
										}}
									>
										<X className="h-4 w-4" />
									</Button>
								</div>
							);
						})}
					</div>
				</div>
			)}
		</div>
	);
};

export default WebFileUpload;
