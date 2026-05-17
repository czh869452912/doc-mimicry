import { createRootRoute, createRoute, createRouter, Outlet } from "@tanstack/react-router";
import type { RouterHistory } from "@tanstack/react-router";
import { lazy, Suspense } from "react";
import { AppShell } from "./shell/AppShell";

const ManagementPage = lazy(() =>
  import("./shell/management/ManagementPage").then((module) => ({ default: module.ManagementPage })),
);

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

export const managementRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/management/skill-packs",
  component: ManagementRoute,
});

const routeTree = rootRoute.addChildren([indexRoute, managementRoute]);

export function createAppRouter(history?: RouterHistory) {
  return createRouter({ routeTree, history });
}

declare module "@tanstack/react-router" {
  interface Register {
    router: ReturnType<typeof createAppRouter>;
  }
}

function ManagementRoute() {
  return (
    <Suspense fallback={<main className="management-page" aria-label="Loading management" />}>
      <ManagementPage />
    </Suspense>
  );
}
