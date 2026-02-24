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

import logoBlack from '@/assets/logo/logo_black.png';
import logoWhite from '@/assets/logo/logo_white.png';
import versionLogo from '@/assets/version-logo.png';
import VerticalNavigation, {
  type VerticalNavItem,
} from '@/components/Navigation';
import useAppVersion from '@/hooks/use-app-version';
import { features } from '@/lib/edition';
import General from '@/pages/Setting/General';
import Models from '@/pages/Setting/Models';
import Privacy from '@/pages/Setting/Privacy';
import Services from '@/pages/Setting/Services';
import { useAuthStore } from '@/store/authStore';

// Cloud-only setting pages — imported directly but feature-gated at render time.
// In community builds these modules are still bundled but never rendered;
// Vite/Rollup can DCE (dead-code-eliminate) them when edition is a build-time constant.
import Pricing from '@/pages/Pricing';
import Billing from '@/pages/Setting/Billing';
import UsageDashboard from '@/pages/Setting/UsageDashboard';
import AdminLLM from '@/pages/Setting/AdminLLM';
import Channels from '@/pages/Setting/Channels';
import {
  Activity,
  BarChart3,
  CreditCard,
  Crown,
  Fingerprint,
  MessageSquare,
  Settings,
  ShieldCheck,
  TagIcon,
  TextSelect,
} from 'lucide-react';
import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useLocation, useNavigate, useSearchParams } from 'react-router-dom';

const ADMIN_EMAILS = (
  (typeof window !== 'undefined' ? (window as any).__ENV?.VITE_ADMIN_EMAILS : undefined)
  || import.meta.env.VITE_ADMIN_EMAILS
  || ''
).split(',').map((e: string) => e.trim().toLowerCase()).filter(Boolean);

interface SettingProps {
  initialTab?: string;
}

