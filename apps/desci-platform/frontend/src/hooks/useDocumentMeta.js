import { useEffect } from 'react';

/**
 * Per-route document metadata for the SPA.
 *
 * The static index.html only carries the home-page title/description, so every
 * route otherwise shows the same browser-tab title and the same meta that gets
 * scraped for deep-link social shares. This hook sets the document title, the
 * meta description, the Open Graph / Twitter title+description, and the
 * canonical URL for the current route, then restores the original index.html
 * values when the component unmounts so non-metered routes stay on the default.
 *
 * No external dependency (intentionally avoids react-helmet) to keep the
 * bundle and dependency surface unchanged.
 *
 * @param {object} meta
 * @param {string} meta.title - Full document title for the route.
 * @param {string} [meta.description] - Meta description (also OG/Twitter).
 * @param {string} [meta.canonicalPath] - Path (e.g. "/pricing") for canonical.
 */
export function useDocumentMeta({ title, description, canonicalPath } = {}) {
  useEffect(() => {
    if (typeof document === 'undefined') return undefined;

    const previous = {
      title: document.title,
      description: readMeta('name', 'description'),
      ogTitle: readMeta('property', 'og:title'),
      ogDescription: readMeta('property', 'og:description'),
      twitterTitle: readMeta('name', 'twitter:title'),
      twitterDescription: readMeta('name', 'twitter:description'),
      canonical: readCanonical(),
    };

    if (title) {
      document.title = title;
      writeMeta('property', 'og:title', title);
      writeMeta('name', 'twitter:title', title);
    }
    if (description) {
      writeMeta('name', 'description', description);
      writeMeta('property', 'og:description', description);
      writeMeta('name', 'twitter:description', description);
    }
    if (canonicalPath) {
      writeCanonical(canonicalPath);
    }

    return () => {
      document.title = previous.title;
      restoreMeta('name', 'description', previous.description);
      restoreMeta('property', 'og:title', previous.ogTitle);
      restoreMeta('property', 'og:description', previous.ogDescription);
      restoreMeta('name', 'twitter:title', previous.twitterTitle);
      restoreMeta('name', 'twitter:description', previous.twitterDescription);
      if (previous.canonical != null) writeCanonical(previous.canonical, true);
    };
  }, [title, description, canonicalPath]);
}

function readMeta(attr, value) {
  const el = document.querySelector(`meta[${attr}="${value}"]`);
  return el ? el.getAttribute('content') : null;
}

function writeMeta(attr, value, content) {
  let el = document.querySelector(`meta[${attr}="${value}"]`);
  if (!el) {
    el = document.createElement('meta');
    el.setAttribute(attr, value);
    document.head.appendChild(el);
  }
  el.setAttribute('content', content);
}

function restoreMeta(attr, value, content) {
  if (content == null) return;
  writeMeta(attr, value, content);
}

const ORIGIN = 'https://decentbio.xyz';

function readCanonical() {
  const el = document.querySelector('link[rel="canonical"]');
  return el ? el.getAttribute('href') : null;
}

function writeCanonical(pathOrHref, isHref = false) {
  let el = document.querySelector('link[rel="canonical"]');
  if (!el) {
    el = document.createElement('link');
    el.setAttribute('rel', 'canonical');
    document.head.appendChild(el);
  }
  const href = isHref
    ? pathOrHref
    : `${ORIGIN}${pathOrHref.startsWith('/') ? '' : '/'}${pathOrHref}`;
  el.setAttribute('href', href);
}

export default useDocumentMeta;
