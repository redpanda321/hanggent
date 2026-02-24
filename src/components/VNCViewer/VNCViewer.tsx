/**
 * VNC Viewer Component
 *
 * Provides a noVNC-based viewer for browser streaming from sandboxes.
 * Connects to VNC websocket endpoint for real-time browser display.
 */

import React, { useEffect, useRef, useState, useCallback } from 'react';
import { cn } from '@/lib/utils';
import { Loader2, Maximize2, Minimize2, RefreshCw, AlertCircle } from 'lucide-react';
import { Button } from '@/components/ui/button';

// noVNC library types (dynamically loaded)
declare global {
	interface Window {
		RFB: any;
	}
}

export interface VNCViewerProps {
	/** VNC websocket URL */
	vncUrl: string;
	/** VNC password (optional) */
	password?: string;
	/** Initial connection state */
	autoConnect?: boolean;
	/** Container className */
	className?: string;
	/** Viewer width */
	width?: string | number;
	/** Viewer height */
	height?: string | number;
	/** Resize mode: 'scale', 'remote', 'off' */
	scaleViewport?: boolean;
	/** Clip to window */
	clipViewport?: boolean;
	/** Show controls */
	showControls?: boolean;
	/** Connection callback */
	onConnect?: () => void;
	/** Disconnect callback */
	onDisconnect?: (e?: any) => void;
	/** Error callback */
	onError?: (error: string) => void;
}

export type ConnectionStatus = 'disconnected' | 'connecting' | 'connected' | 'error';

