import { useState, useCallback } from 'react';
import { Sprout, QrCode, Loader2, Check, Copy } from 'lucide-react';
import { productApi } from '../services/api';
import { Card, CardContent } from './ui/Card';
import { Button } from './ui/Button';
import { Input } from './ui/Input';
import { Badge } from './ui/Badge';

const EMPTY_FORM = {
  name: '',
  category: 'Vegetable',
  description: '',
  origin: '',
  harvest_date: '',
  requires_cold_chain: false,
  owner_id: '',
};

const FIELD_IDS = {
  name: 'registry-crop-name',
  owner_id: 'registry-owner-id',
  category: 'registry-category',
  origin: 'registry-origin',
  harvest_date: 'registry-harvest-date',
  description: 'registry-description',
};

export default function ProductRegistry() {
  const [uiState, setUiState] = useState({
    loading: false,
    success: null,
    submitError: null,
  });
  const [labelCopyStatus, setLabelCopyStatus] = useState('');

  const [formData, setFormData] = useState(EMPTY_FORM);

  const handleChange = useCallback((field, value) => {
    setFormData(prev => ({ ...prev, [field]: value }));
  }, []);

  const handleSubmit = useCallback(async (e) => {
    e.preventDefault();
    if (!formData.owner_id.trim()) {
      setUiState(prev => ({ ...prev, submitError: 'Owner ID is required.' }));
      return;
    }

    setUiState({ loading: true, success: null, submitError: null });

    try {
      const res = await productApi.create({
        ...formData,
        harvest_date: formData.harvest_date ? new Date(formData.harvest_date).toISOString() : null,
      });
      setUiState({ loading: false, success: res.data, submitError: null });
      setLabelCopyStatus('');
      setFormData(EMPTY_FORM);
    } catch (error) {
      console.error("Failed to register product", error);
      setUiState({
        loading: false,
        success: null,
        submitError: error.response?.data?.detail || error.message || 'Registration failed.'
      });
    }
  }, [formData]);

  const handleCopyLabelUrl = useCallback(async () => {
    const labelUrl = uiState.success?.qr_code;
    if (!labelUrl) return;

    if (!navigator.clipboard?.writeText) {
      setLabelCopyStatus('Copy failed');
      return;
    }

    try {
      await navigator.clipboard.writeText(labelUrl);
      setLabelCopyStatus('Copied');
    } catch (error) {
      console.error('Failed to copy registry label URL', error);
      setLabelCopyStatus('Copy failed');
    }
  }, [uiState.success?.qr_code]);

  const inputClass = "min-h-11 w-full bg-white/5 border border-input rounded-lg px-4 py-2.5 text-foreground focus:ring-2 focus:ring-ring outline-none transition-all placeholder:text-muted-foreground sm:py-3";

  return (
    <div data-testid="registry-page" className="mx-auto max-w-2xl space-y-4 sm:space-y-8">
      <div>
        <h1 className="text-3xl font-bold text-foreground">Crop Registry</h1>
        <p className="text-muted-foreground mt-2">Register new harvest batches on the AgriGuard chain.</p>
      </div>

      <Card className="glass">
        <CardContent data-testid="registry-card-content" className="p-3 sm:p-8">
          <form onSubmit={handleSubmit} className="space-y-3 sm:space-y-6">
            <div className="space-y-2">
              <label className="text-sm font-medium text-muted-foreground" htmlFor={FIELD_IDS.name}>Crop Name</label>
              <Input
                id={FIELD_IDS.name}
                type="text"
                required
                value={formData.name}
                onChange={(e) => handleChange('name', e.target.value)}
                className={inputClass}
                placeholder="e.g. Organic Tomatoes"
              />
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium text-muted-foreground" htmlFor={FIELD_IDS.owner_id}>Owner ID <span className="text-destructive">*</span></label>
              <Input
                id={FIELD_IDS.owner_id}
                type="text"
                required
                value={formData.owner_id}
                onChange={(e) => handleChange('owner_id', e.target.value)}
                className={inputClass}
                placeholder="e.g. farmer-001"
              />
            </div>

            <div data-testid="registry-product-origin-grid" className="grid grid-cols-1 gap-4 sm:grid-cols-2 sm:gap-6">
              <div className="space-y-2">
                <label className="text-sm font-medium text-muted-foreground" htmlFor={FIELD_IDS.category}>Category</label>
                <select
                  id={FIELD_IDS.category}
                  value={formData.category}
                  onChange={(e) => handleChange('category', e.target.value)}
                  className={inputClass}
                >
                  <option value="Vegetable">Vegetable</option>
                  <option value="Fruit">Fruit</option>
                  <option value="Grain">Grain</option>
                </select>
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium text-muted-foreground" htmlFor={FIELD_IDS.origin}>Origin Region</label>
                <Input
                  id={FIELD_IDS.origin}
                  type="text"
                  value={formData.origin}
                  onChange={(e) => handleChange('origin', e.target.value)}
                  className={inputClass}
                  placeholder="e.g. California, Jeolla-do"
                />
              </div>
            </div>

            <div data-testid="registry-harvest-chain-grid" className="grid grid-cols-1 gap-4 sm:grid-cols-2 sm:gap-6">
              <div className="space-y-2">
                <label className="text-sm font-medium text-muted-foreground" htmlFor={FIELD_IDS.harvest_date}>Harvest Date</label>
                <Input
                  id={FIELD_IDS.harvest_date}
                  type="date"
                  value={formData.harvest_date}
                  onChange={(e) => handleChange('harvest_date', e.target.value)}
                  className={inputClass}
                />
              </div>
              <div data-testid="registry-cold-chain-control" className="space-y-2 flex items-center sm:mt-8">
                <label className="group relative flex min-h-11 cursor-pointer items-center gap-3">
                  <input
                    type="checkbox"
                    checked={formData.requires_cold_chain}
                    onChange={(e) => handleChange('requires_cold_chain', e.target.checked)}
                    className="peer absolute inset-0 z-10 h-full w-full cursor-pointer opacity-0"
                  />
                  <span
                    data-testid="registry-cold-chain-checkbox"
                    className="pointer-events-none flex h-6 w-6 shrink-0 items-center justify-center rounded-md border-2 border-primary bg-primary/10 text-transparent transition-all group-hover:bg-primary/15 peer-checked:bg-primary peer-checked:text-primary-foreground peer-focus-visible:ring-2 peer-focus-visible:ring-ring"
                    aria-hidden="true"
                  >
                    <Check className="h-4 w-4" />
                  </span>
                  <span className="text-sm font-medium text-muted-foreground whitespace-nowrap">Requires Cold Chain</span>
                </label>
              </div>
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium text-muted-foreground" htmlFor={FIELD_IDS.description}>Description</label>
              <textarea
                id={FIELD_IDS.description}
                value={formData.description}
                onChange={(e) => handleChange('description', e.target.value)}
                className={`${inputClass} h-16 resize-none sm:h-32`}
                placeholder="Batch details..."
              />
            </div>

            {uiState.submitError && (
              <div className="bg-destructive/10 border border-destructive/30 rounded-lg px-4 py-3 text-destructive text-sm">
                {uiState.submitError}
              </div>
            )}

            <Button
              type="submit"
              disabled={uiState.loading}
              size="lg"
              className="w-full bg-gradient-to-r from-primary to-emerald-600 font-bold py-4 hover:shadow-lg hover:shadow-primary/30"
            >
              {uiState.loading ? <Loader2 className="animate-spin" /> : <Sprout />}
              Register Harvest
            </Button>
          </form>
        </CardContent>
      </Card>

      {uiState.success && (
        <Card className="border-primary/20 bg-primary/5 animate-in fade-in duration-500">
          <CardContent className="p-6">
            <div className="flex items-start gap-4">
              <div className="p-3 bg-primary/20 rounded-xl">
                <QrCode className="w-8 h-8 text-primary" />
              </div>
              <div data-testid="registry-success-content" className="min-w-0 flex-1">
                <h3 className="text-lg font-bold text-foreground">Registration Successful!</h3>
                <p className="text-primary text-sm mt-1">
                  Batch ID: <Badge variant="outline" className="font-mono">{uiState.success.id}</Badge>
                </p>
                <p className="mt-4 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                  Public verify label
                </p>
                <div
                  data-testid="registry-label-url"
                  title={uiState.success.qr_code}
                  className="mt-4 max-w-full overflow-x-auto whitespace-nowrap rounded-lg bg-background/50 p-3 font-mono text-xs text-muted-foreground"
                >
                  {uiState.success.qr_code}
                </div>
                <Button
                  type="button"
                  variant="outline"
                  onClick={handleCopyLabelUrl}
                  className="mt-3 min-h-11 w-full border-primary/25 text-primary hover:bg-primary/10 sm:w-auto"
                  aria-label={labelCopyStatus === 'Copied' ? 'Copied public verify label URL' : 'Copy public verify label URL'}
                >
                  {labelCopyStatus === 'Copied' ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
                  {labelCopyStatus || 'Copy label URL'}
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
