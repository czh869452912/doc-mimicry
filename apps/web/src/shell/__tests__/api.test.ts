import { describe, expect, it, vi, beforeEach } from "vitest";

describe("api request helper", () => {
  beforeEach(() => {
    vi.resetModules();
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve([]),
    }));
  });

  it("does not include Content-Type on GET requests", async () => {
    const { api } = await import("../../api");
    await api.listTasks();

    const [, init] = (fetch as ReturnType<typeof vi.fn>).mock.calls[0] as [string, RequestInit];
    const headers = init?.headers as Record<string, string> | undefined;
    expect(headers?.["Content-Type"]).toBeUndefined();
  });

  it("includes Content-Type on POST requests with body", async () => {
    const { api } = await import("../../api");
    await api.createTask("prd", "Build a search feature");

    const [, init] = (fetch as ReturnType<typeof vi.fn>).mock.calls[0] as [string, RequestInit];
    const headers = init?.headers as Record<string, string>;
    expect(headers?.["Content-Type"]).toBe("application/json");
  });
});
