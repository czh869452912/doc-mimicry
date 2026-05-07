import { fileURLToPath, URL } from "node:url";
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes("node_modules")) return;
          if (id.includes("react/") || id.includes("react-dom/")) return "vendor-react";
          if (id.includes("@uiw/react-codemirror")) return "vendor-editor-react";
          if (id.includes("@codemirror/view") || id.includes("@codemirror/state")) return "vendor-editor-core";
          if (id.includes("@codemirror") || id.includes("@lezer") || id.includes("codemirror")) {
            return "vendor-editor-language";
          }
          if (
            id.includes("react-markdown") ||
            id.includes("remark-") ||
            id.includes("rehype-") ||
            id.includes("unified") ||
            id.includes("micromark") ||
            id.includes("mdast") ||
            id.includes("hast") ||
            id.includes("unist") ||
            id.includes("vfile")
          ) {
            return "vendor-markdown";
          }
          if (id.includes("@assistant-ui")) return "vendor-assistant-ui";
          if (id.includes("@radix-ui") || id.includes("cmdk") || id.includes("lucide-react")) {
            return "vendor-ui";
          }
          if (id.includes("diff")) return "vendor-diff";
        },
      },
    },
  },
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
});
