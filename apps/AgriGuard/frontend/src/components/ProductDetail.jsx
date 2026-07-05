import { useState, useEffect, useCallback, useRef } from 'react';
import { useParams, Link, useSearchParams } from 'react-router-dom';
import { Sprout, Loader2, ArrowLeft, ThermometerSnowflake, MapPin, Calendar, CheckCircle, Plus, ShieldCheck, Truck } from 'lucide-react';
import { hasOperatorToken, productApi } from '../services/api';
import { trackQrEvent } from '../services/qrAnalytics';
import ProductTimeline from './ProductTimeline';
import QRTracker from './QRTracker';
import { cn } from '../lib/utils';
import { Card, CardContent } from './ui/Card';
import { Button } from './ui/Button';
import { Input } from './ui/Input';
import { Badge } from './ui/Badge';

const VERIFICATION_TRACK_RETRY_DELAY_MS = 3000;
const MAX_VERIFICATION_TRACK_ATTEMPTS = 3;
const OPERATOR_AUTH_REQUIRED_MESSAGE = 'Operator authentication required to save chain updates.';

function protectedActionErrorMessage(error, fallbackMessage) {
  if (error?.response?.status === 401) {
    return OPERATOR_AUTH_REQUIRED_MESSAGE;
  }
  return fallbackMessage;
}

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
  const [operatorTokenAvailable] = useState(() => hasOperatorToken());
  const [operatorNotice, setOperatorNotice] = useState(
    operatorTokenAvailable ? '' : 'Operator updates locked',
  );
  const scanSource = searchParams.get('scan_source');
  const scanSession = searchParams.get('scan_session');
  const scanVariant = searchParams.get('scan_variant') || 'qr_page_v1';

  const loadProductDetails = useCallback(async (productId) => {
    const [prodRes, histRes] = await Promise.allSettled([
      productApi.getById(productId),
      productApi.getHistory(productId)
    ]);

    if (prodRes.status !== 'fulfilled') {
      throw prodRes.reason;
    }

    if (histRes.status !== 'fulfilled') {
      console.error('Failed to load product history', histRes.reason);
    }

    return {
      product: prodRes.value.data,
      history: histRes.status === 'fulfilled' ? (histRes.value.data.history || []) : []
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
    setOperatorNotice('');
    setTrackingState(prev => ({ ...prev, loading: true }));
    try {
      await productApi.addTracking(id, trackingState.data);
      await refreshProductDetails(id);
      setTrackingState({ showForm: false, loading: false, data: { status: 'IN_TRANSIT', location: '', handler_id: '' } });
      setOperatorNotice('Tracking event saved');
    } catch (err) {
      setOperatorNotice(protectedActionErrorMessage(err, 'Tracking event could not be saved.'));
      setTrackingState(prev => ({ ...prev, loading: false }));
    }
  }, [id, trackingState.data, refreshProductDetails]);

  const handleAddCert = useCallback(async (e) => {
    e.preventDefault();
    if (!certState.data.cert_type || !certState.data.issued_by) return;
    setOperatorNotice('');
    setCertState(prev => ({ ...prev, loading: true }));
    try {
      await productApi.addCertification(id, certState.data);
      await refreshProductDetails(id);
      setCertState({ showForm: false, loading: false, data: { cert_type: '', issued_by: '' } });
      setOperatorNotice('Certificate saved');
    } catch (err) {
      setOperatorNotice(protectedActionErrorMessage(err, 'Certificate could not be saved.'));
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
  const qrCodeValue = String(product.qr_code || product.id);
  const formInputClass = "w-full bg-white/5 border border-input rounded-lg px-4 py-2.5 text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-primary transition-all";

  const actionControls = (
    <div data-testid="product-detail-actions" className="mt-4 grid gap-2 border-t border-border pt-4 sm:flex sm:flex-wrap sm:items-center md:mt-6 md:gap-3 md:pt-6">
      {operatorNotice && (
        <Badge variant={operatorTokenAvailable ? 'info' : 'outline'} className="justify-center border-amber-500/30 text-amber-300 sm:justify-start">
          {operatorNotice}
        </Badge>
      )}
      <Button
        variant="outline"
        disabled={!operatorTokenAvailable}
        title={operatorTokenAvailable ? undefined : OPERATOR_AUTH_REQUIRED_MESSAGE}
        onClick={() => {
          setOperatorNotice('');
          setTrackingState(prev => ({ ...prev, showForm: !prev.showForm }));
        }}
        className="w-full border-orange-500/30 text-orange-400 hover:bg-orange-500/10 sm:w-auto"
      >
        <Truck className="w-4 h-4" /> Add Tracking Event
      </Button>
      <Button
        variant="outline"
        disabled={!operatorTokenAvailable}
        title={operatorTokenAvailable ? undefined : OPERATOR_AUTH_REQUIRED_MESSAGE}
        onClick={() => {
          setOperatorNotice('');
          setCertState(prev => ({ ...prev, showForm: !prev.showForm }));
        }}
        className="w-full border-secondary/30 text-secondary hover:bg-secondary/10 sm:w-auto"
      >
        <ShieldCheck className="w-4 h-4" /> Add Certification
      </Button>
    </div>
  );

  return (
    <div className="max-w-4xl mx-auto space-y-6 sm:space-y-8">
      <Button variant="ghost" asChild size="sm">
        <Link to="/"><ArrowLeft className="w-4 h-4 mr-1" /> Back</Link>
      </Button>

      <Card data-testid="product-detail-card" className="glass">
        <CardContent data-testid="product-detail-card-content" className="p-4 sm:p-8">
          <div className="flex flex-col justify-between gap-4 md:flex-row md:items-start md:gap-6">
            <div>
              <div className="flex items-center gap-3 mb-2">
                <Badge variant="default">{product.category}</Badge>
                {product.certificates?.length > 0 && (
                  <Badge variant="warning" className="gap-1">
                    <CheckCircle className="w-3.5 h-3.5" /> Certified
                  </Badge>
                )}
              </div>
              <h1 data-testid="product-detail-heading" className="flex items-start gap-3 mb-2 text-2xl font-bold leading-tight text-foreground sm:text-3xl">
                <Sprout className="mt-0.5 h-7 w-7 shrink-0 text-primary sm:h-8 sm:w-8" />
                <span className="min-w-0 break-words">{product.name}</span>
              </h1>
              <p className="text-muted-foreground text-lg">
                ID: <Badge variant="outline" className="font-mono text-sm">{product.id}</Badge>
              </p>
            </div>

            <Card data-testid="product-detail-qr-card" className="min-w-[200px]">
              <CardContent data-testid="product-detail-qr-card-content" className="p-3 sm:p-4">
                <div className="flex justify-center mb-2">
                  <QRTracker value={qrCodeValue} ariaLabel="Product verification QR" />
                </div>
                <p className="text-center text-xs text-muted-foreground font-mono break-all">{qrCodeValue}</p>
              </CardContent>
            </Card>
          </div>

          <div data-testid="product-detail-evidence-grid" className="mt-4 grid grid-cols-3 gap-2 border-t border-border pt-4 md:mt-8 md:gap-6 md:pt-8">
            <div className="flex min-w-0 flex-col gap-2 rounded-xl bg-white/5 p-2 sm:flex-row sm:items-start sm:gap-4 sm:p-4">
              <MapPin className="h-5 w-5 shrink-0 text-blue-400 sm:mt-1 sm:h-6 sm:w-6" />
              <div className="min-w-0">
                <p className="text-[11px] font-medium leading-tight text-muted-foreground sm:text-sm">Origin</p>
                <p className="break-words text-xs font-semibold leading-tight text-foreground sm:text-base">{product.origin}</p>
              </div>
            </div>
            <div className="flex min-w-0 flex-col gap-2 rounded-xl bg-white/5 p-2 sm:flex-row sm:items-start sm:gap-4 sm:p-4">
              <Calendar className="h-5 w-5 shrink-0 text-orange-400 sm:mt-1 sm:h-6 sm:w-6" />
              <div className="min-w-0">
                <p className="text-[11px] font-medium leading-tight text-muted-foreground sm:text-sm">Harvest Date</p>
                <p className="break-words text-xs font-semibold leading-tight text-foreground sm:text-base">
                  {product.harvest_date ? new Date(product.harvest_date).toLocaleDateString() : 'Pending'}
                </p>
              </div>
            </div>
            <div className="flex min-w-0 flex-col gap-2 rounded-xl bg-white/5 p-2 sm:flex-row sm:items-start sm:gap-4 sm:p-4">
              <ThermometerSnowflake className={cn('h-5 w-5 shrink-0 sm:mt-1 sm:h-6 sm:w-6', product.requires_cold_chain ? 'text-cyan-400' : 'text-muted-foreground')} />
              <div className="min-w-0">
                <p className="text-[11px] font-medium leading-tight text-muted-foreground sm:text-sm">Cold Chain</p>
                <p className="break-words text-xs font-semibold leading-tight text-foreground sm:text-base">
                  {product.requires_cold_chain ? 'Required (Strict)' : 'Not Required'}
                </p>
              </div>
            </div>
          </div>

          {actionControls}

          {product.description && (
             <div className="mt-4 md:mt-8">
                <h3 className="text-lg font-semibold text-foreground mb-2">Description</h3>
                <div className="p-4 rounded-xl bg-white/5 border border-border text-muted-foreground leading-relaxed">
                   {product.description}
                </div>
             </div>
          )}
        </CardContent>
      </Card>

      {/* Tracking Form */}
      {operatorTokenAvailable && trackingState.showForm && (
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
      {operatorTokenAvailable && certState.showForm && (
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
