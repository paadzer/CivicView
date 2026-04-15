/// <reference types="vitest/config" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
  },
  test: {
    environment: "jsdom",
    setupFiles: "./src/test/setupTests.js",
    include: ["src/**/*.test.{js,jsx}"],
    clearMocks: true,
  },
});


