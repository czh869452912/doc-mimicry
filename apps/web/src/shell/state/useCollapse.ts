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

export interface PanelLayout {
  left: number;
  center: number;
  right: number;
}

export function clampPanelSize(value: number, fallback: number, min: number, max: number) {
  if (!Number.isFinite(value)) return fallback;
  return Math.min(Math.max(value, min), max);
}

export function normalizePanelLayout(leftValue: number, rightValue: number): PanelLayout {
  const left = clampPanelSize(leftValue, 20, 12, 40);
  const right = clampPanelSize(rightValue, 32, 18, 48);
  const maxSideTotal = 82;
  const sideTotal = left + right;
  if (sideTotal <= maxSideTotal) {
    return { left, center: 100 - sideTotal, right };
  }
  const scale = maxSideTotal / sideTotal;
  const scaledLeft = Math.round(left * scale);
  const scaledRight = maxSideTotal - scaledLeft;
  return { left: scaledLeft, center: 18, right: scaledRight };
}

export function useCollapse() {
  const [leftCollapsed, setLeftCollapsed] = useState(() => readBoolean(STORAGE_KEYS.leftCollapsed, false));
  const [rightCollapsed, setRightCollapsed] = useState(() => readBoolean(STORAGE_KEYS.rightCollapsed, false));
  const [leftPanelSize, setLeftPanelSize] = useState(
    () =>
      normalizePanelLayout(
        readNumber(STORAGE_KEYS.leftPanelSize, 20),
        readNumber(STORAGE_KEYS.rightPanelSize, 32),
      ).left,
  );
  const [rightPanelSize, setRightPanelSize] = useState(
    () =>
      normalizePanelLayout(
        readNumber(STORAGE_KEYS.leftPanelSize, 20),
        readNumber(STORAGE_KEYS.rightPanelSize, 32),
      ).right,
  );

  const setLeft = useCallback((collapsed: boolean) => {
    setLeftCollapsed(collapsed);
    window.localStorage.setItem(STORAGE_KEYS.leftCollapsed, String(collapsed));
  }, []);

  const setRight = useCallback((collapsed: boolean) => {
    setRightCollapsed(collapsed);
    window.localStorage.setItem(STORAGE_KEYS.rightCollapsed, String(collapsed));
  }, []);

  const rememberLayout = useCallback(
    (layout: Record<string, number>) => {
      const normalized = normalizePanelLayout(layout.left ?? leftPanelSize, layout.right ?? rightPanelSize);
      setLeftPanelSize(normalized.left);
      setRightPanelSize(normalized.right);
      window.localStorage.setItem(STORAGE_KEYS.leftPanelSize, String(normalized.left));
      window.localStorage.setItem(STORAGE_KEYS.rightPanelSize, String(normalized.right));
    },
    [leftPanelSize, rightPanelSize],
  );

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
