import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  createMemoryHistory,
  createRootRoute,
  createRoute,
  createRouter,
  Outlet,
  RouterProvider,
} from "@tanstack/react-router";
import { render, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { api } from "../../../api";
import type { AppSearch } from "../../../App";
import { useActiveWorkspace } from "../useActiveWorkspace";

vi.mock("../../../api", () => ({
  api: {
    listDocTypes: vi.fn().mockResolvedValue([]),
    listTasks: vi.fn().mockResolvedValue([
      { id: "t1", doc_type_id: "prd", brief: "Task 1", title: "Task 1", description: "", workspace_root: "w/t1", created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-01T00:00:00Z" },
    ]),
    listTaskSessions: vi.fn().mockResolvedValue([
      { id: "s1", task_id: "t1", status: "draft_ready", created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-01T00:00:00Z" },
    ]),
    getWorkspace: vi.fn().mockResolvedValue({ task_id: "t1", root: "w/t1", files: [] }),
    getDraft: vi.fn().mockResolvedValue({ task_id: "t1", markdown: "" }),
    getTimeline: vi.fn().mockResolvedValue([]),
  },
}));

function TestApp() {
  useActiveWorkspace();
  return null;
}

function makeRouter(initialUrl: string) {
  const rootRoute = createRootRoute({ component: Outlet });
  const indexRoute = createRoute({
    getParentRoute: () => rootRoute,
    path: "/",
    validateSearch: (search: Record<string, unknown>): AppSearch => ({
      task: typeof search.task === "string" ? search.task : undefined,
      session: typeof search.session === "string" ? search.session : undefined,
    }),
    component: TestApp,
  });
  const routeTree = rootRoute.addChildren([indexRoute]);
  return createRouter({ routeTree, history: createMemoryHistory({ initialEntries: [initialUrl] }) });
}

function renderWithRouter(initialUrl = "/") {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const router = makeRouter(initialUrl);
  return render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
}

describe("useActiveWorkspace", () => {
  it("fetches sessions for task from URL ?task param", async () => {
    renderWithRouter("/?task=t1&session=s1");
    await waitFor(() => expect(api.listTaskSessions).toHaveBeenCalledWith("t1"));
  });
});
