// @vitest-environment node
/**
 * Launch-meta regression guard.
 *
 * Locks in the launch-readiness invariants added across the SEO/PWA cycles so
 * a future edit to index.html / public assets can't silently regress them.
 * Reads the real files from disk (no rendering) relative to the frontend root.
 */
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

const root = process.cwd();
const read = (rel) => readFileSync(resolve(root, rel), 'utf-8');

describe('index.html launch meta', () => {
  const html = read('index.html');

  it('declares Korean as the primary language', () => {
    expect(html).toMatch(/<html[^>]*\blang="ko"/);
  });

  it('has a canonical link', () => {
    expect(html).toMatch(/<link[^>]*rel="canonical"[^>]*href="https:\/\/decentbio\.xyz\/"/);
  });

  it('has Open Graph image + Twitter summary_large_image', () => {
    expect(html).toMatch(/property="og:image"[^>]*content="https:\/\/decentbio\.xyz\/og-image\.png"/);
    expect(html).toMatch(/name="twitter:card"[^>]*content="summary_large_image"/);
  });

  it('links favicon, apple-touch-icon, and the manifest', () => {
    expect(html).toMatch(/rel="icon"[^>]*href="\/favicon\.svg"/);
    expect(html).toMatch(/rel="apple-touch-icon"[^>]*href="\/apple-touch-icon\.png"/);
    expect(html).toMatch(/rel="manifest"[^>]*href="\/site\.webmanifest"/);
    expect(html).not.toMatch(/href="\/vite\.svg"/);
  });

  it('embeds valid JSON-LD with Organization + SoftwareApplication and pricing offers', () => {
    const m = html.match(/<script type="application\/ld\+json">([\s\S]*?)<\/script>/);
    expect(m).toBeTruthy();
    const data = JSON.parse(m[1]);
    const types = data['@graph'].map((n) => n['@type']);
    expect(types).toContain('Organization');
    expect(types).toContain('SoftwareApplication');
    const software = data['@graph'].find((n) => n['@type'] === 'SoftwareApplication');
    const prices = software.offers.map((o) => o.price).sort();
    expect(prices).toEqual(['0', '199', '29']);
  });
});

describe('PWA manifest', () => {
  it('is valid JSON with brand theme and maskable icons', () => {
    const m = JSON.parse(read('public/site.webmanifest'));
    expect(m.short_name).toBe('DecentBio');
    expect(m.display).toBe('standalone');
    expect(m.theme_color).toBe('#040811');
    const sizes = m.icons.map((i) => i.sizes);
    expect(sizes).toContain('192x192');
    expect(sizes).toContain('512x512');
    expect(m.icons.some((i) => /maskable/.test(i.purpose || ''))).toBe(true);
  });
});

describe('crawler files', () => {
  it('robots.txt points at the sitemap and disallows the app routes', () => {
    const robots = read('public/robots.txt');
    expect(robots).toMatch(/Sitemap:\s*https:\/\/decentbio\.xyz\/sitemap\.xml/);
    expect(robots).toMatch(/Disallow:\s*\/dashboard/);
  });

  it('sitemap.xml lists the public routes only', () => {
    const xml = read('public/sitemap.xml');
    for (const loc of ['/', '/pricing', '/explore', '/investors']) {
      expect(xml).toContain(`https://decentbio.xyz${loc === '/' ? '/' : loc}`);
    }
    expect(xml).not.toMatch(/decentbio\.xyz\/(dashboard|wallet|login)/);
  });
});
