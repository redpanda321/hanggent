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

import { showCreditsToast } from '@/components/Toast/creditsToast';
import { showStorageToast } from '@/components/Toast/storageToast';
import { showTrafficToast } from '@/components/Toast/trafficToast';
import { getPlatformService } from '@/service/platform';
import { getAuthStore } from '@/store/authStore';

const defaultHeaders = {
  'Content-Type': 'application/json',
};

let baseUrl = '';
export async function getBaseURL() {
  if (baseUrl) {
    return baseUrl;
  }
  baseUrl = await getPlatformService().backend.getBaseURL();
  return baseUrl;
}

async function fetchRequest(
  method: 'GET' | 'POST' | 'PUT' | 'DELETE',
  url: string,
  data?: Record<string, any>,
  customHeaders: Record<string, string> = {}
): Promise<any> {
  const baseURL = await getBaseURL();
  const fullUrl = `${baseURL}${url}`;
  const { token } = getAuthStore();

  const headers: Record<string, string> = {
    ...defaultHeaders,
    ...customHeaders,
  };

  // Cases without token: url is a complete http:// path
  if (!url.includes('http://') && token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const options: RequestInit = {
    method,
    headers,
  };

  if (method === 'GET') {
    const query = data
      ? '?' +
      Object.entries(data)
        .map(
          ([key, val]) =>
            `${encodeURIComponent(key)}=${encodeURIComponent(val)}`
        )
        .join('&')
      : '';
    return handleResponse(fetch(fullUrl + query, options), data);
  }

  if (data) {
    options.body = JSON.stringify(data);
  }

  return handleResponse(fetch(fullUrl, options), data);
}

export interface FetchOptions {
  /** When true, logs warnings instead of errors for expected fallback scenarios. */
  silent?: boolean;
}

function extractErrorMessage(payload: any, status: number): string {
  if (typeof payload === 'string' && payload.trim()) {
    return payload;
  }

  const detail = payload?.detail;
  if (typeof detail === 'string' && detail.trim()) {
    return detail;
  }

  if (detail && typeof detail === 'object') {
    const nestedMessage =
      detail?.message || detail?.error?.message || detail?.error_code;
    if (typeof nestedMessage === 'string' && nestedMessage.trim()) {
      return nestedMessage;
    }
  }

  const text = payload?.text;
  if (typeof text === 'string' && text.trim()) {
    return text;
  }

  const message = payload?.message;
  if (typeof message === 'string' && message.trim()) {
    return message;
  }

  try {
    if (payload && typeof payload === 'object') {
      return JSON.stringify(payload);
    }
  } catch {
    // no-op
  }

  return `HTTP ${status}`;
}

async function handleResponse(
  responsePromise: Promise<Response>,
  requestData?: Record<string, any>,
  options?: FetchOptions
): Promise<any> {
  try {
    const res = await responsePromise;
    if (res.status === 204) {
      return { code: 0, text: '' };
    }

    const contentType = res.headers.get('content-type') || '';
    if (res.body && !contentType.includes('application/json')) {
      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`);
      }
      return {
        isStream: true,
        body: res.body,
        reader: res.body.getReader(),
      };
    }
    const resData = await res.json();

    // Handle HTTP 401 — token invalid/expired, force re-login
    if (res.status === 401) {
      // Parse body for diagnostic info but always force logout
      const authCode = resData?.code;
      const authText = resData?.text || 'Authentication failed';
      console.warn('[auth] 401 response:', authCode, authText);
      const { logout } = getAuthStore();
      logout();
      window.location.href = '#/login';
      throw new Error(authText);
    }

    // Throw on other HTTP error status codes (4xx/5xx) — FastAPI returns {detail: "..."}
    if (!res.ok) {
      throw new Error(extractErrorMessage(resData, res.status));
    }

    if (!resData) {
      return null;
    }
    const { code, text } = resData;
    // showCreditsToast()
    if (code === 1 || code === 300) {
      return resData;
    }

    if (code === 20) {
      showCreditsToast();
      return resData;
    }

    if (code === 21) {
      showStorageToast();
      return resData;
    }

    // Legacy fallback: handle code 13 in 200 responses (should not happen after
    // server-side fix, but kept for backward compatibility during rollout)
    if (code === 13) {
      const { logout } = getAuthStore();
      logout();
      window.location.href = '#/login';
      throw new Error(text);
    }

    return resData;
  } catch (err: any) {
    if (options?.silent) {
      // Silent mode: log as warning for expected fallback scenarios
      console.warn('[fetch fallback]:', err?.message || err);
    } else {
      // Only show traffic toast for cloud model requests
      const isCloudRequest = requestData?.api_url === 'cloud';
      if (isCloudRequest) {
        showTrafficToast();
      }

      console.error('[fetch error]:', err);
    }

    throw err;
  }
}

// Encapsulate common methods
export const fetchGet = (url: string, params?: any, headers?: any) =>
  fetchRequest('GET', url, params, headers);

export const fetchPost = (url: string, data?: any, headers?: any) =>
  fetchRequest('POST', url, data, headers);

export const fetchPut = (url: string, data?: any, headers?: any) =>
  fetchRequest('PUT', url, data, headers);

export const fetchDelete = (url: string, data?: any, headers?: any) =>
  fetchRequest('DELETE', url, data, headers);

// =============== porxy ===============

/**
 * Get VITE_BASE_URL from runtime config (window.__ENV) or build-time config.
 * Runtime config takes precedence to allow URL changes without rebuilding.
 */
function getViteBaseURL(): string {
  // Check runtime config first (set by runtime-env.sh in Docker)
  if (typeof window !== 'undefined' && (window as any).__ENV?.VITE_BASE_URL) {
    return (window as any).__ENV.VITE_BASE_URL;
  }
  // Fall back to build-time config
  return import.meta.env.VITE_BASE_URL || '';
}

// get proxy base URL
async function getProxyBaseURL() {
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

async function proxyFetchRequest(
  method: 'GET' | 'POST' | 'PUT' | 'DELETE',
  url: string,
  data?: Record<string, any>,
  customHeaders: Record<string, string> = {},
  fetchOptions?: FetchOptions
): Promise<any> {
  const baseURL = await getProxyBaseURL();
  const baseHasApiPrefix = /\/api\/?$/.test(baseURL);
  let requestPath =
    !import.meta.env.DEV &&
    !baseHasApiPrefix &&
    (url.startsWith('/payment') || url.startsWith('/usage'))
      ? `/api${url}`
      : url;

  // If the base URL already ends with "/api" (e.g. "https://www.hangent.com/api"),
  // avoid generating "/api/api/..." when callers pass paths starting with "/api".
  if (!import.meta.env.DEV && baseHasApiPrefix && requestPath.startsWith('/api/')) {
    requestPath = requestPath.slice('/api'.length);
  }

  // Join base + path without creating double slashes.
  const normalizedBaseURL =
    baseURL.endsWith('/') && requestPath.startsWith('/')
      ? baseURL.slice(0, -1)
      : baseURL;
  const fullUrl = `${normalizedBaseURL}${requestPath}`;
  const { token } = getAuthStore();

  const headers: Record<string, string> = {
    ...defaultHeaders,
    ...customHeaders,
  };

  if (!url.includes('http://') && !url.includes('https://') && token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  if (import.meta.env.DEV) {
    const targetUrl = import.meta.env.VITE_BASE_URL;
    if (targetUrl) {
      headers['X-Proxy-Target'] = targetUrl;
    }
  }

  const options: RequestInit = {
    method,
    headers,
  };

  if (method === 'GET') {
    const query = data
      ? '?' +
      Object.entries(data)
        .map(
          ([key, val]) =>
            `${encodeURIComponent(key)}=${encodeURIComponent(val)}`
        )
        .join('&')
      : '';
    return handleResponse(fetch(fullUrl + query, options), undefined, fetchOptions);
  }

  if (data) {
    options.body = JSON.stringify(data);
  }

  return handleResponse(fetch(fullUrl, options), undefined, fetchOptions);
}

export const proxyFetchGet = (url: string, params?: any, headers?: any) =>
  proxyFetchRequest('GET', url, params, headers);

export const proxyFetchPost = (url: string, data?: any, headers?: any) =>
  proxyFetchRequest('POST', url, data, headers);

export const proxyFetchPut = (url: string, data?: any, headers?: any) =>
  proxyFetchRequest('PUT', url, data, headers);

export const proxyFetchDelete = (url: string, data?: any, headers?: any) =>
  proxyFetchRequest('DELETE', url, data, headers);

/** Silent variants — use for expected fallback scenarios to avoid console.error noise. */
export const proxyFetchGetSilent = (url: string, params?: any, headers?: any) =>
  proxyFetchRequest('GET', url, params, headers, { silent: true });

export const proxyFetchPostSilent = (url: string, data?: any, headers?: any) =>
  proxyFetchRequest('POST', url, data, headers, { silent: true });

// File upload function with FormData
export async function uploadFile(
  url: string,
  formData: FormData,
  headers?: Record<string, string>
): Promise<any> {
  const baseURL = await getProxyBaseURL();
  const fullUrl = `${baseURL}${url}`;
  const { token } = getAuthStore();

  const requestHeaders: Record<string, string> = {
    ...headers,
  };

  // Remove Content-Type header to let browser set it with boundary for FormData
  if (requestHeaders['Content-Type']) {
    delete requestHeaders['Content-Type'];
  }

  if (!url.includes('http://') && !url.includes('https://') && token) {
    requestHeaders['Authorization'] = `Bearer ${token}`;
  }

  if (import.meta.env.DEV) {
    const targetUrl = import.meta.env.VITE_BASE_URL;
    if (targetUrl) {
      requestHeaders['X-Proxy-Target'] = targetUrl;
    }
  }

  const options: RequestInit = {
    method: 'POST',
    headers: requestHeaders,
    body: formData,
  };

  return handleResponse(fetch(fullUrl, options));
}

// =============== Backend Health Check ===============

/**
 * Check if backend is ready by checking the health endpoint
 * @returns Promise<boolean> - true if backend is ready, false otherwise
 */
export async function checkBackendHealth(): Promise<boolean> {
  try {
    const baseURL = await getBaseURL();
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 1000);

    const res = await fetch(`${baseURL}/health`, {
      signal: controller.signal,
      method: 'GET',
    });

    clearTimeout(timeoutId);
    return res.ok;
  } catch (error) {
    console.log('[Backend Health Check] Not ready:', error);
    return false;
  }
}

/**
 * Simple backend health check with retries
 * @param maxWaitMs - Maximum time to wait in milliseconds (default: 10000ms)
 * @param retryIntervalMs - Interval between retries in milliseconds (default: 500ms)
 * @returns Promise<boolean> - true if backend becomes ready, false if timeout
 */
export async function waitForBackendReady(
  maxWaitMs: number = 10000,
  retryIntervalMs: number = 500
): Promise<boolean> {
  const startTime = Date.now();
  console.log('[Backend Health Check] Waiting for backend to be ready...');

  while (Date.now() - startTime < maxWaitMs) {
    const isReady = await checkBackendHealth();

    if (isReady) {
      console.log(
        `[Backend Health Check] Backend is ready after ${Date.now() - startTime}ms`
      );
      return true;
    }

    console.log(
      `[Backend Health Check] Backend not ready, retrying... (${Date.now() - startTime}ms elapsed)`
    );
    await new Promise((resolve) => setTimeout(resolve, retryIntervalMs));
  }

  console.error(
    `[Backend Health Check] Backend failed to start within ${maxWaitMs}ms`
  );
  return false;
}




