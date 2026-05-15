import { buildAcpUiEmbedUrl } from "./acpUiEmbedUrl";

interface AcpUiEmbedProps {
  acpUiUrl: string;
  apiBase: string;
  sessionId: string | null;
  taskId: string | null;
}

export function AcpUiEmbed({
  acpUiUrl,
  apiBase,
  sessionId,
  taskId,
}: AcpUiEmbedProps) {
  const src = buildAcpUiEmbedUrl({ acpUiUrl, apiBase, sessionId, taskId });
  if (!src) return null;

  return (
    <section className="acp-ui-embed" aria-label="ACP interaction client">
      <iframe
        title="ACP interaction client"
        className="acp-ui-embed__frame"
        src={src}
        allow="clipboard-read; clipboard-write"
      />
    </section>
  );
}
