// @lovable.dev/vite-tanstack-config already includes TanStack + React + Tailwind plugins.
// Pass extra Vite options via `vite: { ... }` only.
import path from "node:path";
import { fileURLToPath } from "node:url";
import { defineConfig } from "@lovable.dev/vite-tanstack-config";

const rootDir = path.dirname(fileURLToPath(import.meta.url));

export default defineConfig({
  tanstackStart: {
    server: { entry: "server" },
  },
  vite: {
    server: {
      host: "127.0.0.1",
      port: 5174,
      strictPort: true,
      proxy: {
        "/api": {
          target: "http://127.0.0.1:8000",
          changeOrigin: true,
        },
        "/ws": {
          target: "ws://127.0.0.1:8000",
          ws: true,
          changeOrigin: true,
        },
      },
    },
    resolve: {
      alias: {
        "@": path.resolve(rootDir, "src"),
        "@care-plus/api-client": path.resolve(rootDir, "../../packages/api-client/src/index.ts"),
        "@care-plus/serah-live": path.resolve(rootDir, "../../packages/serah-live/src/index.ts"),
      },
      dedupe: ["zod"],
    },
    optimizeDeps: {
      exclude: ["@care-plus/api-client", "@care-plus/serah-live"],
      include: ["zod"],
    },
  },
});
