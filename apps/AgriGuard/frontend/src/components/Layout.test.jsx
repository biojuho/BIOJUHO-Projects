import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import Layout from './Layout';

function renderLayout() {
  return render(
    <MemoryRouter initialEntries={['/sensor-devices']}>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route path="sensor-devices" element={<div>Sensor content</div>} />
        </Route>
      </Routes>
    </MemoryRouter>,
  );
}

describe('Layout', () => {
  it('keeps fixed navigation opaque over scrolled mobile content', () => {
    renderLayout();

    const nav = screen.getByRole('navigation', { name: /main navigation/i });
    expect(nav).toHaveClass('bg-background');
    expect(nav).toHaveClass('shadow-black/20');
    expect(nav).not.toHaveClass('glass');
    expect(screen.getByRole('link', { name: /dashboard/i })).toHaveClass('min-h-11');

    fireEvent.click(screen.getByRole('button', { name: /open menu/i }));

    const mobileMenu = screen.getByTestId('mobile-nav-menu');
    expect(mobileMenu).toHaveClass('bg-background');
    expect(mobileMenu).not.toHaveClass('glass');
  });
});
