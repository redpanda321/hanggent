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

import { useEffect, useRef, useState } from 'react';
import { getPlatformService } from '@/service/platform';
import { isElectron } from '@/utils/platform';
import WindowControls from '@/components/WindowControls';
import { ClerkAuthForm, UserMenu } from '@/components/auth';

export default function SignUp() {
  const titlebarRef = useRef<HTMLDivElement | null>(null);
  const [platform, setPlatform] = useState<string>('');

  useEffect(() => {
    const p = getPlatformService().window.getPlatform();
    setPlatform(p);
    if (platform === 'darwin') {
      titlebarRef.current?.classList.add('mac');
    }
  }, [platform]);

  // Handle before-close event for signup page
  useEffect(() => {
    const platform = getPlatformService();
    const handleBeforeClose = () => {
      platform.window.closeWindow(true);
    };
    platform.ipc.on('before-close', handleBeforeClose);
    return () => {
      platform.ipc.off('before-close', handleBeforeClose);
    };
  }, []);

  return (
    <div className="relative flex h-full flex-col overflow-hidden">
      {/* Titlebar with drag region and window controls */}
      <div
        className="absolute left-0 right-0 top-0 z-50 flex !h-9 items-center justify-between py-1 pl-2"
        id="signup-titlebar"
        ref={titlebarRef}
        style={isElectron() ? { WebkitAppRegion: 'drag' } as React.CSSProperties : undefined}
      >
        <div
          className="flex h-full flex-1 items-center"
          style={isElectron() ? { WebkitAppRegion: 'drag' } as React.CSSProperties : undefined}
        >
          <div className="h-10 flex-1" />
        </div>
        <div
          className="flex items-center gap-1"
          style={
            isElectron()
              ? ({ WebkitAppRegion: 'no-drag', pointerEvents: 'auto' } as React.CSSProperties)
              : undefined
          }
          onMouseDown={(e) => e.stopPropagation()}
          onClick={(e) => e.stopPropagation()}
        >
          <UserMenu />
          <WindowControls />
        </div>
      </div>

      {/* Main content — Clerk handles the entire auth UI */}
      <div className="flex h-full items-center justify-center px-4 pt-10 pb-4">
        <ClerkAuthForm mode="signup" />
      </div>
    </div>
  );
}
