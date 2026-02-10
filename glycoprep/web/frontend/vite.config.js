import { defineConfig } from 'vite';
import { svelte } from '@sveltejs/vite-plugin-svelte';

export default defineConfig({
  plugins: [svelte()],
  base: '/glycoprep/',
  server: {
    proxy: {
      '/glycoprep/api': {
        target: 'http://localhost:8000',
        rewrite: (path) => path.replace(/^\/glycoprep/, ''),
      },
      '/glycoprep/ws': {
        target: 'ws://localhost:8000',
        ws: true,
        rewrite: (path) => path.replace(/^\/glycoprep/, ''),
      },
    },
  },
});