export const VNCViewer: React.FC<VNCViewerProps> = ({
	vncUrl,
	password,
	autoConnect = true,
	className,
	width = '100%',
	height = '600px',
	scaleViewport = true,
	clipViewport = false,
	showControls = true,
	onConnect,
	onDisconnect,
	onError,
}) => {
	const containerRef = useRef<HTMLDivElement>(null);
	const rfbRef = useRef<any>(null);
	const [status, setStatus] = useState<ConnectionStatus>('disconnected');
	const [errorMessage, setErrorMessage] = useState<string>('');
	const [isFullscreen, setIsFullscreen] = useState(false);
	const [noVNCLoaded, setNoVNCLoaded] = useState(false);

	// Load noVNC library dynamically
	useEffect(() => {
		const loadNoVNC = async () => {
			// Check if already loaded
			if (window.RFB) {
				setNoVNCLoaded(true);
				return;
			}

			try {
				// Load noVNC from CDN
				const script = document.createElement('script');
				script.src =
					'https://cdn.jsdelivr.net/npm/@novnc/novnc@1.4.0/core/rfb.min.js';
				script.async = true;

				script.onload = () => {
					setNoVNCLoaded(true);
					console.log('noVNC loaded successfully');
				};

				script.onerror = () => {
					setErrorMessage('Failed to load noVNC library');
					setStatus('error');
					onError?.('Failed to load noVNC library');
				};

				document.head.appendChild(script);
			} catch (error) {
				console.error('Error loading noVNC:', error);
				setErrorMessage('Error loading noVNC library');
				setStatus('error');
				onError?.('Error loading noVNC library');
			}
		};

		loadNoVNC();
	}, [onError]);

	// Connect to VNC
	const connect = useCallback(() => {
		if (!containerRef.current || !noVNCLoaded || !window.RFB) {
			console.warn('VNC not ready to connect');
			return;
		}

		// Disconnect existing connection
		if (rfbRef.current) {
			rfbRef.current.disconnect();
			rfbRef.current = null;
		}

		setStatus('connecting');
		setErrorMessage('');

		try {
			// Create RFB (Remote Frame Buffer) connection
			const rfb = new window.RFB(containerRef.current, vncUrl, {
				credentials: password ? { password } : undefined,
			});

			// Configure RFB
			rfb.scaleViewport = scaleViewport;
			rfb.clipViewport = clipViewport;
			rfb.resizeSession = true;

			// Event handlers
			rfb.addEventListener('connect', () => {
				console.log('VNC connected');
				setStatus('connected');
				onConnect?.();
			});

			rfb.addEventListener('disconnect', (e: any) => {
				console.log('VNC disconnected', e.detail);
				setStatus('disconnected');
				onDisconnect?.(e);
			});

			rfb.addEventListener('securityfailure', (e: any) => {
				console.error('VNC security failure:', e.detail);
				setErrorMessage(`Security failure: ${e.detail.reason}`);
				setStatus('error');
				onError?.(`Security failure: ${e.detail.reason}`);
			});

			rfbRef.current = rfb;
		} catch (error) {
			console.error('VNC connection error:', error);
			setErrorMessage(`Connection error: ${error}`);
			setStatus('error');
			onError?.(`Connection error: ${error}`);
		}
	}, [
		vncUrl,
		password,
		noVNCLoaded,
		scaleViewport,
		clipViewport,
		onConnect,
		onDisconnect,
		onError,
	]);

	// Disconnect from VNC
	const disconnect = useCallback(() => {
		if (rfbRef.current) {
			rfbRef.current.disconnect();
			rfbRef.current = null;
		}
		setStatus('disconnected');
	}, []);

	// Reconnect
	const reconnect = useCallback(() => {
		disconnect();
		setTimeout(connect, 100);
	}, [connect, disconnect]);

	// Toggle fullscreen
	const toggleFullscreen = useCallback(() => {
		if (!containerRef.current) return;

		if (!isFullscreen) {
			if (containerRef.current.requestFullscreen) {
				containerRef.current.requestFullscreen();
			}
		} else {
			if (document.exitFullscreen) {
				document.exitFullscreen();
			}
		}
	}, [isFullscreen]);

	// Fullscreen change handler
	useEffect(() => {
		const handleFullscreenChange = () => {
			setIsFullscreen(!!document.fullscreenElement);
		};

		document.addEventListener('fullscreenchange', handleFullscreenChange);
		return () => {
			document.removeEventListener('fullscreenchange', handleFullscreenChange);
		};
	}, []);

	// Auto-connect when ready
	useEffect(() => {
		if (autoConnect && noVNCLoaded && vncUrl) {
			connect();
		}

		return () => {
			disconnect();
		};
	}, [autoConnect, noVNCLoaded, vncUrl]);

	// Render status indicator
	const renderStatus = () => {
		switch (status) {
			case 'connecting':
				return (
					<div className="absolute inset-0 flex items-center justify-center bg-background/80 z-10">
						<div className="flex flex-col items-center gap-2">
							<Loader2 className="h-8 w-8 animate-spin text-primary" />
							<span className="text-sm text-muted-foreground">
								Connecting to VNC...
							</span>
						</div>
					</div>
				);

			case 'error':
				return (
					<div className="absolute inset-0 flex items-center justify-center bg-background/80 z-10">
						<div className="flex flex-col items-center gap-2 p-4 text-center">
							<AlertCircle className="h-8 w-8 text-destructive" />
							<span className="text-sm text-destructive">{errorMessage}</span>
							<Button variant="outline" size="sm" onClick={reconnect}>
								<RefreshCw className="h-4 w-4 mr-2" />
								Retry
							</Button>
						</div>
					</div>
				);

			case 'disconnected':
				return (
					<div className="absolute inset-0 flex items-center justify-center bg-background/80 z-10">
						<div className="flex flex-col items-center gap-2">
							<span className="text-sm text-muted-foreground">Disconnected</span>
							<Button variant="outline" size="sm" onClick={connect}>
								Connect
							</Button>
						</div>
					</div>
				);

			default:
				return null;
		}
	};

	return (
		<div
			className={cn(
				'relative rounded-md border bg-background overflow-hidden',
				className
			)}
			style={{ width, height }}
		>
			{/* Controls */}
			{showControls && status === 'connected' && (
				<div className="absolute top-2 right-2 z-20 flex gap-1">
					<Button
						variant="ghost"
						size="icon"
						className="h-8 w-8 bg-background/80 hover:bg-background"
						onClick={reconnect}
						title="Reconnect"
					>
						<RefreshCw className="h-4 w-4" />
					</Button>
					<Button
						variant="ghost"
						size="icon"
						className="h-8 w-8 bg-background/80 hover:bg-background"
						onClick={toggleFullscreen}
						title={isFullscreen ? 'Exit fullscreen' : 'Fullscreen'}
					>
						{isFullscreen ? (
							<Minimize2 className="h-4 w-4" />
						) : (
							<Maximize2 className="h-4 w-4" />
						)}
					</Button>
				</div>
			)}

			{/* Status overlay */}
			{renderStatus()}

			{/* VNC canvas container */}
			<div
				ref={containerRef}
				className="w-full h-full"
				style={{
					display: status === 'connected' ? 'block' : 'none',
				}}
			/>
		</div>
	);
};

export default VNCViewer;
