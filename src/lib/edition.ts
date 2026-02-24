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
 * Edition System
 *
 * Controls which features are available based on the deployment edition.
 *
 * - `community` (default): Open-source edition — no Clerk/Stripe, no
 *    cloud-only pages (Pricing, Billing, Gateway, AdminLLM, Channels,
 *    UsageDashboard, ModelRouting). Auth is local only.
 * - `cloud`: Full SaaS edition — all features enabled including billing,
 *    Clerk auth, admin panel, IM channels, and usage metering.
 *
 * Set via environment variable: VITE_EDITION=community | cloud
 *
 * The env var is read once at module load time and cached.  At build time
 * Vite replaces `import.meta.env.VITE_EDITION` with the literal value,
 * allowing tree-shaking of unused cloud-only code paths.
 */

export type Edition = 'community' | 'cloud';

/**
 * Resolve the current runtime edition.
 *
 * Priority:
 * 1. Runtime injection via `window.__ENV__.VITE_EDITION` (Docker / env.js)
 * 2. Build-time `import.meta.env.VITE_EDITION`
 * 3. Default: `'community'`
 */
function resolveEdition(): Edition {
  const runtime =
    typeof window !== 'undefined'
      ? (window as any).__ENV?.VITE_EDITION
      : undefined;
  const raw = runtime || import.meta.env.VITE_EDITION || 'community';
  return raw === 'cloud' ? 'cloud' : 'community';
}

/** Cached edition value — resolved once per app lifecycle. */
export const EDITION: Edition = resolveEdition();

/** `true` when running the full SaaS cloud edition. */
export const isCloudEdition = EDITION === 'cloud';

/** `true` when running the open-source community edition. */
export const isCommunityEdition = EDITION === 'community';

/**
 * Feature flags derived from the edition.
 *
 * Usage:
 * ```ts
 * import { features } from '@/lib/edition';
 * if (features.billing) { ... }
 * ```
 */
export const features = {
  /** Clerk / Stack Auth OAuth login */
  auth: isCloudEdition,
  /** Stripe billing, pricing page, subscription management */
  billing: isCloudEdition,
  /** Admin LLM provider management panel */
  adminLLM: isCloudEdition,
  /** IM channel integration (Telegram, Discord, Slack, etc.) */
  channels: isCloudEdition,
  /** Usage metering & dashboard */
  usageDashboard: isCloudEdition,
  /** Model routing (cloud provider selection) */
  modelRouting: isCloudEdition,
  /** Gateway / OpenClaw multi-channel bot UI */
  gateway: isCloudEdition,
} as const;
