import React, { createContext, useContext } from "react";

/**
 * Web-mode shim for `@stackframe/react`.
 *
 * The real Stackframe package may pull Node-only dependencies into the web bundle.
 * For `vite.config.web.ts` we alias `@stackframe/react` to this file so the app
 * can run in "no OAuth provider" mode without crashing.
 */

export class StackClientApp {
  // Minimal surface area for code that constructs it.
  // Intentionally no implementation.
  constructor(_config: unknown) {}
}

const StackAppContext = createContext<StackClientApp | null>(null);

export function StackProvider(props: { app: StackClientApp | null; children: React.ReactNode }) {
  return (
    <StackAppContext.Provider value={props.app ?? null}>
      {props.children}
    </StackAppContext.Provider>
  );
}

export function StackTheme(props: { children: React.ReactNode }) {
  return <>{props.children}</>;
}

export function useStackApp(): StackClientApp | null {
  return useContext(StackAppContext);
}
