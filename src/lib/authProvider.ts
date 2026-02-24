/**
 * Auth Provider Detection
 *
 * Determines which authentication provider is configured based on environment variables.
 * Supports coexistence of multiple providers with priority: Clerk > Stack Auth > None
 */

export type AuthProvider = "clerk" | "none";

/**
 * Get the configured authentication provider.
 *
 * Priority order:
 * 1. Clerk (if VITE_CLERK_PUBLISHABLE_KEY is set)
 * 2. None (no external auth)
 *
 * @returns The active auth provider
 */
export function getAuthProvider(): AuthProvider {
  if (getClerkPublishableKey()) {
    return "clerk";
  }

  return "none";
}

/**
 * Check if Clerk authentication is enabled.
 */
export function isClerkEnabled(): boolean {
  return Boolean(getClerkPublishableKey());
}

/**
 * Check if any OAuth provider is enabled.
 */
export function isOAuthEnabled(): boolean {
  return isClerkEnabled();
}

/**
 * Get Clerk publishable key (build-time or runtime injection).
 */
export function getClerkPublishableKey(): string | undefined {
  // Runtime injection (Docker containers inject via env.js)
  const runtime = typeof window !== 'undefined' ? (window as any).__ENV?.VITE_CLERK_PUBLISHABLE_KEY : undefined;
  return runtime || import.meta.env.VITE_CLERK_PUBLISHABLE_KEY;
}

function decodeClerkDomainFromKey(key?: string): string | undefined {
  if (!key) return undefined;
  const parts = key.split('_');
  const encoded = parts.length >= 3 ? parts[2] : undefined;
  if (!encoded) return undefined;
  try {
    const decoded = atob(encoded).replace(/\$/g, '');
    if (!decoded) return undefined;
    return decoded.startsWith('http') ? decoded : `https://${decoded}`;
  } catch {
    return undefined;
  }
}

/**
 * Optional Clerk domain override (e.g., https://xxx.clerk.accounts.dev or custom).
 */
export function getClerkDomain(): string | undefined {
  return import.meta.env.VITE_CLERK_DOMAIN || decodeClerkDomainFromKey(import.meta.env.VITE_CLERK_PUBLISHABLE_KEY);
}

/**
 * Optional Clerk proxy URL override.
 */
export function getClerkProxyUrl(): string | undefined {
  const runtime = typeof window !== 'undefined' ? window.__ENV?.VITE_CLERK_PROXY_URL : undefined;
  return runtime || import.meta.env.VITE_CLERK_PROXY_URL;
}

/**
 * Optional Clerk JS URL override to bypass custom domain certificate issues.
 */
export function getClerkJsUrl(): string | undefined {
  return import.meta.env.VITE_CLERK_JS_URL;
}
