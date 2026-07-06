import { useCallback, useEffect, useState } from 'react';
import { Package, Truck, CheckCircle, Factory, ShieldCheck, MapPin, Search, X } from 'lucide-react';
import { productApi } from '../services/api';
import { cn } from '../lib/utils';
import { Card, CardContent } from './ui/Card';
import { Input } from './ui/Input';
import { Badge } from './ui/Badge';
import { Button } from './ui/Button';

const PAGE_SIZE = 20;
const COMPLETE_STATUSES = ['DELIVERED', 'VERIFIED'];
const SUPPLY_CHAIN_STEPS = [
  {
    status: 'REGISTERED',
    label: 'Farm',
    activeStatuses: ['REGISTERED', 'IN_TRANSIT', ...COMPLETE_STATUSES],
    activeClassName: 'border-primary bg-primary/20',
  },
  {
    status: 'IN_TRANSIT',
    label: 'Transit',
    activeStatuses: ['IN_TRANSIT', ...COMPLETE_STATUSES],
    activeClassName: 'border-orange-500 bg-orange-500/20',
  },
  {
    status: 'DELIVERED',
    label: 'Delivered',
    activeStatuses: COMPLETE_STATUSES,
    activeClassName: 'border-blue-500 bg-blue-500/20',
  },
];

const getStatusIcon = (status) => {
  switch (status) {
    case 'REGISTERED':
      return <Factory className="w-5 h-5 text-blue-400" />;
    case 'IN_TRANSIT':
      return <Truck className="w-5 h-5 text-orange-400" />;
    case 'DELIVERED':
    case 'VERIFIED':
      return <CheckCircle className="w-5 h-5 text-primary" />;
    default:
      return <Package className="w-5 h-5 text-muted-foreground" />;
  }
};

const getStatusText = (status) => {
  switch (status) {
    case 'REGISTERED':
      return 'At Farm / Processing';
    case 'IN_TRANSIT':
      return 'In Transit to Distributor';
    case 'DELIVERED':
    case 'VERIFIED':
      return 'Delivered & Available';
    default:
      return 'Unknown Status';
  }
};

const STATUS_ALIASES = new Map([
  ['REGISTERED', 'REGISTERED'],
  ['PLANTED', 'REGISTERED'],
  ['HARVESTED', 'REGISTERED'],
  ['IN_TRANSIT', 'IN_TRANSIT'],
  ['DELIVERED', 'DELIVERED'],
  ['DELIVERED_TO_WAREHOUSE', 'DELIVERED'],
  ['VERIFIED', 'VERIFIED'],
  ['QUALITY_CHECK_PASSED', 'VERIFIED'],
]);

const normalizeStatusKey = (status) => String(status || '').trim().toUpperCase().replace(/[\s-]+/g, '_');

const normalizeSupplyChainStatus = (status) => STATUS_ALIASES.get(normalizeStatusKey(status)) || 'UNKNOWN';

const getEventTime = (event) => {
  const parsed = Date.parse(event?.timestamp || '');
  return Number.isFinite(parsed) ? parsed : Number.NEGATIVE_INFINITY;
};

const getLatestTrackingEvent = (history) =>
  history
    .map((event, index) => ({ event, index, time: getEventTime(event) }))
    .reduce((latest, candidate) => {
      if (!latest) return candidate;
      if (candidate.time > latest.time) return candidate;
      if (candidate.time === latest.time && candidate.index > latest.index) return candidate;
      return latest;
    }, null)?.event;

function StatusFlow({ status }) {
  return (
    <div className="flex-1 lg:max-w-md bg-background/50 rounded-lg p-4 flex items-center justify-between">
      {SUPPLY_CHAIN_STEPS.map((step, index) => {
        const isActive = step.activeStatuses.includes(status);
        const nextStep = SUPPLY_CHAIN_STEPS[index + 1];
        const isConnectorActive = nextStep?.activeStatuses.includes(status);

        return (
          <div key={step.status} className="contents">
            <div className="flex flex-col items-center">
              <div
                className={cn(
                  'w-12 h-12 rounded-full flex items-center justify-center border-2',
                  isActive ? step.activeClassName : 'border-border bg-muted'
                )}
              >
                {getStatusIcon(step.status)}
              </div>
              <span className="text-xs mt-2 text-muted-foreground">{step.label}</span>
            </div>

            {nextStep && <div className={cn('flex-1 h-1 mx-2', isConnectorActive ? 'bg-primary' : 'bg-border')} />}
          </div>
        );
      })}
    </div>
  );
}

