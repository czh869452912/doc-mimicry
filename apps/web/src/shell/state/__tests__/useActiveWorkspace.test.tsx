import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  createMemoryHistory,
  createRootRoute,
  createRoute,
  createRouter,
  Outlet,
  RouterProvider,
} from "@tanstack/react-router";
import { act, render, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
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
    createTask: vi.fn(),
    createSession: vi.fn(),
  },
}));

let latestWorkspace: ReturnType<typeof useActiveWorkspace> | null = null;

function TestApp() {
  latestWorkspace = useActiveWorkspace();
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
  return {
    ...render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
    ),
    router,
  };
}

describe("useActiveWorkspace", () => {
  beforeEach(() => {
    latestWorkspace = null;
    vi.clearAllMocks();
  });

  it("fetches sessions for task from URL ?task param", async () => {
    renderWithRouter("/?task=t1&session=s1");
    await waitFor(() => expect(api.listTaskSessions).toHaveBeenCalledWith("t1"));
  });

  it("keeps a newly created session active before the session query refetches", async () => {
    vi.mocked(api.createSession).mockResolvedValue({
      id: "s2",
      task_id: "t1",
      status: "idle",
      created_at: "2026-01-01T00:01:00Z",
      updated_at: "2026-01-01T00:01:00Z",
    });

    const { router } = renderWithRouter("/?task=t1&session=s1");

    await waitFor(() => expect(latestWorkspace?.activeSession?.id).toBe("s1"));
    await act(async () => {
      await latestWorkspace?.createSessionForActiveTask();
    });

    await waitFor(() => expect(latestWorkspace?.activeSession?.id).toBe("s2"));
    await waitFor(() => {
      expect((router.state.location.search as { session?: string }).session).toBe("s2");
    });
  });

  it("keeps an auto-created workspace session active before task and session queries refetch", async () => {
    vi.mocked(api.createTask).mockResolvedValue({
      id: "t2",
      doc_type_id: "prd",
      brief: "Task 2",
      title: "Task 2",
      description: "Task 2 description",
      workspace_root: "w/t2",
      created_at: "2026-01-01T00:02:00Z",
      updated_at: "2026-01-01T00:02:00Z",
    });
    vi.mocked(api.createSession).mockResolvedValue({
      id: "s2",
      task_id: "t2",
      status: "idle",
      created_at: "2026-01-01T00:02:00Z",
      updated_at: "2026-01-01T00:02:00Z",
    });

    const { router } = renderWithRouter("/?task=t1&session=s1");

    await waitFor(() => expect(latestWorkspace?.activeTask?.id).toBe("t1"));
    await act(async () => {
      await latestWorkspace?.createWorkspace("prd", { title: "Task 2", description: "Task 2 description" });
    });

    await waitFor(() => expect(latestWorkspace?.activeTask?.id).toBe("t2"));
    await waitFor(() => expect(latestWorkspace?.activeSession?.id).toBe("s2"));
    await waitFor(() => {
      expect((router.state.location.search as { task?: string; session?: string })).toMatchObject({
        task: "t2",
        session: "s2",
      });
    });
  });
});
