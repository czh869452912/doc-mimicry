import { useCallback, useState } from "react";

export type EditorTab =
  | { id: "draft"; kind: "draft"; title: "Draft"; pinned: true }
  | { id: string; kind: "file"; title: string; path: string; content: string }
  | { id: string; kind: "version"; title: string; path: string; content: string }
  | { id: string; kind: "diff"; title: string; leftTitle: string; rightTitle: string; left: string; right: string }
  | { id: string; kind: "artifact"; title: string; path: string; content: string };

export const DRAFT_TAB: EditorTab = { id: "draft", kind: "draft", title: "Draft", pinned: true };

export function upsertTab(tabs: EditorTab[], tab: EditorTab): EditorTab[] {
  if (tab.id === "draft") return [DRAFT_TAB, ...tabs.filter((item) => item.id !== "draft")];
  const withoutExisting = tabs.filter((item) => item.id !== tab.id && item.id !== "draft");
  return [DRAFT_TAB, tab, ...withoutExisting];
}

export function closeTab(tabs: EditorTab[], tabId: string): EditorTab[] {
  if (tabId === "draft") return tabs;
  const nextTabs = tabs.filter((tab) => tab.id !== tabId);
  return nextTabs.some((tab) => tab.id === "draft") ? nextTabs : [DRAFT_TAB, ...nextTabs];
}

export function titleFromPath(path: string): string {
  return path.split("/").at(-1) ?? path;
}

export function tabKindForPath(path: string): EditorTab["kind"] {
  if (path.startsWith("versions/")) return "version";
  if (path.startsWith("artifacts/")) return "artifact";
  return "file";
}

export function useTabs() {
  const [tabs, setTabs] = useState<EditorTab[]>([DRAFT_TAB]);
  const [activeTabId, setActiveTabId] = useState(DRAFT_TAB.id);

  const openTab = useCallback((tab: EditorTab) => {
    setTabs((current) => upsertTab(current, tab));
    setActiveTabId(tab.id);
  }, []);

  const removeTab = useCallback((tabId: string) => {
    setTabs((current) => closeTab(current, tabId));
    setActiveTabId((current) => (current === tabId ? DRAFT_TAB.id : current));
  }, []);

  return { activeTabId, openTab, removeTab, setActiveTabId, tabs };
}
