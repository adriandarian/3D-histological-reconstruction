import { defineConfig } from 'vite';

// Development serves local pipeline outputs. Production installs the published demos.
export default defineConfig({ build: { copyPublicDir: false } });
