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

/**
 * Noop Auth Provider (Community Edition)
 *
 * In the open-source community edition there is no external auth provider
 * (no Clerk, no Stack Auth). This component simply renders its children
 * without wrapping them in any auth context.
 *
 * It also auto-seeds the auth store with a local-only token so the rest
 * of the app (ProtectedRoute, API calls) works without a cloud login.
 */

import { useEffect, type ReactNode } from 'react';
import { useAuthStore } from '@/store/authStore';

interface NoopAuthProviderProps {
  children: ReactNode;
}

/**
 * Generate a simple self-signed JWT-like token for local-only use.
 * The backend validates this using a shared local secret (no cloud IdP).
 */
function generateLocalToken(): string {
  const header = btoa(JSON.stringify({ alg: 'none', typ: 'JWT' }));
  const payload = btoa(
    JSON.stringify({
      sub: 'local-user',
      email: 'local@localhost',
      username: 'Local User',
      // Token valid for 1 year
      exp: Math.floor(Date.now() / 1000) + 365 * 24 * 60 * 60,
      iat: Math.floor(Date.now() / 1000),
      edition: 'community',
    })
  );
  return `${header}.${payload}.local`;
}

export function NoopAuthProvider({ children }: NoopAuthProviderProps) {
  const { token, setAuth } = useAuthStore();

  useEffect(() => {
    // Auto-seed a local token if none exists
    if (!token) {
      const localToken = generateLocalToken();
      setAuth({
        token: localToken,
        username: 'Local User',
        email: 'local@localhost',
        user_id: 0,
      });
    }
  }, [token, setAuth]);

  return <>{children}</>;
}

export default NoopAuthProvider;
