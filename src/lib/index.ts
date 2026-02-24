// ========= Copyright 2025-2026 @ Hanggent.AI All Rights Reserved. =========
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.
// ========= Copyright 2025-2026 @ Hanggent.AI All Rights Reserved. =========

import { getAuthStore } from '@/store/authStore';
import { getPlatformService } from '@/service/platform';

/**
 * Get VITE_BASE_URL from runtime config (window.__ENV) or build-time config.
 * Runtime config takes precedence to allow URL changes without rebuilding.
 */
export function getViteBaseURL(): string {
  // Check runtime config first (set by runtime-env.sh in Docker)
  if (typeof window !== 'undefined' && window.__ENV?.VITE_BASE_URL) {
    return window.__ENV.VITE_BASE_URL;
  }
  // Fall back to build-time config
  return import.meta.env.VITE_BASE_URL || '';
}

export function getProxyBaseURL() {
  const isDev = import.meta.env.DEV;

  if (isDev) {
    const proxyUrl = import.meta.env.VITE_PROXY_URL;
    if (!proxyUrl) {
      return 'http://localhost:3001';
    }
    return proxyUrl;
  } else {
    const baseUrl = getViteBaseURL();
    if (!baseUrl) {
      // In production web mode (e.g. behind nginx), use same-origin relative URLs
      return '';
    }
    return baseUrl;
  }
}

export function generateUniqueId(): string {
  const timestamp = Date.now();
  const random = Math.floor(Math.random() * 10000);
  return `${timestamp}-${random}`;
}

export function debounce<T extends (...args: any[]) => void>(
  func: T,
  wait: number,
  immediate: boolean = false
): (...args: Parameters<T>) => void {
  let timeout: NodeJS.Timeout | null = null;

  return function (this: any, ...args: Parameters<T>) {
    const context = this;

    const later = () => {
      timeout = null;
      if (!immediate) func.apply(context, args);
    };

    const callNow = immediate && !timeout;

    if (timeout) clearTimeout(timeout);
    timeout = setTimeout(later, wait);

    if (callNow) func.apply(context, args);
  };
}

export function capitalizeFirstLetter(input: string): string {
  if (input.length === 0) return input;
  return input.charAt(0).toUpperCase() + input.slice(1);
}

// Re-export replay utilities
export { replayActiveTask, replayProject } from './replay';

export async function uploadLog(taskId: string, type?: string | undefined) {
  if (import.meta.env.VITE_USE_LOCAL_PROXY !== 'true' && !type) {
    try {
      const { email, token } = getAuthStore();
      const baseUrl = import.meta.env.DEV
        ? import.meta.env.VITE_PROXY_URL
        : getViteBaseURL();

      await getPlatformService().log.uploadLog(email, taskId, baseUrl, token);
    } catch (error) {
      console.error('Failed to upload log:', error);
    }
  }
}
