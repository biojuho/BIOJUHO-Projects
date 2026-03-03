import { useState, useCallback } from 'react';
import { Sprout, QrCode, Loader2 } from 'lucide-react';
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

export default function ProductRegistry() {
  const [uiState, setUiState] = useState({
    loading: false,
    success: null,
    submitError: null,
  });
  
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

  const inputClass = "w-full bg-white/5 border border-input rounded-lg px-4 py-3 text-foreground focus:ring-2 focus:ring-ring outline-none transition-all placeholder:text-muted-foreground";

  return (
    <div className="max-w-2xl mx-auto space-y-8">
      <div>
        <h1 className="text-3xl font-bold text-foreground">Crop Registry</h1>
        <p className="text-muted-foreground mt-2">Register new harvest batches on the AgriGuard chain.</p>
      </div>

      <Card className="glass">
        <CardContent className="p-8">
          <form onSubmit={handleSubmit} className="space-y-6">
            <div className="space-y-2">
              <label className="text-sm font-medium text-muted-foreground">Crop Name</label>
              <Input
                type="text"
                required
                value={formData.name}
                onChange={(e) => handleChange('name', e.target.value)}
                className={inputClass}
                placeholder="e.g. Organic Tomatoes"
              />
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium text-muted-foreground">Owner ID <span className="text-destructive">*</span></label>
              <Input
                type="text"
                required
                value={formData.owner_id}
                onChange={(e) => handleChange('owner_id', e.target.value)}
                className={inputClass}
                placeholder="e.g. farmer-001"
              />
            </div>

            <div className="grid grid-cols-2 gap-6">
              <div className="space-y-2">
                <label className="text-sm font-medium text-muted-foreground">Category</label>
                <select
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
                <label className="text-sm font-medium text-muted-foreground">Origin Region</label>
                <Input
                  type="text"
                  value={formData.origin}
                  onChange={(e) => handleChange('origin', e.target.value)}
                  className={inputClass}
                  placeholder="e.g. California, Jeolla-do"
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-6">
              <div className="space-y-2">
                <label className="text-sm font-medium text-muted-foreground">Harvest Date</label>
                <Input
                  type="date"
                  value={formData.harvest_date}
                  onChange={(e) => handleChange('harvest_date', e.target.value)}
                  className={inputClass}
                />
              </div>
              <div className="space-y-2 flex items-center mt-8">
                <label className="flex items-center space-x-3 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={formData.requires_cold_chain}
                    onChange={(e) => handleChange('requires_cold_chain', e.target.checked)}
                    className="w-5 h-5 rounded border-border text-primary focus:ring-ring bg-white/5"
                  />
                  <span className="text-sm font-medium text-muted-foreground">Requires Cold Chain</span>
                </label>
              </div>
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium text-muted-foreground">Description</label>
              <textarea
                value={formData.description}
                onChange={(e) => handleChange('description', e.target.value)}
                className={`${inputClass} h-32 resize-none`}
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
              <div>
                <h3 className="text-lg font-bold text-foreground">Registration Successful!</h3>
                <p className="text-primary text-sm mt-1">
                  Batch ID: <Badge variant="outline" className="font-mono">{uiState.success.id}</Badge>
                </p>
                <div className="mt-4 p-3 bg-background/50 rounded-lg font-mono text-xs text-muted-foreground break-all">
                  TX: {uiState.success.qr_code}
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
