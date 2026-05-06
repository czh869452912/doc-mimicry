import { DiffViewer } from "../DiffViewer";

interface DiffTabProps {
  left: string;
  leftTitle: string;
  right: string;
  rightTitle: string;
}

export function DiffTab({ left, leftTitle, right, rightTitle }: DiffTabProps) {
  return <DiffViewer left={left} leftTitle={leftTitle} right={right} rightTitle={rightTitle} />;
}
