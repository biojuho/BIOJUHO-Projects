/* global beforeEach, describe, expect, it */
import { fireEvent, render, screen } from '@testing-library/react';
import { LocaleProvider, useLocale } from '../../contexts/LocaleContext';

function LocaleProbe() {
  const { locale, outputLanguage, setLocale, toggleLocale } = useLocale();

  return (
    <div>
      <div data-testid="locale">{locale}</div>
      <div data-testid="output">{outputLanguage}</div>
      <button type="button" onClick={() => setLocale('en-US')}>set-en</button>
      <button type="button" onClick={toggleLocale}>toggle</button>
    </div>
  );
}

describe('LocaleContext', () => {
  beforeEach(() => {
    window.localStorage.clear();
    document.documentElement.lang = '';
  });

  it('defaults to Korean locale and output language', () => {
    render(
      <LocaleProvider>
        <LocaleProbe />
      </LocaleProvider>,
    );

    expect(screen.getByTestId('locale').textContent).toBe('ko-KR');
    expect(screen.getByTestId('output').textContent).toBe('ko');
    expect(window.localStorage.getItem('dsci.locale')).toBe('ko-KR');
    expect(window.localStorage.getItem('dsci.outputLanguage')).toBe('ko');
    expect(document.documentElement.lang).toBe('ko-KR');
  });

  it('persists locale changes and updates output language', () => {
    render(
      <LocaleProvider>
        <LocaleProbe />
      </LocaleProvider>,
    );

    fireEvent.click(screen.getByText('set-en'));

    expect(screen.getByTestId('locale').textContent).toBe('en-US');
    expect(screen.getByTestId('output').textContent).toBe('en');
    expect(window.localStorage.getItem('dsci.locale')).toBe('en-US');
    expect(window.localStorage.getItem('dsci.outputLanguage')).toBe('en');
    expect(document.documentElement.lang).toBe('en-US');
  });
});
