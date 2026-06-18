import { renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { useDocumentMeta } from './useDocumentMeta';

function setBaseline() {
  // Set head contents first: assigning innerHTML replaces any <title> jsdom
  // auto-creates for document.title, so the title must be set afterwards.
  document.head.innerHTML = `
    <meta name="description" content="home description" />
    <meta property="og:title" content="Home OG" />
    <meta property="og:description" content="home og desc" />
    <meta name="twitter:title" content="Home TW" />
    <meta name="twitter:description" content="home tw desc" />
    <link rel="canonical" href="https://decentbio.xyz/" />
  `;
  document.title = 'Home Title';
}

const content = (sel) => document.querySelector(sel)?.getAttribute('content');
const href = (sel) => document.querySelector(sel)?.getAttribute('href');

describe('useDocumentMeta', () => {
  beforeEach(setBaseline);
  afterEach(() => {
    document.head.innerHTML = '';
  });

  it('sets title and propagates to description/og/twitter', () => {
    renderHook(() =>
      useDocumentMeta({ title: 'Pricing — DecentBio', description: 'plans and prices' }),
    );

    expect(document.title).toBe('Pricing — DecentBio');
    expect(content('meta[name="description"]')).toBe('plans and prices');
    expect(content('meta[property="og:title"]')).toBe('Pricing — DecentBio');
    expect(content('meta[property="og:description"]')).toBe('plans and prices');
    expect(content('meta[name="twitter:title"]')).toBe('Pricing — DecentBio');
    expect(content('meta[name="twitter:description"]')).toBe('plans and prices');
  });

  it('sets a canonical from a path', () => {
    renderHook(() => useDocumentMeta({ title: 'X', canonicalPath: '/pricing' }));
    expect(href('link[rel="canonical"]')).toBe('https://decentbio.xyz/pricing');
  });

  it('restores baseline meta on unmount', () => {
    const { unmount } = renderHook(() =>
      useDocumentMeta({ title: 'Pricing', description: 'plans', canonicalPath: '/pricing' }),
    );
    expect(document.title).toBe('Pricing');

    unmount();

    expect(document.title).toBe('Home Title');
    expect(content('meta[name="description"]')).toBe('home description');
    expect(content('meta[property="og:title"]')).toBe('Home OG');
    expect(content('meta[name="twitter:description"]')).toBe('home tw desc');
    expect(href('link[rel="canonical"]')).toBe('https://decentbio.xyz/');
  });

  it('creates a missing meta tag instead of throwing', () => {
    document.head.innerHTML = '';
    renderHook(() => useDocumentMeta({ title: 'Solo', description: 'fresh' }));
    expect(content('meta[name="description"]')).toBe('fresh');
    expect(content('meta[property="og:title"]')).toBe('Solo');
  });
});
