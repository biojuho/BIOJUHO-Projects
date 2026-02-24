import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { Sprout, Loader2, ArrowLeft, ThermometerSnowflake, MapPin, Calendar, CheckCircle, Plus, ShieldCheck, Truck } from 'lucide-react';
import { productApi } from '../services/api';
import ProductTimeline from './ProductTimeline';

export default function ProductDetail() {
  const { id } = useParams();
  const [product, setProduct] = useState(null);
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(true);

  // Tracking form state
  const [showTrackingForm, setShowTrackingForm] = useState(false);
  const [trackingData, setTrackingData] = useState({ status: 'IN_TRANSIT', location: '', handler_id: '' });
  const [trackingLoading, setTrackingLoading] = useState(false);

  // Certification form state
  const [showCertForm, setShowCertForm] = useState(false);
  const [certData, setCertData] = useState({ cert_type: '', issued_by: '' });
  const [certLoading, setCertLoading] = useState(false);

  const fetchProductDetails = async () => {
    try {
      const [prodRes, histRes] = await Promise.all([
        productApi.getById(id),
        productApi.getHistory(id)
      ]);
      setProduct(prodRes.data);
      setHistory(histRes.data.history);
    } catch (err) {
      console.error("Failed to load product details", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchProductDetails();
  }, [id]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleAddTracking = async (e) => {
    e.preventDefault();
    if (!trackingData.location || !trackingData.handler_id) return;
    setTrackingLoading(true);
    try {
      await productApi.addTracking(id, trackingData);
      await fetchProductDetails();
      setShowTrackingForm(false);
      setTrackingData({ status: 'IN_TRANSIT', location: '', handler_id: '' });
    } catch (err) {
      console.error('Failed to add tracking event', err);
    } finally {
      setTrackingLoading(false);
    }
  };

  const handleAddCert = async (e) => {
    e.preventDefault();
    if (!certData.cert_type || !certData.issued_by) return;
    setCertLoading(true);
    try {
      await productApi.addCertification(id, certData);
      await fetchProductDetails();
      setShowCertForm(false);
      setCertData({ cert_type: '', issued_by: '' });
    } catch (err) {
      console.error('Failed to add certification', err);
    } finally {
      setCertLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex justify-center items-center h-64">
        <Loader2 className="w-8 h-8 text-green-500 animate-spin" />
      </div>
    );
  }

  if (!product) {
    return (
      <div className="text-center text-white p-8">
        <h2 className="text-2xl font-bold mb-4">Product Not Found</h2>
        <Link to="/" className="text-green-400 hover:text-green-300 flex items-center justify-center gap-2">
          <ArrowLeft className="w-4 h-4" /> Back to Dashboard
        </Link>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto space-y-8 animate-fade-in">
      <Link to="/" className="inline-flex items-center gap-2 text-gray-400 hover:text-white transition-colors">
        <ArrowLeft className="w-4 h-4" /> Back
      </Link>

      <div className="glass p-8 rounded-2xl">
        <div className="flex flex-col md:flex-row md:items-start justify-between gap-6">
          <div>
            <div className="flex items-center gap-3 mb-2">
              <span className="bg-green-500/20 text-green-400 px-3 py-1 rounded-full text-sm font-semibold border border-green-500/30">
                {product.category}
              </span>
              {product.certificates?.length > 0 && (
                <span className="bg-yellow-500/20 text-yellow-400 px-3 py-1 rounded-full text-sm font-semibold border border-yellow-500/30 flex items-center gap-1">
                  <CheckCircle className="w-4 h-4" /> Certified
                </span>
              )}
            </div>
            <h1 className="text-3xl font-bold text-white flex items-center gap-3 mb-2">
              <Sprout className="text-green-500 w-8 h-8" />
              {product.name}
            </h1>
            <p className="text-gray-400 text-lg">ID: <span className="font-mono text-sm px-2 py-1 bg-black/30 rounded">{product.id}</span></p>
          </div>
          
          <div className="bg-white/5 p-4 rounded-xl border border-white/10 min-w-[200px]">
            <img src={`https://api.qrserver.com/v1/create-qr-code/?size=150x150&data=${encodeURIComponent(product.qr_code)}&bgcolor=22C55E`} alt="QR Code" className="w-full rounded-lg mb-2 opacity-90 hover:opacity-100 transition-opacity" />
            <p className="text-center text-xs text-gray-400 font-mono break-all">{product.qr_code}</p>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mt-8 pt-8 border-t border-white/10">
          <div className="flex items-start gap-4 p-4 rounded-xl bg-white/5">
            <MapPin className="text-blue-400 w-6 h-6 mt-1" />
            <div>
              <p className="text-sm text-gray-400 font-medium">Origin</p>
              <p className="text-white font-semibold">{product.origin}</p>
            </div>
          </div>
          <div className="flex items-start gap-4 p-4 rounded-xl bg-white/5">
            <Calendar className="text-orange-400 w-6 h-6 mt-1" />
            <div>
              <p className="text-sm text-gray-400 font-medium">Harvest Date</p>
              <p className="text-white font-semibold">
                {product.harvest_date ? new Date(product.harvest_date).toLocaleDateString() : 'Pending'}
              </p>
            </div>
          </div>
          <div className="flex items-start gap-4 p-4 rounded-xl bg-white/5">
            <ThermometerSnowflake className={`w-6 h-6 mt-1 ${product.requires_cold_chain ? 'text-cyan-400' : 'text-gray-500'}`} />
            <div>
              <p className="text-sm text-gray-400 font-medium">Cold Chain</p>
              <p className="text-white font-semibold">
                {product.requires_cold_chain ? 'Required (Strict)' : 'Not Required'}
              </p>
            </div>
          </div>
        </div>
        
        {product.description && (
           <div className="mt-8">
              <h3 className="text-lg font-semibold text-white mb-2">Description</h3>
              <div className="p-4 rounded-xl bg-white/5 border border-white/10 text-gray-300 leading-relaxed">
                 {product.description}
              </div>
           </div>
        )}
      </div>

      {/* Action Buttons */}
      <div className="flex gap-3">
        <button
          onClick={() => setShowTrackingForm(!showTrackingForm)}
          className="flex items-center gap-2 px-4 py-2.5 bg-orange-500/20 text-orange-400 border border-orange-500/30 rounded-xl hover:bg-orange-500/30 transition-colors font-semibold text-sm"
        >
          <Truck className="w-4 h-4" /> Add Tracking Event
        </button>
        <button
          onClick={() => setShowCertForm(!showCertForm)}
          className="flex items-center gap-2 px-4 py-2.5 bg-yellow-500/20 text-yellow-400 border border-yellow-500/30 rounded-xl hover:bg-yellow-500/30 transition-colors font-semibold text-sm"
        >
          <ShieldCheck className="w-4 h-4" /> Add Certification
        </button>
      </div>

      {/* Tracking Form */}
      {showTrackingForm && (
        <div className="glass p-6 rounded-2xl border border-orange-500/20 animate-fade-in">
          <h3 className="text-lg font-bold text-white mb-4 flex items-center gap-2">
            <Truck className="w-5 h-5 text-orange-400" /> New Tracking Event
          </h3>
          <form onSubmit={handleAddTracking} className="space-y-3">
            <select
              value={trackingData.status}
              onChange={e => setTrackingData({ ...trackingData, status: e.target.value })}
              className="w-full bg-white/5 border border-white/10 rounded-lg px-4 py-2.5 text-white focus:outline-none focus:border-orange-500"
            >
              <option value="REGISTERED">Registered (Farm)</option>
              <option value="IN_TRANSIT">In Transit</option>
              <option value="DELIVERED">Delivered</option>
              <option value="VERIFIED">Verified</option>
            </select>
            <input
              type="text"
              placeholder="Location (e.g. Seoul Distribution Center)"
              value={trackingData.location}
              onChange={e => setTrackingData({ ...trackingData, location: e.target.value })}
              className="w-full bg-white/5 border border-white/10 rounded-lg px-4 py-2.5 text-white placeholder:text-gray-500 focus:outline-none focus:border-orange-500"
              required
            />
            <input
              type="text"
              placeholder="Handler ID (e.g. HANDLER-001)"
              value={trackingData.handler_id}
              onChange={e => setTrackingData({ ...trackingData, handler_id: e.target.value })}
              className="w-full bg-white/5 border border-white/10 rounded-lg px-4 py-2.5 text-white placeholder:text-gray-500 focus:outline-none focus:border-orange-500"
              required
            />
            <div className="flex gap-2">
              <button
                type="submit"
                disabled={trackingLoading}
                className="flex items-center gap-2 px-5 py-2.5 bg-orange-500 text-white rounded-lg hover:bg-orange-600 transition-colors font-semibold disabled:opacity-50"
              >
                {trackingLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />}
                {trackingLoading ? 'Submitting...' : 'Add Event'}
              </button>
              <button type="button" onClick={() => setShowTrackingForm(false)} className="px-4 py-2.5 text-gray-400 hover:text-white transition-colors">
                Cancel
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Certification Form */}
      {showCertForm && (
        <div className="glass p-6 rounded-2xl border border-yellow-500/20 animate-fade-in">
          <h3 className="text-lg font-bold text-white mb-4 flex items-center gap-2">
            <ShieldCheck className="w-5 h-5 text-yellow-400" /> New Certification
          </h3>
          <form onSubmit={handleAddCert} className="space-y-3">
            <input
              type="text"
              placeholder="Certification Type (e.g. GAP, Organic, HACCP)"
              value={certData.cert_type}
              onChange={e => setCertData({ ...certData, cert_type: e.target.value })}
              className="w-full bg-white/5 border border-white/10 rounded-lg px-4 py-2.5 text-white placeholder:text-gray-500 focus:outline-none focus:border-yellow-500"
              required
            />
            <input
              type="text"
              placeholder="Issued By (e.g. Korean Food Safety Authority)"
              value={certData.issued_by}
              onChange={e => setCertData({ ...certData, issued_by: e.target.value })}
              className="w-full bg-white/5 border border-white/10 rounded-lg px-4 py-2.5 text-white placeholder:text-gray-500 focus:outline-none focus:border-yellow-500"
              required
            />
            <div className="flex gap-2">
              <button
                type="submit"
                disabled={certLoading}
                className="flex items-center gap-2 px-5 py-2.5 bg-yellow-500 text-black rounded-lg hover:bg-yellow-400 transition-colors font-semibold disabled:opacity-50"
              >
                {certLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />}
                {certLoading ? 'Submitting...' : 'Add Certificate'}
              </button>
              <button type="button" onClick={() => setShowCertForm(false)} className="px-4 py-2.5 text-gray-400 hover:text-white transition-colors">
                Cancel
              </button>
            </div>
          </form>
        </div>
      )}

      <div className="mt-12">
        <ProductTimeline history={history} />
      </div>
    </div>
  );
}
