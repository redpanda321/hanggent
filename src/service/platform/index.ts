// ========= Copyright 2025-2026 @ Hanggent.AI All Rights Reserved. =========
// Platform Service Factory
// Returns the correct PlatformService implementation based on runtime environment
// =========================================================================

import { isElectron } from '@/utils/platform';
import { ElectronPlatformService } from './electron';
import type { PlatformService } from './types';
import { WebPlatformService } from './web';

let _instance: PlatformService | null = null;

/**
 * Get the singleton PlatformService instance.
 * Automatically selects Electron or Web implementation based on runtime detection.
 */
export function getPlatformService(): PlatformService {
  if (_instance) return _instance;

  if (isElectron()) {
    _instance = new ElectronPlatformService();
  } else {
    _instance = new WebPlatformService();
  }

  return _instance!;
}

/**
 * Convenience export — pre-initialized platform service singleton.
 * Safe to use at module level because isElectron() is synchronous and
 * available immediately (checks window.ipcRenderer existence).
 */
export const platformService = getPlatformService();

// Re-export types for convenience
export type { PlatformService } from './types';
export type {
  BackendService,
  FileService,
  McpService,
  EnvService,
  WindowService,
  WebViewService,
  SystemService,
  UpdateService,
  InstallService,
  LogService,
  IpcEventService,
} from './types';
