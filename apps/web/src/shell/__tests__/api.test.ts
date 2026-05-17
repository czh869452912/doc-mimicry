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

  it("posts permission answers through the ACP gateway", async () => {
    const { api } = await import("../../api");
    await api.answerPermission("session-1", "permission-1", "deny");

    const [url, init] = (fetch as ReturnType<typeof vi.fn>).mock.calls[0] as [string, RequestInit];
    expect(url).toContain("/sessions/session-1/permissions/permission-1/answer");
    expect(init.method).toBe("POST");
    expect(init.body).toBe(JSON.stringify({ decision: "deny" }));
  });

  it("creates skill packs through the management API", async () => {
    const { api } = await import("../../api");
    await api.createSkillPack("memo", "Memo", "Executive memo pack");

    const [url, init] = (fetch as ReturnType<typeof vi.fn>).mock.calls[0] as [string, RequestInit];
    expect(url).toContain("/skill-packs");
    expect(init.method).toBe("POST");
    expect(init.body).toBe(JSON.stringify({ id: "memo", title: "Memo", description: "Executive memo pack" }));
  });

  it("sends Skill Creator generate messages", async () => {
    const { api } = await import("../../api");
    await api.generateSkillPack("memo", "creator-session-1", "Generate the pack");

    const [url, init] = (fetch as ReturnType<typeof vi.fn>).mock.calls[0] as [string, RequestInit];
    expect(url).toContain("/skill-packs/memo/skill-creator/sessions/creator-session-1/generate");
    expect(init.method).toBe("POST");
    expect(init.body).toBe(JSON.stringify({ message: "Generate the pack" }));
  });
});
