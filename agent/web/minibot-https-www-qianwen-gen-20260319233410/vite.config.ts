import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

/** 开发时把 /api 转到 FastAPI（8000），避免前端写死错端口 */
export default defineConfig({
  plugins: [react()],
  server: {
    host: "127.0.0.1",
    port: 3000,
    strictPort: true,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
});
