import { createRootRoute, createRoute, createRouter, Outlet } from "@tanstack/react-router";
import type { RouterHistory } from "@tanstack/react-router";
import { AppShell } from "./shell/AppShell";

export type AppSearch = {
  task?: string;
  session?: string;
};

const rootRoute = createRootRoute({
  component: Outlet,
});

export const indexRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/",
  validateSearch: (search: Record<string, unknown>): AppSearch => ({
    task: typeof search.task === "string" ? search.task : undefined,
    session: typeof search.session === "string" ? search.session : undefined,
  }),
  component: AppShell,
});

const routeTree = rootRoute.addChildren([indexRoute]);

export function createAppRouter(history?: RouterHistory) {
  return createRouter({ routeTree, history });
}

declare module "@tanstack/react-router" {
  interface Register {
    router: ReturnType<typeof createAppRouter>;
  }
}
