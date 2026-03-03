import { Outlet, Link, useLocation } from 'react-router-dom';
import { Sprout, ShieldCheck, Truck, Menu, X, Scan, Thermometer } from 'lucide-react';
import { useState } from 'react';
import { cn } from '../lib/utils';
import { Button } from './ui/Button';

export default function Layout() {
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const location = useLocation();

  const navItems = [
    { name: 'Dashboard', path: '/', icon: Sprout },
    { name: 'Registry', path: '/registry', icon: ShieldCheck },
    { name: 'Supply Chain', path: '/supply-chain', icon: Truck },
    { name: 'Cold-Chain', path: '/cold-chain', icon: Thermometer },
    { name: 'Scanner', path: '/scan', icon: Scan },
  ];

  return (
    <div className="min-h-screen bg-background text-foreground font-sans">
      {/* Navbar */}
      <nav className="fixed top-0 w-full z-50 glass border-b border-border" role="navigation" aria-label="Main navigation">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center gap-2">
              <div className="p-2 bg-primary/20 rounded-lg">
                <ShieldCheck className="w-6 h-6 text-primary" />
              </div>
              <span className="text-xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-primary to-emerald-600">
                AgriGuard
              </span>
            </div>
            
            {/* Desktop Nav */}
            <div className="hidden md:block">
              <div className="ml-10 flex items-baseline space-x-1">
                {navItems.map((item) => {
                  const Icon = item.icon;
                  const isActive = location.pathname === item.path;
                  return (
                    <Link
                      key={item.name}
                      to={item.path}
                      className={cn(
                        'flex items-center gap-2 px-3 py-2 rounded-md text-sm font-medium transition-colors',
                        isActive
                          ? 'bg-primary/20 text-primary border border-primary/30'
                          : 'text-muted-foreground hover:bg-accent hover:text-foreground'
                      )}
                    >
                      <Icon className="w-4 h-4" />
                      {item.name}
                    </Link>
                  );
                })}
              </div>
            </div>

            {/* Mobile menu button */}
            <div className="md:hidden">
              <Button
                variant="ghost"
                size="icon"
                onClick={() => setIsMenuOpen(!isMenuOpen)}
                aria-label={isMenuOpen ? 'Close menu' : 'Open menu'}
                aria-expanded={isMenuOpen}
              >
                {isMenuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
              </Button>
            </div>
          </div>
        </div>

        {/* Mobile Nav */}
        {isMenuOpen && (
          <div className="md:hidden glass border-t border-border">
            <div className="px-2 pt-2 pb-3 space-y-1 sm:px-3">
              {navItems.map((item) => {
                const Icon = item.icon;
                const isActive = location.pathname === item.path;
                return (
                  <Link
                    key={item.name}
                    to={item.path}
                    onClick={() => setIsMenuOpen(false)}
                    className={cn(
                      'flex items-center gap-2 px-3 py-2 rounded-md text-base font-medium transition-colors',
                      isActive
                        ? 'bg-primary/20 text-primary'
                        : 'text-muted-foreground hover:text-foreground hover:bg-accent'
                    )}
                  >
                    <Icon className="w-4 h-4" />
                    {item.name}
                  </Link>
                );
              })}
            </div>
          </div>
        )}
      </nav>

      {/* Main Content */}
      <main className="pt-20 px-4 sm:px-6 lg:px-8 max-w-7xl mx-auto pb-12">
        <Outlet />
      </main>
    </div>
  );
}
