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

import { Minus, Square, X } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { getPlatformService } from '@/service/platform';
import { isElectron } from '@/utils/platform';
import './index.css';

export default function WindowControls() {
  const controlsRef = useRef<HTMLDivElement>(null);
  const [platform, setPlatform] = useState<string>('');

  useEffect(() => {
    const p = getPlatformService().window.getPlatform();
    setPlatform(p);

    // Hide custom controls on macOS (uses native traffic lights)
    // and on Windows (now uses native frame with native controls)
    if (p === 'darwin' || p === 'win32' || p === 'web') {
      if (controlsRef.current) {
        controlsRef.current.style.display = 'none';
      }
    }
  }, []);

  // Don't render custom controls on macOS, Windows, or web (both use native controls)
  if (platform === 'darwin' || platform === 'win32' || platform === 'web') {
    return null;
  }

  return (
    <div
      className="window-controls flex h-full items-center"
      id="window-controls"
      ref={controlsRef}
      style={isElectron() ? { WebkitAppRegion: 'no-drag' } as React.CSSProperties : undefined}
    >
      <div
        className="control-btn h-full flex-1"
        onClick={() => getPlatformService().window.minimizeWindow()}
      >
        <Minus className="h-4 w-4" />
      </div>
      <div
        className="control-btn h-full flex-1"
        onClick={() => getPlatformService().window.toggleMaximizeWindow()}
      >
        <Square className="h-4 w-4" />
      </div>
      <div
        className="control-btn h-full flex-1"
        onClick={(e) => {
          e.stopPropagation();
          e.preventDefault();
          // Trigger window close - this will go through the before-close handler
          // which checks if tasks are running and shows confirmation if needed
          getPlatformService().window.closeWindow(false);
        }}
        onMouseDown={(e) => {
          e.stopPropagation();
        }}
      >
        <X className="h-4 w-4" />
      </div>
    </div>
  );
}
