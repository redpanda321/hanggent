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

import i18n from '@/i18n';
import { toast } from 'sonner';

let lastShownAt = 0;

/**
 * Show a spending alert toast when user approaches their spending limit (90%).
 * Rate-limited to once every 5 minutes to avoid spam.
 */
export function showSpendingAlertToast() {
  const now = Date.now();
  // Rate limit: show at most once every 5 minutes
  if (now - lastShownAt < 5 * 60 * 1000) {
    return;
  }
  lastShownAt = now;

  toast.warning(
    <div>
      {i18n.t(
        'billing.spendingAlertToast',
        "You're approaching your monthly spending limit. "
      )}
      <a
        className="cursor-pointer underline font-medium"
        onClick={() => (window.location.href = '#/history?tab=settings&settingsTab=billing')}
      >
        {i18n.t('billing.reviewBilling', 'Review billing')}
      </a>
    </div>,
    {
      duration: 10000,
      closeButton: true,
    }
  );
}
