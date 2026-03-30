import { useState, useEffect, useCallback, useRef } from 'react';
import { useParams, Link, useSearchParams } from 'react-router-dom';
import { Sprout, Loader2, ArrowLeft, ThermometerSnowflake, MapPin, Calendar, CheckCircle, Plus, ShieldCheck, Truck } from 'lucide-react';
import { productApi } from '../services/api';
import { trackQrEvent } from '../services/qrAnalytics';
import ProductTimeline from './ProductTimeline';
import { cn } from '../lib/utils';
import { Card, CardContent } from './ui/Card';
import { Button } from './ui/Button';
import { Input } from './ui/Input';
import { Badge } from './ui/Badge';

const VERIFICATION_TRACK_RETRY_DELAY_MS = 3000;
const MAX_VERIFICATION_TRACK_ATTEMPTS = 3;

export default function ProductDetail() {
  const { id } = useParams();
  const [searchParams] = useSearchParams();
  const verificationTrackedRef = useRef(false);
  const verificationRetryTimerRef = useRef(null);
  const [verificationTrackAttempt, setVerificationTrackAttempt] = useState(0);

  const [data, setData] = useState({
    product: null,
    history: [],
    loading: true
  });

  const [trackingState, setTrackingState] = useState({
    showForm: false,
    loading: false,
    data: { status: 'IN_TRANSIT', location: '', handler_id: '' }
  });

  const [certState, setCertState] = useState({
    showForm: false,
    loading: false,
    data: { cert_type: '', issued_by: '' }
  });
  const scanSource = searchParams.get('scan_source');
  const scanSession = searchParams.get('scan_session');
  const scanVariant = searchParams.get('scan_variant') || 'qr_page_v1';

  const loadProductDetails = useCallback(async (productId) => {
    const [prodRes, histRes] = await Promise.all([
      productApi.getById(productId),
      productApi.getHistory(productId)
    ]);
    return {
      product: prodRes.data,
      history: histRes.data.history
    };
  }, []);

  const refreshProductDetails = useCallback(async (productId) => {
    try {
      const nextData = await loadProductDetails(productId);
      setData({ product: nextData.product, history: nextData.history, loading: false });
    } catch (err) {
      console.error('Failed to refresh product details', err);
      setData(prev => ({ ...prev, loading: false }));
    }
  }, [loadProductDetails]);

  useEffect(() => {
    let isCancelled = false;
    const run = async () => {
      try {
        const nextData = await loadProductDetails(id);
        if (isCancelled) return;
        setData({ product: nextData.product, history: nextData.history, loading: false });
      } catch (err) {
        if (isCancelled) return;
        console.error("Failed to load product details", err);
        setData(prev => ({ ...prev, loading: false }));
      }
    };
    run();
    return () => { isCancelled = true; };
  }, [id, loadProductDetails]);

  useEffect(() => {
    if (verificationTrackedRef.current) {
      return;
    }
    if (!data.product) {
      return;
    }
    if (scanSource !== 'qr_reader' || !scanSession) {
      return;
    }

    let isCancelled = false;

    const attemptVerificationTracking = async () => {
      const tracked = await trackQrEvent({
        session_id: scanSession,
        event_type: 'verification_complete',
        product_id: id,
        source: scanSource,
        variant_id: scanVariant,
        event_payload: {
          product_name: data.product.name,
          origin: data.product.origin,
          requires_cold_chain: Boolean(data.product.requires_cold_chain),
        },
      });

      if (isCancelled) {
        return;
      }

      if (tracked) {
        verificationTrackedRef.current = true;
        return;
      }

      if (verificationTrackAttempt >= MAX_VERIFICATION_TRACK_ATTEMPTS - 1) {
        console.warn('Failed to track verification_complete after retries', {
          sessionId: scanSession,
          productId: id,
          attempts: verificationTrackAttempt + 1,
        });
        return;
      }

      verificationRetryTimerRef.current = window.setTimeout(() => {
        verificationRetryTimerRef.current = null;
        setVerificationTrackAttempt((current) => current + 1);
      }, VERIFICATION_TRACK_RETRY_DELAY_MS);
    };

    void attemptVerificationTracking();

    return () => {
      isCancelled = true;
      if (verificationRetryTimerRef.current) {
        window.clearTimeout(verificationRetryTimerRef.current);
        verificationRetryTimerRef.current = null;
      }
    };
  }, [data.product, id, scanSession, scanSource, scanVariant, verificationTrackAttempt]);

  const handleTrackingChange = useCallback((field, value) => {
    setTrackingState(prev => ({ ...prev, data: { ...prev.data, [field]: value } }));
  }, []);

  const handleCertChange = useCallback((field, value) => {
    setCertState(prev => ({ ...prev, data: { ...prev.data, [field]: value } }));
  }, []);

  const handleAddTracking = useCallback(async (e) => {
    e.preventDefault();
    if (!trackingState.data.location || !trackingState.data.handler_id) return;
    setTrackingState(prev => ({ ...prev, loading: true }));
    try {
      await productApi.addTracking(id, trackingState.data);
      await refreshProductDetails(id);
      setTrackingState({ showForm: false, loading: false, data: { status: 'IN_TRANSIT', location: '', handler_id: '' } });
    } catch (err) {
      console.error('Failed to add tracking event', err);
      setTrackingState(prev => ({ ...prev, loading: false }));
    }
  }, [id, trackingState.data, refreshProductDetails]);

  const handleAddCert = useCallback(async (e) => {
    e.preventDefault();
    if (!certState.data.cert_type || !certState.data.issued_by) return;
    setCertState(prev => ({ ...prev, loading: true }));
    try {
      await productApi.addCertification(id, certState.data);
      await refreshProductDetails(id);
      setCertState({ showForm: false, loading: false, data: { cert_type: '', issued_by: '' } });
    } catch (err) {
      console.error('Failed to add certification', err);
      setCertState(prev => ({ ...prev, loading: false }));
    }
  }, [id, certState.data, refreshProductDetails]);

  if (data.loading) {
    return (
      <div className="flex justify-center items-center h-64">
        <Loader2 className="w-8 h-8 text-primary animate-spin" />
      </div>
    );
  }

  if (!data.product) {
    return (
      <Card className="text-center mx-auto max-w-md mt-12">
        <CardContent className="p-8">
          <h2 className="text-2xl font-bold text-foreground mb-4">Product Not Found</h2>
          <Button variant="link" asChild className="text-primary">
            <Link to="/"><ArrowLeft className="w-4 h-4 mr-2" /> Back to Dashboard</Link>
          </Button>
        </CardContent>
      </Card>
    );
  }

  const { product, history } = data;
  const formInputClass = "w-full bg-white/5 border border-input rounded-lg px-4 py-2.5 text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-primary transition-all";

  return (
    <div className="max-w-4xl mx-auto space-y-8">
      <Button variant="ghost" asChild size="sm">
        <Link to="/"><ArrowLeft className="w-4 h-4 mr-1" /> Back</Link>
      </Button>

      <Card className="glass">
        <CardContent className="p-8">
          <div className="flex flex-col md:flex-row md:items-start justify-between gap-6">
            <div>
              <div className="flex items-center gap-3 mb-2">
                <Badge variant="default">{product.category}</Badge>
                {product.certificates?.length > 0 && (
                  <Badge variant="warning" className="gap-1">
                    <CheckCircle className="w-3.5 h-3.5" /> Certified
                  </Badge>
                )}
              </div>
              <h1 className="text-3xl font-bold text-foreground flex items-center gap-3 mb-2">
                <Sprout className="text-primary w-8 h-8" />
                {product.name}
              </h1>
              <p className="text-muted-foreground text-lg">
                ID: <Badge variant="outline" className="font-mono text-sm">{product.id}</Badge>
              </p>
            </div>

            <Card className="min-w-[200px]">
              <CardContent className="p-4">
                <img src={`https://api.qrserver.com/v1/create-qr-code/?size=150x150&data=${encodeURIComponent(product.qr_code)}&bgcolor=22C55E`} alt="QR Code" className="w-full rounded-lg mb-2 opacity-90 hover:opacity-100 transition-opacity" />
                <p className="text-center text-xs text-muted-foreground font-mono break-all">{product.qr_code}</p>
              </CardContent>
            </Card>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mt-8 pt-8 border-t border-border">
            <div className="flex items-start gap-4 p-4 rounded-xl bg-white/5">
              <MapPin className="text-blue-400 w-6 h-6 mt-1" />
              <div>
                <p className="text-sm text-muted-foreground font-medium">Origin</p>
                <p className="text-foreground font-semibold">{product.origin}</p>
              </div>
            </div>
            <div className="flex items-start gap-4 p-4 rounded-xl bg-white/5">
              <Calendar className="text-orange-400 w-6 h-6 mt-1" />
              <div>
                <p className="text-sm text-muted-foreground font-medium">Harvest Date</p>
                <p className="text-foreground font-semibold">
                  {product.harvest_date ? new Date(product.harvest_date).toLocaleDateString() : 'Pending'}
                </p>
              </div>
            </div>
            <div className="flex items-start gap-4 p-4 rounded-xl bg-white/5">
              <ThermometerSnowflake className={cn('w-6 h-6 mt-1', product.requires_cold_chain ? 'text-cyan-400' : 'text-muted-foreground')} />
              <div>
                <p className="text-sm text-muted-foreground font-medium">Cold Chain</p>
                <p className="text-foreground font-semibold">
                  {product.requires_cold_chain ? 'Required (Strict)' : 'Not Required'}
                </p>
              </div>
            </div>
          </div>

          {product.description && (
             <div className="mt-8">
                <h3 className="text-lg font-semibold text-foreground mb-2">Description</h3>
                <div className="p-4 rounded-xl bg-white/5 border border-border text-muted-foreground leading-relaxed">
                   {product.description}
                </div>
             </div>
          )}
        </CardContent>
      </Card>

      {/* Action Buttons */}
      <div className="flex gap-3">
        <Button
          variant="outline"
          onClick={() => setTrackingState(prev => ({ ...prev, showForm: !prev.showForm }))}
          className="border-orange-500/30 text-orange-400 hover:bg-orange-500/10"
        >
          <Truck className="w-4 h-4" /> Add Tracking Event
        </Button>
        <Button
          variant="outline"
          onClick={() => setCertState(prev => ({ ...prev, showForm: !prev.showForm }))}
          className="border-secondary/30 text-secondary hover:bg-secondary/10"
        >
          <ShieldCheck className="w-4 h-4" /> Add Certification
        </Button>
      </div>

      {/* Tracking Form */}
      {trackingState.showForm && (
        <Card className="glass border-orange-500/20">
          <CardContent className="p-6">
            <h3 className="text-lg font-bold text-foreground mb-4 flex items-center gap-2">
              <Truck className="w-5 h-5 text-orange-400" /> New Tracking Event
            </h3>
            <form onSubmit={handleAddTracking} className="space-y-3">
              <select
                value={trackingState.data.status}
                onChange={e => handleTrackingChange('status', e.target.value)}
                className={formInputClass}
              >
                <option value="REGISTERED">Registered (Farm)</option>
                <option value="IN_TRANSIT">In Transit</option>
                <option value="DELIVERED">Delivered</option>
                <option value="VERIFIED">Verified</option>
              </select>
              <Input
                type="text"
                placeholder="Location (e.g. Seoul Distribution Center)"
                value={trackingState.data.location}
                onChange={e => handleTrackingChange('location', e.target.value)}
                className={formInputClass}
                required
              />
              <Input
                type="text"
                placeholder="Handler ID (e.g. HANDLER-001)"
                value={trackingState.data.handler_id}
                onChange={e => handleTrackingChange('handler_id', e.target.value)}
                className={formInputClass}
                required
              />
              <div className="flex gap-2">
                <Button type="submit" disabled={trackingState.loading} className="bg-orange-500 hover:bg-orange-600">
                  {trackingState.loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />}
                  {trackingState.loading ? 'Submitting...' : 'Add Event'}
                </Button>
                <Button type="button" variant="ghost" onClick={() => setTrackingState(prev => ({ ...prev, showForm: false }))}>
                  Cancel
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>
      )}

      {/* Certification Form */}
      {certState.showForm && (
        <Card className="glass border-secondary/20">
          <CardContent className="p-6">
            <h3 className="text-lg font-bold text-foreground mb-4 flex items-center gap-2">
              <ShieldCheck className="w-5 h-5 text-secondary" /> New Certification
            </h3>
            <form onSubmit={handleAddCert} className="space-y-3">
              <Input
                type="text"
                placeholder="Certification Type (e.g. GAP, Organic, HACCP)"
                value={certState.data.cert_type}
                onChange={e => handleCertChange('cert_type', e.target.value)}
                className={formInputClass}
                required
              />
              <Input
                type="text"
                placeholder="Issued By (e.g. Korean Food Safety Authority)"
                value={certState.data.issued_by}
                onChange={e => handleCertChange('issued_by', e.target.value)}
                className={formInputClass}
                required
              />
              <div className="flex gap-2">
                <Button type="submit" disabled={certState.loading} className="bg-secondary hover:bg-secondary/80 text-secondary-foreground">
                  {certState.loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />}
                  {certState.loading ? 'Submitting...' : 'Add Certificate'}
                </Button>
                <Button type="button" variant="ghost" onClick={() => setCertState(prev => ({ ...prev, showForm: false }))}>
                  Cancel
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>
      )}

      <div className="mt-12">
        <ProductTimeline history={history} />
      </div>
    </div>
  );
}
