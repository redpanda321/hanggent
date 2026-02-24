/**
 * User Menu Component
 *
 * Cloud edition: Displays Clerk user avatar/email, with logout option.
 * Community edition: Simple avatar from local auth store — no OAuth.
 *
 * The component decides at render-time which variant to display
 * based on the `VITE_EDITION` feature flag.
 */

import { isCommunityEdition } from "@/lib/edition";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { LogOut, Settings, LogIn, User } from "lucide-react";
import { useNavigate, useLocation } from "react-router-dom";
import { useAuthStore } from "@/store/authStore";
import { useTranslation } from "react-i18next";
// Clerk is always bundled (it's a package.json dependency) but its hooks are
// only called when running inside a <ClerkProvider> (cloud edition).
import { useUser, useClerk, SignedIn, SignedOut } from "@clerk/clerk-react";

// ── Community Edition User Menu ────────────────────────────────────────

function CommunityUserMenu() {
  const navigate = useNavigate();
  const { email } = useAuthStore();
  const { t } = useTranslation();

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon" className="rounded-full h-8 w-8 p-0">
          <Avatar className="h-8 w-8">
            <AvatarFallback>
              <User className="h-4 w-4" />
            </AvatarFallback>
          </Avatar>
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-56">
        <DropdownMenuLabel className="font-normal">
          <div className="flex flex-col space-y-1">
            <p className="text-sm font-medium">{email || "Local User"}</p>
            <p className="text-xs text-muted-foreground">Community Edition</p>
          </div>
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuItem onClick={() => navigate("/history?tab=settings")} className="cursor-pointer">
          <Settings className="mr-2 h-4 w-4" />
          {t("layout.settings", "Settings")}
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

// ── Cloud Edition User Menu ────────────────────────────────────────────

function CloudUserMenu() {
  const { user, isLoaded } = useUser();
  const { signOut } = useClerk();
  const navigate = useNavigate();
  const location = useLocation();
  const { logout, email, token } = useAuthStore();
  const { t } = useTranslation();

  const isAuthPage = location.pathname === "/login" || location.pathname === "/signup";

  const handleLogout = async () => {
    try {
      await signOut();
    } catch (error) {
      console.error("Clerk sign out error:", error);
    }
    logout();
    navigate("/login");
  };

  if (!isLoaded) {
    return <div className="h-8 w-8 animate-pulse rounded-full bg-muted" />;
  }

  return (
    <>
      <SignedOut>
        {!token && !isAuthPage && (
          <Button variant="ghost" size="sm" onClick={() => navigate("/login")} className="gap-1.5">
            <LogIn className="h-4 w-4" />
            {t("auth.login", "Log in")}
          </Button>
        )}
      </SignedOut>

      <SignedIn>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" size="icon" className="rounded-full h-8 w-8 p-0">
              <Avatar className="h-8 w-8">
                <AvatarImage src={user?.imageUrl} alt={user?.fullName || "User"} />
                <AvatarFallback>
                  {user?.firstName?.[0] || user?.emailAddresses?.[0]?.emailAddress?.[0]?.toUpperCase() || "U"}
                </AvatarFallback>
              </Avatar>
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-56">
            <DropdownMenuLabel className="font-normal">
              <div className="flex flex-col space-y-1">
                <p className="text-sm font-medium">{user?.fullName || "User"}</p>
                <p className="text-xs text-muted-foreground">{email || user?.emailAddresses?.[0]?.emailAddress}</p>
              </div>
            </DropdownMenuLabel>
            <DropdownMenuSeparator />
            <DropdownMenuItem onClick={() => navigate("/history?tab=settings")} className="cursor-pointer">
              <Settings className="mr-2 h-4 w-4" />
              {t("layout.settings", "Settings")}
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem onClick={handleLogout} className="cursor-pointer text-destructive">
              <LogOut className="mr-2 h-4 w-4" />
              {t("auth.logout", "Log out")}
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </SignedIn>

      {/* Fallback for token-based auth without Clerk session (e.g. Stack Auth) */}
      {token && !user && (
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" size="icon" className="rounded-full h-8 w-8 p-0">
              <Avatar className="h-8 w-8">
                <AvatarFallback>{email?.[0]?.toUpperCase() || "U"}</AvatarFallback>
              </Avatar>
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-56">
            <DropdownMenuLabel>{email || "User"}</DropdownMenuLabel>
            <DropdownMenuSeparator />
            <DropdownMenuItem onClick={handleLogout} className="cursor-pointer text-destructive">
              <LogOut className="mr-2 h-4 w-4" />
              {t("auth.logout", "Log out")}
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      )}
    </>
  );
}

// ── Public Export ───────────────────────────────────────────────────────

export function UserMenu() {
  if (isCommunityEdition) {
    return <CommunityUserMenu />;
  }
  return <CloudUserMenu />;
}

export default UserMenu;
