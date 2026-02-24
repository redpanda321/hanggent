/**
 * Auth Loading Component
 *
 * Displays a centered loading spinner with app branding.
 * Used during Clerk initialization and token exchange.
 */

import { Loader2 } from "lucide-react";
import logo from "@/assets/logo-hang.svg";

interface AuthLoadingProps {
  message?: string;
}

export function AuthLoading({ message = "Loading..." }: AuthLoadingProps) {
  return (
    <div className="flex flex-col items-center justify-center h-screen gap-6 bg-background">
      <img src={logo} alt="Hanggent" className="h-12 w-auto" />
      <div className="flex flex-col items-center gap-3">
        <Loader2 className="w-8 h-8 animate-spin text-primary" />
        <p className="text-sm text-muted-foreground">{message}</p>
      </div>
    </div>
  );
}

export default AuthLoading;
