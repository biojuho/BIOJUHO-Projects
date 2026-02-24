import React, { useState } from 'react';
import { Sprout, QrCode, ClipboardCheck, Loader2 } from 'lucide-react';
import { productApi } from '../services/api';

export default function ProductRegistry() {
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(null);
  const [formData, setFormData] = useState({
    name: '',
    category: 'Vegetable',
    description: '',
    location: 'Farm A-1',
    origin: 'Unknown',
    harvest_date: '',
    requires_cold_chain: false,
  });

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setSuccess(null);
    try {
      const res = await productApi.create({
        ...formData,
        harvest_date: formData.harvest_date ? new Date(formData.harvest_date).toISOString() : null,
      });
      setSuccess(res.data);
      setFormData({ 
        name: '', 
        category: 'Vegetable', 
        description: '', 
        location: 'Farm A-1',
        origin: 'Unknown',
        harvest_date: '',
        requires_cold_chain: false,
      });
    } catch (error) {
      console.error("Failed to register product", error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-2xl mx-auto space-y-8">
      <div>
        <h1 className="text-3xl font-bold text-white">Crop Registry</h1>
        <p className="text-gray-400 mt-2">Register new harvest batches on the AgriGuard chain.</p>
      </div>

      <div className="glass p-8 rounded-2xl">
        <form onSubmit={handleSubmit} className="space-y-6">
          <div className="space-y-2">
            <label className="text-sm font-medium text-gray-300">Crop Name</label>
            <input
              type="text"
              required
              value={formData.name}
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              className="w-full bg-white/5 border border-white/10 rounded-lg px-4 py-3 text-white focus:ring-2 focus:ring-green-500 outline-none transition-all"
              placeholder="e.g. Organic Tomatoes"
            />
          </div>

          <div className="grid grid-cols-2 gap-6">
            <div className="space-y-2">
              <label className="text-sm font-medium text-gray-300">Category</label>
              <select
                value={formData.category}
                onChange={(e) => setFormData({ ...formData, category: e.target.value })}
                className="w-full bg-white/5 border border-white/10 rounded-lg px-4 py-3 text-white focus:ring-2 focus:ring-green-500 outline-none transition-all"
              >
                <option value="Vegetable">Vegetable</option>
                <option value="Fruit">Fruit</option>
                <option value="Grain">Grain</option>
              </select>
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium text-gray-300">Origin Region</label>
              <input
                type="text"
                value={formData.origin}
                onChange={(e) => setFormData({ ...formData, origin: e.target.value })}
                className="w-full bg-white/5 border border-white/10 rounded-lg px-4 py-3 text-white focus:ring-2 focus:ring-green-500 outline-none transition-all"
                placeholder="e.g. California, General Farm"
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-6">
            <div className="space-y-2">
              <label className="text-sm font-medium text-gray-300">Harvest Date</label>
              <input
                type="date"
                value={formData.harvest_date}
                onChange={(e) => setFormData({ ...formData, harvest_date: e.target.value })}
                className="w-full bg-white/5 border border-white/10 rounded-lg px-4 py-3 text-white focus:ring-2 focus:ring-green-500 outline-none transition-all"
              />
            </div>
            <div className="space-y-2 flex items-center mt-8">
              <label className="flex items-center space-x-3 cursor-pointer">
                <input
                  type="checkbox"
                  checked={formData.requires_cold_chain}
                  onChange={(e) => setFormData({ ...formData, requires_cold_chain: e.target.checked })}
                  className="w-5 h-5 rounded border-gray-300 text-green-500 focus:ring-green-500 bg-white/5"
                />
                <span className="text-sm font-medium text-gray-300">Requires Cold Chain</span>
              </label>
            </div>
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium text-gray-300">Description</label>
            <textarea
              value={formData.description}
              onChange={(e) => setFormData({ ...formData, description: e.target.value })}
              className="w-full bg-white/5 border border-white/10 rounded-lg px-4 py-3 text-white focus:ring-2 focus:ring-green-500 outline-none transition-all h-32 resize-none"
              placeholder="Batch details..."
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full bg-gradient-to-r from-green-500 to-emerald-600 text-white font-bold py-4 rounded-xl hover:shadow-lg hover:shadow-green-500/30 transition-all flex items-center justify-center gap-2 disabled:opacity-50"
          >
            {loading ? <Loader2 className="animate-spin" /> : <Sprout />}
            Register Harvest
          </button>
        </form>
      </div>

      {success && (
        <div className="bg-green-500/10 border border-green-500/20 rounded-2xl p-6 animate-fade-in">
          <div className="flex items-start gap-4">
            <div className="p-3 bg-green-500/20 rounded-xl">
              <QrCode className="w-8 h-8 text-green-400" />
            </div>
            <div>
              <h3 className="text-lg font-bold text-white">Registration Successful!</h3>
              <p className="text-green-300 text-sm mt-1">Batch ID: <span className="font-mono bg-black/20 px-2 py-0.5 rounded">{success.id}</span></p>
              <div className="mt-4 p-3 bg-black/20 rounded-lg font-mono text-xs text-gray-400 break-all">
                TX: {success.qr_code}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
