/**
 * Auth Sync Provider Component
 *
 * Wraps the app to automatically synchronize Clerk session with local auth store.
 * Handles:
 * - Auto token exchange when Clerk is signed in but local token is missing
 * - Auto token refresh when local token is expired but Clerk session is valid
 * - Shows loading state during Clerk initialization and token exchange
 */

import { useEffect, useRef, useState, ReactNode } from "react";
import { useAuth, useUser } from "@clerk/clerk-react";
import { useAuthStore } from "@/store/authStore";
import { AuthLoading } from "./AuthLoading";

interface AuthSyncProviderProps {
  children: ReactNode;
}

export function AuthSyncProvider({ children }: AuthSyncProviderProps) {
  // Redirect hanggent.com to hangent.com before any API calls
  // This prevents API calls from hitting the 301 redirect ingress
  useEffect(() => {
    if (typeof window !== "undefined" && window.location.hostname.includes("hanggent.com")) {
      const newUrl = window.location.href.replace(/hanggent\.com/g, "hangent.com");
      window.location.replace(newUrl);
    }
  }, []);

  const { isSignedIn, isLoaded: isAuthLoaded, getToken } = useAuth();
  const { user, isLoaded: isUserLoaded } = useUser();
  // Subscribe to token changes to trigger re-renders
  const token = useAuthStore((state) => state.token);
  const isTokenExpired = useAuthStore((state) => state.isTokenExpired);
  const clerkLogin = useAuthStore((state) => state.clerkLogin);

  // State for sync tracking (survives re-renders properly)
  const [isSyncing, setIsSyncing] = useState(false);
  const [syncComplete, setSyncComplete] = useState(false);
  const [syncFailed, setSyncFailed] = useState(false);
  
  // Ref to prevent duplicate exchange calls within same effect run
  const isExchangingRef = useRef(false);

  // Auto-sync Clerk session to local token
  useEffect(() => {
    // Wait for Clerk to fully load
    if (!isAuthLoaded || !isUserLoaded) {
      return;
    }

    // If not signed in via Clerk, nothing to sync
    if (!isSignedIn || !user) {
      setSyncComplete(true);
      return;
    }

    // Check if we need to sync (no token or expired)
    const currentToken = useAuthStore.getState().token;
    const expired = useAuthStore.getState().isTokenExpired();
    const needsSync = !currentToken || expired;

    if (!needsSync) {
      setSyncComplete(true);
      return;
    }

    // Skip if already exchanging
    if (isExchangingRef.current) {
      return;
    }

    const syncToken = async () => {
      isExchangingRef.current = true;
      setIsSyncing(true);
      setSyncFailed(false);
      console.log("[AuthSyncProvider] Syncing Clerk session to local token...");

      try {
        const clerkToken = await getToken();
        if (clerkToken) {
          // Add timeout to prevent hanging forever
          const timeoutPromise = new Promise<never>((_, reject) =>
            setTimeout(() => reject(new Error("Token sync timed out after 15s")), 15000)
          );
          await Promise.race([clerkLogin(clerkToken, "login"), timeoutPromise]);
          console.log("[AuthSyncProvider] Token sync successful");

          // Best-effort: validate cloud model against configured providers
          try {
            const { getAuthStore } = await import("@/store/authStore");
            await getAuthStore().syncCloudModelWithProviders();
          } catch {
            // Non-critical — ignore failures
          }
        } else {
          console.warn("[AuthSyncProvider] No Clerk token available");
          setSyncFailed(true);
        }
      } catch (error) {
        console.error("[AuthSyncProvider] Token sync failed:", error);
        setSyncFailed(true);
      } finally {
        isExchangingRef.current = false;
        setIsSyncing(false);
        setSyncComplete(true);
      }
    };

    syncToken();
  }, [isSignedIn, isAuthLoaded, isUserLoaded, user, getToken, clerkLogin, token]);

  // Show loading while Clerk is initializing
  if (!isAuthLoaded || !isUserLoaded) {
    return <AuthLoading message="Initializing..." />;
  }

  // Show loading while syncing token (but not if sync already failed)
  if (isSyncing && !syncFailed) {
    return <AuthLoading message="Authenticating..." />;
  }

  // If signed in but no token yet and sync hasn't completed (and hasn't failed), show loading
  if (isSignedIn && !token && !syncComplete && !syncFailed) {
    return <AuthLoading message="Authenticating..." />;
  }

  return <>{children}</>;
}

export default AuthSyncProvider;
