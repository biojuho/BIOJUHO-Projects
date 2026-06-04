import { defineConfig, type Plugin } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';
import { readFileSync, writeFileSync } from 'fs';
import { isAbsolute, resolve } from 'path';
import { fileURLToPath } from 'url';

const __dirname = fileURLToPath(new URL('.', import.meta.url));

function normalizeGeneratedHtmlLineEndings(): Plugin {
  return {
    name: 'normalize-generated-html-line-endings',
    generateBundle(_options, bundle) {
      for (const asset of Object.values(bundle)) {
        if (
          asset.type === 'asset' &&
          asset.fileName.endsWith('.html') &&
          typeof asset.source === 'string'
        ) {
          asset.source = asset.source.replace(/\r\n?/g, '\n');
        }
      }
    },
    writeBundle(options, bundle) {
      const outDir = options.dir
        ? isAbsolute(options.dir)
          ? options.dir
          : resolve(__dirname, options.dir)
        : resolve(__dirname, 'assets');

      for (const asset of Object.values(bundle)) {
        if (!asset.fileName.endsWith('.html')) {
          continue;
        }

        const assetPath = resolve(outDir, asset.fileName);
        const html = readFileSync(assetPath, 'utf8');
        const normalizedHtml = html.replace(/\r\n?/g, '\n');
        if (normalizedHtml !== html) {
          writeFileSync(assetPath, normalizedHtml, 'utf8');
        }
      }
    },
  };
}

export default defineConfig({
  plugins: [react(), tailwindcss(), normalizeGeneratedHtmlLineEndings()],
  root: './',
  build: {
    outDir: 'assets',
    emptyOutDir: true,
    rollupOptions: {
      input: {
        'canva-design-editor': resolve(__dirname, 'src/components/canva-design-editor.html'),
        'canva-design-generator': resolve(__dirname, 'src/components/canva-design-generator.html'),
        'canva-search-designs': resolve(__dirname, 'src/components/canva-search-designs.html'),
        'preview': resolve(__dirname, 'src/dev/preview.html'),
      },
      output: {
        entryFileNames: '[name].js',
        chunkFileNames: '[name]-[hash].js',
        assetFileNames: (assetInfo) => {
          if (assetInfo.name?.endsWith('.html')) {
            return '[name][extname]';
          }
          return '[name]-[hash][extname]';
        }
      }
    }
  },
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src')
    }
  },
  server: {
    port: 5173,
    open: '/src/dev/preview.html',
  }
});
