import { Capacitor } from '@capacitor/core';

/**
 * Platform detection utilities for Hanggent
 * Supports Electron (desktop), Capacitor (mobile), and Web modes
 */

/**
 * Check if running in Electron environment
 */
export function isElectron(): boolean {
  return (
    typeof window !== 'undefined' &&
    typeof window.ipcRenderer !== 'undefined' &&
    window.ipcRenderer !== null
  );
}

/**
 * Check if running in Capacitor (native mobile) environment
 */
export function isCapacitor(): boolean {
  return Capacitor.isNativePlatform();
}

/**
 * Check if running on iOS (Capacitor)
 */
export function isIOS(): boolean {
  return Capacitor.getPlatform() === 'ios';
}

/**
 * Check if running on Android (Capacitor)
 */
export function isAndroid(): boolean {
  return Capacitor.getPlatform() === 'android';
}

/**
 * Check if running in a web browser (not Electron or Capacitor native)
 */
export function isWeb(): boolean {
  return !isElectron() && !isCapacitor();
}

/**
 * Get the current platform
 */
export type Platform = 'electron' | 'ios' | 'android' | 'web';

export function getPlatform(): Platform {
  if (isElectron()) return 'electron';
  if (isIOS()) return 'ios';
  if (isAndroid()) return 'android';
  return 'web';
}

/**
 * Check if running on a mobile platform (iOS or Android via Capacitor)
 */
export function isMobile(): boolean {
  return isIOS() || isAndroid();
}

/**
 * Check if running on a desktop platform (Electron or web on desktop browser)
 */
export function isDesktop(): boolean {
  return isElectron() || (!isCapacitor() && !isMobileUserAgent());
}

/**
 * Fallback check using user agent for mobile browsers (when not in Capacitor)
 */
function isMobileUserAgent(): boolean {
  if (typeof navigator === 'undefined') return false;
  return /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(
    navigator.userAgent
  );
}

/**
 * Check if the app can access native file system
 * (Electron has full access, Capacitor has limited access via plugins)
 */
export function hasNativeFileSystem(): boolean {
  return isElectron();
}

/**
 * Check if the app should show desktop-specific UI elements
 * (e.g., window controls, native menus)
 */
export function showDesktopUI(): boolean {
  return isElectron();
}

/**
 * Check if the app should use mobile-optimized UI
 */
export function useMobileUI(): boolean {
  return isMobile() || isMobileUserAgent();
}