export default function SupplyChain() {
  const [products, setProducts] = useState([]);
  const [totalProducts, setTotalProducts] = useState(0);
  const [totalPages, setTotalPages] = useState(1);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [page, setPage] = useState(1);

  const fetchProducts = useCallback(async () => {
    setLoading(true);
    try {
      const res = await productApi.getPage({ page, pageSize: PAGE_SIZE, search: searchTerm });
      setProducts(res.data.items);
      setTotalProducts(res.data.total);
      setTotalPages(Math.max(1, res.data.total_pages));
    } catch (err) {
      console.error('Failed to load supply chain data', err);
    } finally {
      setLoading(false);
    }
  }, [page, searchTerm]);

  useEffect(() => {
    // Mount-time API load for this route; state updates happen after the async request settles.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    fetchProducts();
  }, [fetchProducts]);

  const getProductStatus = (product) => {
    const history = product.tracking_history || [];
    if (history.length === 0) return 'REGISTERED';
    return normalizeSupplyChainStatus(getLatestTrackingEvent(history)?.status);
  };

  const currentPage = Math.min(page, totalPages);
  const pageStart = (currentPage - 1) * PAGE_SIZE;
  const visibleProducts = products;
  const firstVisible = totalProducts === 0 ? 0 : pageStart + 1;
  const lastVisible = Math.min(pageStart + visibleProducts.length, totalProducts);

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-primary"></div>
      </div>
    );
  }

  return (
    <div className="p-8 max-w-7xl mx-auto text-foreground">
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center mb-8 gap-4">
        <div>
          <h1 data-testid="supply-chain-heading" className="max-w-full text-2xl font-bold leading-tight bg-clip-text text-transparent bg-gradient-to-r from-primary to-emerald-600 mb-2 sm:text-3xl">
            Supply Chain Overview
          </h1>
          <p className="text-muted-foreground">Monitor all agricultural products across the network.</p>
        </div>

        <div className="relative w-full md:w-64">
          <label htmlFor="supply-chain-search" className="sr-only">
            Search products or locations
          </label>
          <Input
            id="supply-chain-search"
            type="text"
            placeholder="Search products or locations..."
            value={searchTerm}
            onChange={(e) => {
              setSearchTerm(e.target.value);
              setPage(1);
            }}
            className={cn(
              'min-h-11 w-full bg-white/5 border border-input rounded-lg pl-10 py-2 text-foreground focus:outline-none focus:border-primary transition-colors',
              searchTerm ? 'pr-12' : 'pr-4'
            )}
          />
          <Search className="w-5 h-5 text-muted-foreground absolute left-3 top-2.5" />
          {searchTerm && (
            <Button
              type="button"
              variant="ghost"
              size="icon"
              onClick={() => {
                setSearchTerm('');
                setPage(1);
              }}
              className="absolute right-1 top-1/2 h-9 w-9 -translate-y-1/2 text-muted-foreground hover:text-foreground"
              aria-label="Clear supply chain search"
              title="Clear search"
            >
              <X className="h-4 w-4" />
            </Button>
          )}
        </div>
      </div>

      <div className="mb-4 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 text-sm text-muted-foreground">
        <span aria-live="polite">
          Showing {firstVisible}-{lastVisible} of {totalProducts} products
        </span>
        <div className="flex items-center gap-2">
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => setPage((value) => Math.max(1, value - 1))}
            disabled={currentPage === 1}
          >
            Previous
          </Button>
          <span className="min-w-20 text-center">
            Page {currentPage} / {totalPages}
          </span>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => setPage((value) => Math.min(totalPages, value + 1))}
            disabled={currentPage === totalPages}
          >
            Next
          </Button>
        </div>
      </div>

      <div className="grid gap-6">
        {visibleProducts.map((product) => {
          const status = getProductStatus(product);

          return (
            <Card key={product.id} className="hover:bg-white/10 transition-colors">
              <CardContent className="p-6">
                <div className="flex flex-col lg:flex-row justify-between gap-6">
                  {/* Product Info */}
                  <div className="flex-1">
                    <div className="flex items-center gap-3 mb-4">
                      <span className="p-2 bg-primary/20 rounded-lg">
                        <Package className="w-6 h-6 text-primary" />
                      </span>
                      <div>
                        <h3 className="text-xl font-bold">{product.name}</h3>
                        <p className="text-sm font-mono text-muted-foreground">ID: {product.id}</p>
                      </div>
                    </div>

                    <div className="grid grid-cols-2 gap-4 mb-4">
                      <div className="flex items-center gap-2 text-muted-foreground">
                        <MapPin className="w-4 h-4" />
                        <span className="text-sm">{product.origin}</span>
                      </div>
                      <div className="flex items-center gap-2 text-muted-foreground">
                        <ShieldCheck className="w-4 h-4 text-primary" />
                        <span className="text-sm">Verified Farm</span>
                      </div>
                    </div>
                  </div>

                  {/* Status Flow */}
                  <StatusFlow status={status} />
                </div>

                <div className="mt-4 pt-4 border-t border-border flex items-center justify-between">
                  <span className="text-sm font-semibold text-muted-foreground">
                    Current Status: <Badge variant="outline" className="ml-2">{getStatusText(status)}</Badge>
                  </span>

                  <Button variant="link" asChild className="text-primary hover:text-primary/80">
                    <a href={`/product/${product.id}`}>View Details →</a>
                  </Button>
                </div>
              </CardContent>
            </Card>
          );
        })}

        {totalProducts === 0 && (
          <Card className="text-center">
            <CardContent className="p-12">
              <Package className="w-12 h-12 text-muted-foreground mx-auto mb-4" />
              <h3 className="text-xl font-semibold text-foreground">No products found</h3>
              <p className="text-muted-foreground mt-2">Try adjusting your search criteria.</p>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}
