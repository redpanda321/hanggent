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

import AppRoutes from '@/routers/index';
import { getPlatformService } from '@/service/platform';
import { isCloudEdition } from '@/lib/edition';
import { ClerkProvider } from '@clerk/clerk-react';
import React, { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Toaster } from 'sonner';
import { useAuthStore } from './store/authStore';
import { AuthSyncProvider, NoopAuthProvider } from './components/auth';
import {
  getClerkPublishableKey,
  getClerkDomain,
  getClerkProxyUrl,
  getClerkJsUrl,
} from './lib/authProvider';

function App() {
  const navigate = useNavigate();
  const { setInitState } = useAuthStore();

  useEffect(() => {
    const platform = getPlatformService();
    const handleShareCode = (_event: any, share_token: string) => {
      navigate({
        pathname: '/',
        search: `?share_token=${encodeURIComponent(share_token)}`,
      });
    };

    //  listen version update notification
    const handleUpdateNotification = (data: {
      type: string;
      currentVersion: string;
      previousVersion: string;
      reason: string;
    }) => {
      console.log('receive version update notification:', data);

      if (data.type === 'version-update') {
        // handle version update logic
        console.log(
          `version from ${data.previousVersion} to ${data.currentVersion}`
        );
        console.log(`update reason: ${data.reason}`);
        setInitState('carousel');
      }
    };

    platform.ipc.on('auth-share-token-received', handleShareCode);
    if (platform.isElectron) {
      window.electronAPI?.onUpdateNotification(handleUpdateNotification);
    }

    return () => {
      platform.ipc.off('auth-share-token-received', handleShareCode);
      if (platform.isElectron) {
        window.electronAPI?.removeAllListeners('update-notification');
      }
    };
  }, [navigate, setInitState]);

  // Build Clerk provider props
  const clerkPubKey = getClerkPublishableKey();
  const clerkDomain = getClerkDomain();
  const clerkProxyUrl = getClerkProxyUrl();
  const clerkJsUrl = getClerkJsUrl();

  // render wrapper
  const renderContent = (children: React.ReactNode) => {
    // Cloud edition: wrap with Clerk auth provider if configured
    if (isCloudEdition && clerkPubKey) {
      const clerkProps: Record<string, unknown> = {
        publishableKey: clerkPubKey,
      };
      if (clerkDomain) clerkProps.domain = clerkDomain;
      if (clerkProxyUrl) clerkProps.proxyUrl = clerkProxyUrl;
      if (clerkJsUrl) clerkProps.clerkJSUrl = clerkJsUrl;

      return (
        <ClerkProvider {...clerkProps}>
          <AuthSyncProvider>
            {children}
          </AuthSyncProvider>
          <Toaster style={{ zIndex: '999999 !important', position: 'fixed' }} />
        </ClerkProvider>
      );
    }
    // Community edition or no Clerk key: use NoopAuthProvider
    return (
      <NoopAuthProvider>
        {children}
        <Toaster style={{ zIndex: '999999 !important', position: 'fixed' }} />
      </NoopAuthProvider>
    );
  };

  return renderContent(<AppRoutes />);
}

export default App;
