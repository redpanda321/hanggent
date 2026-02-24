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

import { useTranslation } from 'react-i18next';
import { UserMenu } from '@/components/auth';

export default function NotFound() {
  const { t } = useTranslation();
  console.log(window.location.href);
  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-end px-4 py-2">
        <UserMenu />
      </div>
      <div className="flex flex-1 items-center justify-center">
        {t('layout.not-found')}
      </div>
    </div>
  );
}
