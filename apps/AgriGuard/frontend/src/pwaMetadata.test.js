/* @vitest-environment node */
/* global describe, it, expect */
import { readFileSync } from 'node:fs';

const replacementCharacter = String.fromCharCode(0xfffd);

function readText(path) {
  return readFileSync(new URL(path, import.meta.url), 'utf8');
}

function readManifest() {
  return JSON.parse(readText('../public/manifest.json'));
}

function hasIcon(manifest, size) {
  return manifest.icons.some(
    (icon) =>
      icon.src.startsWith('/icons/') &&
      icon.sizes.split(/\s+/).includes(size) &&
      icon.type === 'image/png' &&
      icon.purpose.split(/\s+/).includes('maskable'),
  );
}

describe('PWA metadata policy', () => {
  it('keeps app identity, scope, and install presentation explicit', () => {
    const manifest = readManifest();
    const html = readText('../index.html');

    expect(manifest.id).toBe('/');
    expect(manifest.scope).toBe('/');
    expect(manifest.start_url).toBe('/');
    expect(manifest.name).toBe('AgriGuard');
    expect(manifest.short_name).toBe('AgriGuard');
    expect(manifest.short_name.length).toBeLessThanOrEqual(12);
    expect(manifest.display).toBe('standalone');
    expect(manifest.theme_color).toBe('#4ade80');
    expect(manifest.background_color).toBe('#0b1120');
    expect(hasIcon(manifest, '192x192')).toBe(true);
    expect(hasIcon(manifest, '512x512')).toBe(true);

    expect(html).toContain('<html lang="ko">');
    expect(html).toContain('<link rel="manifest" href="/manifest.json" />');
    expect(html).toContain('<meta name="theme-color" content="#4ade80" />');
    expect(html).not.toContain(replacementCharacter);
    expect(JSON.stringify(manifest)).not.toContain(replacementCharacter);
  });

  it('exposes installed-app shortcuts only for in-scope public workflows', () => {
    const manifest = readManifest();
    const appSource = readText('./App.jsx');

    expect(manifest.shortcuts).toHaveLength(2);
    expect(manifest.shortcuts.map((shortcut) => shortcut.url)).toEqual(['/scan', '/supply-chain']);

    for (const shortcut of manifest.shortcuts) {
      expect(shortcut.name).toEqual(expect.any(String));
      expect(shortcut.short_name).toEqual(expect.any(String));
      expect(shortcut.short_name.length).toBeLessThanOrEqual(12);
      expect(shortcut.description).toEqual(expect.any(String));
      expect(shortcut.url.startsWith('/')).toBe(true);
      expect(shortcut.url.includes('?')).toBe(false);
      expect(shortcut.url.includes('#')).toBe(false);
      expect(shortcut.icons).toEqual([
        {
          src: '/icons/icon-192.png',
          sizes: '192x192',
          type: 'image/png',
        },
      ]);

      const routePath = shortcut.url.slice(1);
      expect(appSource).toContain(`path="${routePath}"`);
    }
  });
});