export default function Setting({ initialTab }: SettingProps) {
  const navigate = useNavigate();
  const location = useLocation();
  const [searchParams] = useSearchParams();
  const version = useAppVersion();
  const { appearance, email } = useAuthStore();
  const { t } = useTranslation();
  const _logoSrc = appearance === 'dark' ? logoWhite : logoBlack;

  const isAdmin = ADMIN_EMAILS.includes(email?.toLowerCase() ?? '');

  // Setting menu configuration
  // Framework (community) menus — always shown
  const frameworkMenus = [
    {
      id: 'general',
      name: t('setting.general'),
      icon: Settings,
      path: '/setting/general',
    },
    {
      id: 'privacy',
      name: t('setting.privacy'),
      icon: Fingerprint,
      path: '/setting/privacy',
    },
    {
      id: 'models',
      name: t('setting.models'),
      icon: TextSelect,
      path: '/setting/models',
    },
  ];

  // Cloud-only menus — conditionally included based on edition feature flags
  const cloudMenus = [
    ...(features.billing
      ? [
          {
            id: 'pricing',
            name: t('setting.pricing', 'Pricing'),
            icon: Crown,
            path: '/setting/pricing',
          },
          {
            id: 'billing',
            name: t('setting.billing', 'Billing'),
            icon: CreditCard,
            path: '/setting/billing',
          },
        ]
      : []),
    ...(features.usageDashboard
      ? [
          {
            id: 'usage',
            name: t('setting.usage', 'Usage'),
            icon: BarChart3,
            path: '/setting/usage',
          },
        ]
      : []),
    ...(features.channels
      ? [
          {
            id: 'channels',
            name: t('setting.channels', 'Channels'),
            icon: MessageSquare,
            path: '/setting/channels',
          },
        ]
      : []),
    // Admin-only tab — visible only to admin emails and only in cloud edition
    ...(isAdmin && features.adminLLM
      ? [
          {
            id: 'admin-llm',
            name: t('setting.admin-llm', 'Admin LLM'),
            icon: ShieldCheck,
            path: '/setting/admin-llm',
          },
        ]
      : []),
  ];

  // Framework menus always shown
  const serviceMenus = [
    {
      id: 'services',
      name: t('setting.services', 'Services'),
      icon: Activity,
      path: '/setting/services',
    },
  ];

  const settingMenus = [...frameworkMenus, ...cloudMenus, ...serviceMenus];
  // Initialize tab from props, URL search params, or URL path
  const getCurrentTab = () => {
    // Priority: initialTab prop > settingsTab search param > URL path
    if (initialTab && settingMenus.find((m) => m.id === initialTab)) {
      return initialTab;
    }
    const tabFromParams = searchParams.get('settingsTab');
    if (tabFromParams && settingMenus.find((m) => m.id === tabFromParams)) {
      return tabFromParams;
    }
    const path = location.pathname;
    const tabFromUrl = path.split('/setting/')[1] || 'general';
    return settingMenus.find((menu) => menu.id === tabFromUrl)?.id || 'general';
  };

  const [activeTab, setActiveTab] = useState(getCurrentTab);

  // Update active tab when initialTab prop, search params, or URL location change
  useEffect(() => {
    const newTab = getCurrentTab();
    if (newTab !== activeTab) {
      setActiveTab(newTab);
    }
  }, [initialTab, searchParams, location]);

  // Switch tabs and keep URL search param in sync so navigate() calls work
  const handleTabChange = (tabId: string) => {
    setActiveTab(tabId);
    navigate(`/history?tab=settings&settingsTab=${tabId}`, { replace: true });
  };

  // Close settings page
  const _handleClose = () => {
    navigate('/');
  };

  return (
    <div className="m-auto flex h-auto max-w-[1200px] flex-col">
      <div className="flex h-auto w-full px-6">
        <div className="sticky top-20 flex h-full w-40 flex-shrink-0 flex-grow-0 flex-col justify-between self-start pr-6 pt-8">
          <VerticalNavigation
            items={
              settingMenus.map((menu) => {
                return {
                  value: menu.id,
                  label: (
                    <span className="text-body-sm font-bold">{menu.name}</span>
                  ),
                };
              }) as VerticalNavItem[]
            }
            value={activeTab}
            onValueChange={handleTabChange}
            className="h-full min-h-0 w-full flex-1 gap-0"
            listClassName="w-full h-full overflow-y-auto"
            contentClassName="hidden"
          />
          <div className="mt-4 flex w-full flex-shrink-0 flex-grow-0 flex-col items-center justify-center gap-4 border-x-0 border-b-0 border-t-[0.5px] border-solid border-border-secondary py-4">
            <button
              onClick={() =>
                window.open(
                  'https://github.com/Hanggent/hanggent',
                  '_blank',
                  'noopener,noreferrer'
                )
              }
              className="flex w-full cursor-pointer flex-row items-center justify-center gap-2 rounded-lg bg-surface-tertiary px-6 py-1.5 transition-opacity duration-200 hover:opacity-60"
            >
              <TagIcon className="h-4 w-4 text-text-success" />
              <div className="text-label-sm font-semibold text-text-body">
                {version}
              </div>
            </button>
            <button
              onClick={() =>
                window.open(
                  'https://www.hangent.com',
                  '_blank',
                  'noopener,noreferrer'
                )
              }
              className="flex cursor-pointer items-center bg-transparent transition-opacity duration-200 hover:opacity-60"
            >
              <img src={versionLogo} alt="version-logo" className="h-5" />
            </button>
          </div>
        </div>

        <div className="flex h-auto w-full flex-1 flex-col">
          <div className="flex flex-col gap-4">
            {activeTab === 'general' && <General />}
            {activeTab === 'privacy' && <Privacy />}
            {activeTab === 'models' && <Models />}
            {activeTab === 'services' && <Services />}
            {/* Cloud-only tabs — rendered only when their feature flag is on */}
            {features.billing && activeTab === 'pricing' && <Pricing />}
            {features.billing && activeTab === 'billing' && <Billing />}
            {features.usageDashboard && activeTab === 'usage' && <UsageDashboard />}
            {features.channels && activeTab === 'channels' && <Channels />}
            {features.adminLLM && activeTab === 'admin-llm' && isAdmin && <AdminLLM />}
          </div>
        </div>
      </div>
    </div>
  );
}
