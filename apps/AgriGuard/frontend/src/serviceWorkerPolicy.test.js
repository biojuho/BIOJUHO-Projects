/* @vitest-environment node */
/* global describe, it, expect, vi */
import { readFileSync } from 'node:fs';
import vm from 'node:vm';

function loadServiceWorkerPolicy() {
  const source = readFileSync(new URL('../public/sw.js', import.meta.url), 'utf8');
  const context = {
    URL,
    Promise,
    caches: {},
    fetch: vi.fn(),
    self: {
      location: { origin: 'https://agriguard.example' },
      addEventListener: vi.fn(),
      skipWaiting: vi.fn(),
      clients: { claim: vi.fn() },
    },
  };

  vm.createContext(context);
  vm.runInContext(
    `${source}\n` +
      'globalThis.__policy = { CACHE_NAME, isAppShellRequest, isCacheableStaticRequest };',
    context,
  );
  return context.__policy;
}

function readText(path) {
  return readFileSync(new URL(path, import.meta.url), 'utf8');
}

describe('service worker cache policy', () => {
  it('serves the app shell through the network-first branch', () => {
    const policy = loadServiceWorkerPolicy();

    expect(policy.CACHE_NAME).toBe('agriguard-v4');
    expect(policy.isAppShellRequest(new URL('https://agriguard.example/'))).toBe(true);
    expect(policy.isAppShellRequest(new URL('https://agriguard.example/index.html'))).toBe(true);
    expect(policy.isAppShellRequest(new URL('https://agriguard.example/assets/Dashboard.js'))).toBe(false);
    expect(policy.isCacheableStaticRequest(new URL('https://agriguard.example/'))).toBe(false);
    expect(policy.isCacheableStaticRequest(new URL('https://agriguard.example/index.html'))).toBe(false);
  });

  it('keeps immutable assets and icons on the cache-first branch', () => {
    const policy = loadServiceWorkerPolicy();

    expect(policy.isCacheableStaticRequest(new URL('https://agriguard.example/assets/Dashboard.js'))).toBe(true);
    expect(policy.isCacheableStaticRequest(new URL('https://agriguard.example/icons/icon-192.png'))).toBe(true);
    expect(policy.isCacheableStaticRequest(new URL('https://agriguard.example/manifest.json'))).toBe(true);
  });

  it('registers service worker updates without consulting the HTTP cache', () => {
    const html = readText('../index.html');

    expect(html).toContain('navigator.serviceWorker.register("/sw.js", { updateViaCache: "none" })');
  });

  it('serves the service worker script with revalidation headers', () => {
    const nginx = readText('../nginx.conf');

    expect(nginx).toContain('location = /sw.js');
    expect(nginx).toContain('try_files /sw.js =404;');
    expect(nginx).toContain('add_header Cache-Control "no-cache" always;');
  });
});
