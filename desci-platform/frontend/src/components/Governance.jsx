import React, { useState, useEffect } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { Vote, Plus, CheckCircle, XCircle, Clock, Zap, Users } from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';
import { useToast } from '../contexts/ToastContext';
import api from '../services/api';
import { Badge } from './ui/Badge';
import { Button } from './ui/Button';
import { Input } from './ui/Input';
import { Card, CardContent } from './ui/Card';

const STATE_LABELS = {
  0: { text: 'Pending', variant: 'warning' },
  1: { text: 'Active', variant: 'info' },
  2: { text: 'Passed', variant: 'success' },
  3: { text: 'Rejected', variant: 'error' },
  4: { text: 'Executed', variant: 'accent' },
};

export default function Governance() {
  const [proposals, setProposals] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [newTitle, setNewTitle] = useState('');
  const [newDesc, setNewDesc] = useState('');
  const { walletAddress } = useAuth();
  const { showToast } = useToast();

  useEffect(() => {
    loadProposals();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);;

  const loadProposals = async () => {
    try {
      const res = await api.get('/governance/proposals');
      setProposals(res.data);
    } catch (_err) {
      showToast('Failed to load proposals', 'error');
    } finally {
      setLoading(false);
    }
  };

  const handleCreate = async () => {
    if (!newTitle.trim() || !newDesc.trim()) {
      showToast('Title and description required', 'warning');
      return;
    }
    try {
      await api.post('/governance/proposals', {
        title: newTitle,
        description: newDesc,
        proposer: walletAddress,
      });
      showToast('Proposal created successfully!', 'success');
      setNewTitle('');
      setNewDesc('');
      setShowCreate(false);
      loadProposals();
    } catch (err) {
      showToast(err.response?.data?.detail || 'Failed to create proposal', 'error');
    }
  };

  const handleVote = async (proposalId, support) => {
    try {
      await api.post(`/governance/proposals/${proposalId}/vote`, {
        voter: walletAddress,
        support,
      });
      showToast(`Vote cast: ${support ? 'For' : 'Against'}`, 'success');
      loadProposals();
    } catch (err) {
      showToast(err.response?.data?.detail || 'Vote failed', 'error');
    }
  };

  if (loading) {
    return (
      <div className="animate-pulse space-y-4 p-8">
        {[1, 2, 3].map((i) => (
          <div key={i} className="h-32 rounded-2xl bg-white/5" />
        ))}
      </div>
    );
  }

  return (
    <div className="p-4 sm:p-8 max-w-4xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-purple-400 to-blue-400">
            DAO Governance
          </h1>
          <p className="text-sm text-gray-400 mt-1">
            DSCI 토큰 기반 탈중앙화 의사결정
          </p>
        </div>
        <Button
          variant="outline"
          onClick={() => setShowCreate(!showCreate)}
          className="border-purple-500/30 text-purple-300 hover:bg-purple-500/10"
        >
          <Plus className="w-4 h-4" />
          New Proposal
        </Button>
      </div>

      {/* Create Form */}
      <AnimatePresence>
        {showCreate && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            className="mb-8 p-6 rounded-2xl border border-purple-500/20 bg-purple-500/5 backdrop-blur-lg"
          >
            <h2 className="text-lg font-semibold text-purple-300 mb-4">Create Proposal</h2>
            <input
              type="text"
              value={newTitle}
              onChange={(e) => setNewTitle(e.target.value)}
              placeholder="Proposal title..."
              className="w-full mb-3 px-4 py-3 rounded-xl bg-white/5 border border-white/10 text-white placeholder-gray-500 focus:outline-none focus:border-purple-500/50"
            />
            <textarea
              value={newDesc}
              onChange={(e) => setNewDesc(e.target.value)}
              placeholder="Describe your proposal in detail..."
              rows={4}
              className="w-full mb-4 px-4 py-3 rounded-xl bg-white/5 border border-white/10 text-white placeholder-gray-500 focus:outline-none focus:border-purple-500/50 resize-none"
            />
            <div className="flex items-center gap-3">
              <Button
                onClick={handleCreate}
                className="bg-purple-600 hover:bg-purple-700 text-white"
              >
                Submit Proposal
              </Button>
              <span className="text-xs text-gray-500">Requires 100+ DSCI tokens</span>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Proposals List */}
      <div className="space-y-4">
        {proposals.length === 0 ? (
          <div className="text-center py-16 text-gray-500">
            <Vote className="w-12 h-12 mx-auto mb-4 opacity-30" />
            <p className="text-lg">No proposals yet</p>
            <p className="text-sm mt-1">Be the first to create a governance proposal!</p>
          </div>
        ) : (
          proposals.map((p, idx) => {
            const state = STATE_LABELS[p.state] || STATE_LABELS[0];
            const totalVotes = (p.for_votes || 0) + (p.against_votes || 0);
            const forPct = totalVotes > 0 ? ((p.for_votes || 0) / totalVotes) * 100 : 0;

            return (
              <motion.div
                key={p.id}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: idx * 0.1 }}
                className="p-6 rounded-2xl border border-white/10 bg-white/5 backdrop-blur-lg hover:border-white/20 transition-all"
              >
                <div className="flex items-start justify-between mb-3">
                  <div>
                    <h3 className="text-lg font-semibold text-white">{p.title}</h3>
                    <p className="text-sm text-gray-400 mt-1 line-clamp-2">{p.description}</p>
                  </div>
                  <Badge variant={state.variant}>
                    {state.text}
                  </Badge>
                </div>

                {/* Vote Bar */}
                <div className="mt-4 mb-3">
                  <div className="flex justify-between text-xs text-gray-400 mb-1">
                    <span className="text-green-400">For: {p.for_votes || 0} DSCI</span>
                    <span className="text-red-400">Against: {p.against_votes || 0} DSCI</span>
                  </div>
                  <div className="h-2 bg-gray-700 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-gradient-to-r from-green-500 to-emerald-400 rounded-full transition-all"
                      style={{ width: `${forPct}%` }}
                    />
                  </div>
                </div>

                {/* Actions */}
                <div className="flex items-center gap-3 mt-4">
                  {p.state === 1 && (
                    <>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleVote(p.id, true)}
                        className="bg-green-500/10 hover:bg-green-500/20 text-green-400 border border-green-500/20"
                      >
                        <CheckCircle className="w-4 h-4" /> For
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleVote(p.id, false)}
                        className="bg-red-500/10 hover:bg-red-500/20 text-red-400 border border-red-500/20"
                      >
                        <XCircle className="w-4 h-4" /> Against
                      </Button>
                    </>
                  )}
                  <div className="flex items-center gap-1 text-xs text-gray-500 ml-auto">
                    <Clock className="w-3 h-3" />
                    {new Date(p.end_time).toLocaleDateString()}
                  </div>
                </div>
              </motion.div>
            );
          })
        )}
      </div>
    </div>
  );
}
