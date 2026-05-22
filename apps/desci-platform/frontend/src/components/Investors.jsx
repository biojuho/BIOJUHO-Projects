import { useEffect, useMemo, useState } from 'react';
import { Building2, Globe2, Mail, Search } from 'lucide-react';
import client from '../services/api';
import GlassCard from './ui/GlassCard';
import { SkeletonList } from './ui/Skeleton';

const STAGE_OPTIONS = [
  '',
  'Seed',
  'Pre-Series A',
  'Series A',
  'Series B',
  'Series C',
  'Growth',
  'Pre-IPO',
  'Strategic',
];

const COUNTRY_OPTIONS = [
  { value: '', label: 'All countries' },
  { value: 'KR', label: 'Korea' },
  { value: 'US', label: 'United States' },
  { value: 'FR', label: 'France' },
];

function InvestorCard({ vc }) {
  return (
    <GlassCard className="p-6" hoverEffect>
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0 flex-1">
          <div className="mb-3 flex flex-wrap items-center gap-2">
            <span className="rounded-full bg-primary/15 px-3 py-1 text-xs font-bold uppercase tracking-[0.16em] text-primary">
              {vc.country}
            </span>
            {vc.preferred_stages?.slice(0, 3).map((stage) => (
              <span
                key={stage}
                className="rounded-full bg-white/70 px-3 py-1 text-xs font-semibold text-ink-muted"
              >
                {stage}
              </span>
            ))}
          </div>
          <h3 className="font-display text-2xl font-semibold text-ink">{vc.name}</h3>
          <p className="mt-3 text-sm leading-6 text-ink-muted">{vc.investment_thesis}</p>
          {vc.portfolio_keywords?.length > 0 && (
            <div className="mt-4 flex flex-wrap gap-2">
              {vc.portfolio_keywords.slice(0, 6).map((kw) => (
                <span
                  key={kw}
                  className="rounded-full border border-surface-line/60 bg-surface/70 px-3 py-1 text-xs font-medium text-ink-muted"
                >
                  {kw}
                </span>
              ))}
            </div>
          )}
        </div>
        <div className="flex w-full flex-shrink-0 flex-col gap-2 text-sm text-ink-muted lg:w-56">
          {vc.website && (
            <a
              href={vc.website}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-2 text-primary hover:underline"
            >
              <Globe2 className="h-4 w-4" />
              <span className="truncate">{vc.website.replace(/^https?:\/\//, '')}</span>
            </a>
          )}
          {vc.contact_email && (
            <a
              href={`mailto:${vc.contact_email}`}
              className="inline-flex items-center gap-2 text-ink hover:text-primary"
            >
              <Mail className="h-4 w-4" />
              <span className="truncate">{vc.contact_email}</span>
            </a>
          )}
          <span className="mt-2 text-xs text-ink-soft">{vc.id}</span>
        </div>
      </div>
    </GlassCard>
  );
}

export default function Investors() {
  const [allVcs, setAllVcs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [country, setCountry] = useState('');
  const [stage, setStage] = useState('');
  const [keyword, setKeyword] = useState('');

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      try {
        const response = await client.get('/vcs', { params: { limit: 500 } });
        if (!cancelled) {
          setAllVcs(Array.isArray(response.data) ? response.data : []);
          setError(null);
        }
      } catch (err) {
        if (!cancelled) {
          console.error('Failed to fetch VCs:', err);
          setError('Could not load investor directory.');
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const filtered = useMemo(() => {
    const term = keyword.trim().toLowerCase();
    return allVcs.filter((vc) => {
      if (country && vc.country !== country) return false;
      if (stage && !(vc.preferred_stages || []).some((s) => s.toLowerCase() === stage.toLowerCase())) {
        return false;
      }
      if (term) {
        const hay = `${vc.name} ${vc.investment_thesis || ''} ${(vc.portfolio_keywords || []).join(' ')}`.toLowerCase();
        if (!hay.includes(term)) return false;
      }
      return true;
    });
  }, [allVcs, country, stage, keyword]);

  return (
    <div className="mx-auto max-w-7xl space-y-6 px-4 py-8 lg:px-8">
      <GlassCard className="p-7">
        <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="clay-chip mb-4 inline-flex items-center gap-2">
              <Building2 className="h-4 w-4" /> Investor directory
            </p>
            <h1 className="font-display text-4xl font-semibold text-ink">
              Bio <span className="text-gradient">VC ecosystem</span>
            </h1>
            <p className="mt-3 max-w-3xl text-sm leading-7 text-ink-muted">
              Browse {allVcs.length || '50+'} curated Korean and global biotech investors. Filter by
              country, stage, or keyword to find the right partner for your research.
            </p>
          </div>
        </div>
      </GlassCard>

      <GlassCard className="p-5">
        <div className="grid gap-3 lg:grid-cols-[1fr,180px,180px]">
          <div className="relative">
            <Search className="absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-soft" />
            <input
              type="text"
              placeholder="Search name, thesis, or keyword"
              value={keyword}
              onChange={(e) => setKeyword(e.target.value)}
              className="clay-input pl-11"
            />
          </div>
          <select
            value={country}
            onChange={(e) => setCountry(e.target.value)}
            className="clay-input"
            aria-label="Filter by country"
          >
            {COUNTRY_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
          <select
            value={stage}
            onChange={(e) => setStage(e.target.value)}
            className="clay-input"
            aria-label="Filter by preferred stage"
          >
            <option value="">All stages</option>
            {STAGE_OPTIONS.filter(Boolean).map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </div>
      </GlassCard>

      {error && (
        <GlassCard className="p-6 text-center">
          <p className="font-semibold text-error-dark">{error}</p>
        </GlassCard>
      )}

      <p className="text-sm text-ink-muted">
        Showing {filtered.length} of {allVcs.length} investors
      </p>

      {loading ? (
        <SkeletonList count={5} />
      ) : filtered.length === 0 ? (
        <GlassCard className="p-10 text-center">
          <p className="font-semibold text-ink">No investors match your filters</p>
          <p className="mt-2 text-sm text-ink-muted">
            Try clearing a filter or broadening the keyword search.
          </p>
        </GlassCard>
      ) : (
        <div className="space-y-4">
          {filtered.map((vc) => (
            <InvestorCard key={vc.id} vc={vc} />
          ))}
        </div>
      )}
    </div>
  );
}
