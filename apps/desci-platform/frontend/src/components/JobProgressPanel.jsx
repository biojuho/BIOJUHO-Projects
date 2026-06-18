import { Activity } from 'lucide-react';

export default function JobProgressPanel({ job, title, icon = true }) {
    const progress = Math.max(0, Math.min(100, job?.progress ?? 0));

    return (
        <div className="glass-card p-5">
            <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
                <div className="flex min-w-0 items-start gap-3">
                    {icon && (
                        <span className="rounded-full bg-primary/15 p-2 text-primary">
                            <Activity className="h-4 w-4" />
                        </span>
                    )}
                    <div className="min-w-0">
                        <p className="text-xs font-bold uppercase tracking-[0.16em] text-primary">{title}</p>
                        <p className="mt-1 text-sm font-semibold text-ink">{job?.message}</p>
                    </div>
                </div>
                <span className="shrink-0 rounded-full bg-white/70 px-3 py-1 text-sm font-bold text-ink">
                    {progress}%
                </span>
            </div>
            <div className="mt-4 h-2 overflow-hidden rounded-full bg-white/70">
                <div
                    className="h-full rounded-full bg-primary transition-all duration-500"
                    style={{ width: `${progress}%` }}
                />
            </div>
            <div className="mt-3 flex flex-wrap gap-2 text-xs font-semibold text-ink-muted">
                <span className="rounded-full bg-white/65 px-3 py-1">{job?.status}</span>
                {job?.type && <span className="rounded-full bg-white/65 px-3 py-1">{job.type}</span>}
                <span className="rounded-full bg-white/65 px-3 py-1">
                    {job?.storage === 'redis' ? 'Redis synced' : 'Local task'}
                </span>
            </div>
        </div>
    );
}
