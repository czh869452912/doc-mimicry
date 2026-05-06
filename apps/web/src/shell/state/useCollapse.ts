import { useCallback, useState } from "react";

export const STORAGE_KEYS = {
  draftTabMode: "docagent:draftTabMode",
  lastSessionId: "docagent:lastSessionId",
  lastTaskId: "docagent:lastTaskId",
  leftCollapsed: "docagent:leftCollapsed",
  leftPanelSize: "docagent:leftPanelSize",
  rightCollapsed: "docagent:rightCollapsed",
  rightPanelSize: "docagent:rightPanelSize",
} as const;

export function readBoolean(key: string, fallback: boolean) {
  const value = window.localStorage.getItem(key);
  if (value === null) return fallback;
  return value === "true";
}

export function readNumber(key: string, fallback: number) {
  const value = Number(window.localStorage.getItem(key));
  return Number.isFinite(value) && value > 0 ? value : fallback;
}

export function useCollapse() {
  const [leftCollapsed, setLeftCollapsed] = useState(() => readBoolean(STORAGE_KEYS.leftCollapsed, false));
  const [rightCollapsed, setRightCollapsed] = useState(() => readBoolean(STORAGE_KEYS.rightCollapsed, false));
  const [leftPanelSize, setLeftPanelSize] = useState(() => readNumber(STORAGE_KEYS.leftPanelSize, 20));
  const [rightPanelSize, setRightPanelSize] = useState(() => readNumber(STORAGE_KEYS.rightPanelSize, 32));

  const setLeft = useCallback((collapsed: boolean) => {
    setLeftCollapsed(collapsed);
    window.localStorage.setItem(STORAGE_KEYS.leftCollapsed, String(collapsed));
  }, []);

  const setRight = useCallback((collapsed: boolean) => {
    setRightCollapsed(collapsed);
    window.localStorage.setItem(STORAGE_KEYS.rightCollapsed, String(collapsed));
  }, []);

  const rememberLayout = useCallback((layout: Record<string, number>) => {
    if (layout.left) {
      setLeftPanelSize(layout.left);
      window.localStorage.setItem(STORAGE_KEYS.leftPanelSize, String(layout.left));
    }
    if (layout.right) {
      setRightPanelSize(layout.right);
      window.localStorage.setItem(STORAGE_KEYS.rightPanelSize, String(layout.right));
    }
  }, []);

  return {
    leftCollapsed,
    leftPanelSize,
    rememberLayout,
    rightCollapsed,
    rightPanelSize,
    setLeftCollapsed: setLeft,
    setRightCollapsed: setRight,
  };
}
