import React, { useState, useEffect } from 'react';
import { Package, Truck, CheckCircle, Factory, ShieldCheck, MapPin, Search } from 'lucide-react';
import { productApi } from '../services/api';

export default function SupplyChain() {
  const [products, setProducts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');

  useEffect(() => {
    fetchProducts();
  }, []); // Intentionally empty to run once, defined below

  const fetchProducts = async () => {
    try {
      const res = await productApi.getAll();
      // Filter out products that are created but haven't started transit if necessary,
      // or just show all. Here we assume we show all.
      setProducts(res.data);
    } catch (err) {
      console.error('Failed to load supply chain data', err);
    } finally {
      setLoading(false);
    }
  };

  const getProductStatus = (product) => {
    const history = product.tracking_history || [];
    if (history.length === 0) return 'REGISTERED';
    return history[history.length - 1].status || 'REGISTERED';
  };

  const filteredProducts = products.filter(
    (p) =>
      p.id.toLowerCase().includes(searchTerm.toLowerCase()) ||
      p.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      (p.origin || '').toLowerCase().includes(searchTerm.toLowerCase())
  );

  const getStatusIcon = (status) => {
    switch (status) {
      case 'REGISTERED':
        return <Factory className="w-5 h-5 text-blue-400" />;
      case 'IN_TRANSIT':
        return <Truck className="w-5 h-5 text-orange-400" />;
      case 'DELIVERED':
      case 'VERIFIED':
        return <CheckCircle className="w-5 h-5 text-green-400" />;
      default:
        return <Package className="w-5 h-5 text-gray-400" />;
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

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-green-500"></div>
      </div>
    );
  }

  return (
    <div className="p-8 max-w-7xl mx-auto text-white">
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center mb-8 gap-4">
        <div>
          <h1 className="text-3xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-green-400 to-emerald-600 mb-2">
            Supply Chain Overview
          </h1>
          <p className="text-gray-400">Monitor all agricultural products across the network.</p>
        </div>

        <div className="relative w-full md:w-64">
          <input
            type="text"
            placeholder="Search products or locations..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full bg-white/5 border border-white/10 rounded-lg pl-10 pr-4 py-2 text-white focus:outline-none focus:border-green-500 transition-colors"
          />
          <Search className="w-5 h-5 text-gray-400 absolute left-3 top-2.5" />
        </div>
      </div>

      <div className="grid gap-6">
        {filteredProducts.map((product) => (
          <div
            key={product.id}
            className="bg-white/5 border border-white/10 rounded-xl p-6 hover:bg-white/10 transition-colors"
          >
            <div className="flex flex-col lg:flex-row justify-between gap-6">
              {/* Product Info */}
              <div className="flex-1">
                <div className="flex items-center gap-3 mb-4">
                  <span className="p-2 bg-green-500/20 rounded-lg">
                    <Package className="w-6 h-6 text-green-400" />
                  </span>
                  <div>
                    <h3 className="text-xl font-bold">{product.name}</h3>
                    <p className="text-sm font-mono text-gray-400">ID: {product.id}</p>
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4 mb-4">
                  <div className="flex items-center gap-2 text-gray-300">
                    <MapPin className="w-4 h-4 text-gray-500" />
                    <span className="text-sm">{product.origin}</span>
                  </div>
                  <div className="flex items-center gap-2 text-gray-300">
                    <ShieldCheck className="w-4 h-4 text-green-500" />
                    <span className="text-sm">Verified Farm</span>
                  </div>
                </div>
              </div>

              {/* Status Flow */}
              {(() => { const status = getProductStatus(product); return (
              <div className="flex-1 lg:max-w-md bg-black/20 rounded-lg p-4 flex items-center justify-between">
                <div className="flex flex-col items-center">
                  <div
                    className={`w-12 h-12 rounded-full flex items-center justify-center border-2 ${
                      status === 'REGISTERED' || status === 'IN_TRANSIT' || status === 'DELIVERED' || status === 'VERIFIED'
                        ? 'border-green-500 bg-green-500/20'
                        : 'border-gray-600 bg-gray-800'
                    }`}
                  >
                    {getStatusIcon('REGISTERED')}
                  </div>
                  <span className="text-xs mt-2 text-gray-400">Farm</span>
                </div>

                <div
                  className={`flex-1 h-1 mx-2 ${
                    status === 'IN_TRANSIT' || status === 'DELIVERED' || status === 'VERIFIED'
                      ? 'bg-green-500'
                      : 'bg-gray-700'
                  }`}
                />

                <div className="flex flex-col items-center">
                  <div
                    className={`w-12 h-12 rounded-full flex items-center justify-center border-2 ${
                      status === 'IN_TRANSIT' || status === 'DELIVERED' || status === 'VERIFIED'
                        ? 'border-orange-500 bg-orange-500/20'
                        : 'border-gray-600 bg-gray-800'
                    }`}
                  >
                    {getStatusIcon('IN_TRANSIT')}
                  </div>
                  <span className="text-xs mt-2 text-gray-400">Transit</span>
                </div>

                <div
                  className={`flex-1 h-1 mx-2 ${
                    status === 'DELIVERED' || status === 'VERIFIED'
                      ? 'bg-green-500'
                      : 'bg-gray-700'
                  }`}
                />

                <div className="flex flex-col items-center">
                  <div
                    className={`w-12 h-12 rounded-full flex items-center justify-center border-2 ${
                      status === 'DELIVERED' || status === 'VERIFIED'
                        ? 'border-blue-500 bg-blue-500/20'
                        : 'border-gray-600 bg-gray-800'
                    }`}
                  >
                    {getStatusIcon('DELIVERED')}
                  </div>
                  <span className="text-xs mt-2 text-gray-400">Delivered</span>
                </div>
              </div>
              ); })()}
            </div>
            
            <div className="mt-4 pt-4 border-t border-white/5 flex items-center justify-between">
                <span className="text-sm font-semibold text-gray-300">
                    Current Status: <span className="text-white ml-2">{getStatusText(getProductStatus(product))}</span>
                </span>
                
                <a href={`/product/${product.id}`} className="text-sm font-bold text-green-400 hover:text-green-300 transition-colors flex items-center gap-1">
                    View Details →
                </a>
            </div>
          </div>
        ))}

        {filteredProducts.length === 0 && (
          <div className="text-center p-12 bg-white/5 border border-white/10 rounded-xl">
            <Package className="w-12 h-12 text-gray-500 mx-auto mb-4" />
            <h3 className="text-xl font-semibold text-gray-300">No products found</h3>
            <p className="text-gray-500 mt-2">Try adjusting your search criteria.</p>
          </div>
        )}
      </div>
    </div>
  );
}
