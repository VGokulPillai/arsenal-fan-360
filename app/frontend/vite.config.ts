import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [
    react(),
    {
      name: "html-build-stamp",
      transformIndexHtml(html) {
        const stamp = new Date().toISOString();
        return html.replace(
          "</head>",
          `  <meta name="build-stamp" content="${stamp}" />\n  </head>`
        );
      },
    },
  ],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
});
