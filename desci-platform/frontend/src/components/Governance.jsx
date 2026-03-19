import { useEffect, useMemo, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Plus, Scale, Vote } from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';
import { useToast } from '../contexts/ToastContext';
import { useLocale } from '../contexts/LocaleContext';
import api from '../services/api';
import { Badge } from './ui/Badge';
import { Button } from './ui/Button';
import GlassCard from './ui/GlassCard';
import { Input } from './ui/Input';

export default function Governance() {
  const [proposals, setProposals] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [newTitle, setNewTitle] = useState('');
  const [newDesc, setNewDesc] = useState('');
  const { walletAddress } = useAuth();
  const { showToast } = useToast();
  const { t } = useLocale();

  const stateLabels = useMemo(() => ({
    0: { text: t('governance.statePending'), variant: 'warning' },
    1: { text: t('governance.stateActive'), variant: 'info' },
    2: { text: t('governance.statePassed'), variant: 'success' },
    3: { text: t('governance.stateRejected'), variant: 'error' },
    4: { text: t('governance.stateExecuted'), variant: 'accent' },
  }), [t]);

  useEffect(() => {
    loadProposals();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const loadProposals = async () => {
    try {
      const response = await api.get('/governance/proposals');
      setProposals(response.data);
    } catch (_err) {
      showToast(t('governance.loadFailed'), 'error');
    } finally {
      setLoading(false);
    }
  };

  const handleCreate = async () => {
    if (!newTitle.trim() || !newDesc.trim()) {
      showToast(t('governance.validation'), 'warning');
      return;
    }

    try {
      await api.post('/governance/proposals', {
        title: newTitle,
        description: newDesc,
        proposer: walletAddress,
      });
      showToast(t('governance.createSuccess'), 'success');
      setNewTitle('');
      setNewDesc('');
      setShowCreate(false);
      loadProposals();
    } catch (err) {
      showToast(err.response?.data?.detail || t('governance.createFailed'), 'error');
    }
  };

  const handleVote = async (proposalId, support) => {
    try {
      await api.post(`/governance/proposals/${proposalId}/vote`, { voter: walletAddress, support });
      showToast(t(support ? 'governance.voteSuccessFor' : 'governance.voteSuccessAgainst'), 'success');
      loadProposals();
    } catch (err) {
      showToast(err.response?.data?.detail || t('governance.voteFailed'), 'error');
    }
  };

  if (loading) {
    return (
      <div className="space-y-4">
        {[1, 2, 3].map((index) => (
          <div key={index} className="glass-card h-28 animate-pulse" />
        ))}
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <GlassCard className="p-7">
        <div className="flex flex-col gap-5 md:flex-row md:items-end md:justify-between">
          <div>
            <p className="clay-chip mb-4">{t('layout.trust')}</p>
            <h1 className="font-display text-4xl font-semibold text-ink">{t('governance.title')}</h1>
            <p className="mt-3 text-sm leading-7 text-ink-muted">{t('governance.subtitle')}</p>
          </div>
          <Button variant="outline" onClick={() => setShowCreate((value) => !value)}>
            <Plus className="h-4 w-4" />
            {t('governance.newProposal')}
          </Button>
        </div>
      </GlassCard>

      <AnimatePresence>
        {showCreate && (
          <motion.div initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }}>
            <GlassCard className="p-6">
              <h2 className="mb-4 font-display text-2xl font-semibold text-ink">{t('governance.createTitle')}</h2>
              <div className="space-y-3">
                <Input value={newTitle} onChange={(event) => setNewTitle(event.target.value)} placeholder={t('governance.proposalTitle')} />
                <textarea value={newDesc} onChange={(event) => setNewDesc(event.target.value)} placeholder={t('governance.proposalDescription')} rows={5} className="clay-input resize-none" />
                <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
                  <p className="text-sm text-ink-muted">{t('governance.requiresTokens')}</p>
                  <Button onClick={handleCreate} className="justify-center text-white">{t('governance.submitProposal')}</Button>
                </div>
              </div>
            </GlassCard>
          </motion.div>
        )}
      </AnimatePresence>

      <div className="space-y-4">
        {proposals.length === 0 ? (
          <GlassCard className="p-10 text-center">
            <div className="mx-auto mb-6 flex h-20 w-20 items-center justify-center rounded-full bg-white text-primary shadow-clay-soft">
              <Vote className="h-10 w-10" />
            </div>
            <h3 className="font-display text-3xl font-semibold text-ink">{t('governance.noProposals')}</h3>
            <p className="mt-3 text-sm text-ink-muted">{t('governance.noProposalsHint')}</p>
          </GlassCard>
        ) : (
          proposals.map((proposal, index) => {
            const state = stateLabels[proposal.state] || stateLabels[0];
            const totalVotes = (proposal.for_votes || 0) + (proposal.against_votes || 0);
            const forPct = totalVotes > 0 ? ((proposal.for_votes || 0) / totalVotes) * 100 : 0;

            return (
              <motion.div key={proposal.id} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: index * 0.06 }}>
                <GlassCard className="p-6">
                  <div className="mb-4 flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
                    <div className="flex-1">
                      <div className="mb-3 flex items-center gap-3">
                        <div className="flex h-12 w-12 items-center justify-center rounded-full bg-white text-primary shadow-clay-soft">
                          <Scale className="h-5 w-5" />
                        </div>
                        <Badge variant={state.variant}>{state.text}</Badge>
                      </div>
                      <h3 className="font-display text-2xl font-semibold text-ink">{proposal.title}</h3>
                      <p className="mt-3 text-sm leading-7 text-ink-muted">{proposal.description}</p>
                    </div>
                  </div>

                  <div className="clay-panel-pressed rounded-[1.6rem] p-4">
                    <div className="mb-2 flex justify-between text-sm text-ink-muted">
                      <span>{t('governance.votesFor')}: {proposal.for_votes || 0}</span>
                      <span>{t('governance.votesAgainst')}: {proposal.against_votes || 0}</span>
                    </div>
                    <div className="h-2 overflow-hidden rounded-full bg-white/70">
                      <div className="h-full rounded-full bg-gradient-to-r from-primary to-accent" style={{ width: `${forPct}%` }} />
                    </div>
                  </div>

                  <div className="mt-4 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
                    <span className="text-sm text-ink-muted">{t('governance.endDate')}: {new Date(proposal.end_time).toLocaleDateString()}</span>
                    {proposal.state === 1 && (
                      <div className="flex gap-2">
                        <Button variant="success" size="sm" onClick={() => handleVote(proposal.id, true)}>{t('governance.voteFor')}</Button>
                        <Button variant="destructive" size="sm" onClick={() => handleVote(proposal.id, false)}>{t('governance.voteAgainst')}</Button>
                      </div>
                    )}
                  </div>
                </GlassCard>
              </motion.div>
            );
          })
        )}
      </div>
    </div>
  );
}
