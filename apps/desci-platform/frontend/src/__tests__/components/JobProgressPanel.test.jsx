/* global describe, it, expect */
import { render, screen } from '@testing-library/react';
import JobProgressPanel from '../../components/JobProgressPanel';

describe('JobProgressPanel', () => {
  it('renders title, message, status, and clamped progress', () => {
    render(
      <JobProgressPanel
        title="Collecting"
        job={{
          status: 'running',
          progress: 42,
          message: 'Pulling NTIS notices',
          type: 'notice_collection',
          storage: 'redis',
        }}
      />,
    );

    expect(screen.getByText('Collecting')).toBeDefined();
    expect(screen.getByText('Pulling NTIS notices')).toBeDefined();
    expect(screen.getByText('42%')).toBeDefined();
    expect(screen.getByText('running')).toBeDefined();
    expect(screen.getByText('notice_collection')).toBeDefined();
    expect(screen.getByText('Redis synced')).toBeDefined();
  });

  it('clamps progress above 100 to 100 and shows Local task when storage is missing', () => {
    render(<JobProgressPanel title="X" job={{ status: 'running', progress: 150 }} />);
    expect(screen.getByText('100%')).toBeDefined();
    expect(screen.getByText('Local task')).toBeDefined();
  });

  it('clamps negative progress to 0 and tolerates missing job fields', () => {
    render(<JobProgressPanel title="Idle" job={{ progress: -20 }} />);
    expect(screen.getByText('0%')).toBeDefined();
  });

  it('omits the icon when icon prop is false', () => {
    const { container } = render(
      <JobProgressPanel title="No-Icon" job={{ status: 'queued', progress: 0 }} icon={false} />,
    );
    expect(container.querySelector('.bg-primary\\/15')).toBeNull();
  });
});
