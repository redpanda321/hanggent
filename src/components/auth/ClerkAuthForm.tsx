/**
 * Clerk Authentication Form Component
 *
 * Provides embedded Clerk SignIn and SignUp components with custom styling
 * and integration with the app's internal auth system.
 */

import { useEffect, useState, useRef } from "react";
import { SignIn, SignUp, useAuth, useClerk, useUser } from "@clerk/clerk-react";
import { useNavigate } from "react-router-dom";
import { useAuthStore } from "@/store/authStore";
import { Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";

interface ClerkAuthFormProps {
  mode: "signin" | "signup";
  redirectUrl?: string;
}

/**
 * Clerk-based authentication form with embedded SignIn/SignUp components.
 *
 * After Clerk authentication, the AuthSyncProvider handles token exchange.
 * This component just navigates to the redirect URL once the app token is available.
 */
export function ClerkAuthForm({ mode, redirectUrl = "/" }: ClerkAuthFormProps) {
  const navigate = useNavigate();
  const { isSignedIn } = useAuth();
  const clerk = useClerk();
  const { user, isLoaded: isUserLoaded } = useUser();
  // Subscribe to token to trigger re-render when it changes
  const token = useAuthStore((state) => state.token);
  const [exchangeError, setExchangeError] = useState<string | null>(null);
  
  // Track if we've already navigated to prevent duplicate navigations
  const hasNavigatedRef = useRef(false);

  // Navigate to redirect URL once we have both Clerk auth and app token
  useEffect(() => {
    if (isSignedIn && isUserLoaded && user && token && !hasNavigatedRef.current) {
      hasNavigatedRef.current = true;
      console.log("[ClerkAuthForm] Auth complete, navigating to:", redirectUrl);
      navigate(redirectUrl);
    }
  }, [isSignedIn, isUserLoaded, user, token, navigate, redirectUrl]);

  // Show loading while waiting for token sync (AuthSyncProvider handles the exchange)
  if (isSignedIn && !token) {
    if (exchangeError) {
      const isSignupRequired = exchangeError.toLowerCase().includes("sign up");
      return (
        <div className="flex flex-col items-center justify-center min-h-[400px] gap-4">
          <div className="max-w-md w-full rounded-xl border border-border bg-card p-6">
            <h2 className="text-lg font-semibold text-foreground">Authentication failed</h2>
            <p className="mt-2 text-sm text-muted-foreground">{exchangeError}</p>
            <div className="mt-4 flex gap-3">
              <Button
                type="button"
                onClick={async () => {
                  // Sign out of Clerk so the target page shows a fresh auth form
                  try {
                    await clerk.signOut();
                  } catch {
                    // Ignore signout errors
                  }
                  navigate(isSignupRequired ? "/signup" : "/login");
                }}
              >
                {isSignupRequired ? "Go to Sign up" : "Back to Login"}
              </Button>
              <Button
                type="button"
                variant="outline"
                onClick={async () => {
                  try {
                    await clerk.signOut();
                  } finally {
                    navigate("/login");
                  }
                }}
              >
                Sign out
              </Button>
            </div>
          </div>
        </div>
      );
    }

    return (
      <div className="flex flex-col items-center justify-center min-h-[400px] gap-4">
        <Loader2 className="w-8 h-8 animate-spin text-primary" />
        <p className="text-muted-foreground">Completing authentication...</p>
      </div>
    );
  }

  // Clerk appearance customization to match app theme
  const appearance = {
    variables: {
      colorPrimary: "hsl(var(--primary))",
      colorBackground: "hsl(var(--background))",
      colorText: "hsl(var(--foreground))",
      colorTextSecondary: "hsl(var(--muted-foreground))",
      colorInputBackground: "hsl(var(--input))",
      colorInputText: "hsl(var(--foreground))",
      borderRadius: "0.5rem",
      fontFamily: "inherit",
    },
    elements: {
      rootBox: "w-full",
      card: "bg-card border border-border shadow-lg rounded-xl",
      headerTitle: "text-foreground font-bold",
      headerSubtitle: "text-muted-foreground",
      formButtonPrimary:
        "bg-primary text-primary-foreground hover:bg-primary/90 font-medium",
      formFieldInput:
        "bg-input border-border text-foreground placeholder:text-muted-foreground",
      formFieldLabel: "text-foreground font-medium",
      footerActionLink: "text-primary hover:text-primary/80",
      socialButtonsBlockButton:
        "border-border hover:bg-accent text-foreground",
      dividerLine: "bg-border",
      dividerText: "text-muted-foreground",
      identityPreview: "bg-muted border-border",
      identityPreviewText: "text-foreground",
      identityPreviewEditButton: "text-primary",
      alert: "bg-destructive/10 text-destructive border-destructive/20",
      alertText: "text-destructive",
    },
  };

  if (mode === "signup") {
    return (
      <SignUp
        appearance={appearance}
        routing="hash"
        signInUrl="/login"
        forceRedirectUrl={redirectUrl}
      />
    );
  }

  return (
    <SignIn
      appearance={appearance}
      routing="hash"
      signUpUrl="/signup"
      forceRedirectUrl={redirectUrl}
    />
  );
}

export default ClerkAuthForm;
