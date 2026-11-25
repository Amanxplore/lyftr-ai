import { Plus, RefreshCw } from 'lucide-react';
import type { HealthResponsePayload } from '../../types/chat';

interface HeaderProps {
  health: HealthResponsePayload | null;
  healthError: string | null;
  onRefreshHealth: () => void;
  onNewSession: () => void;
}

export function Header({
  health,
  healthError,
  onRefreshHealth,
  onNewSession,
}: HeaderProps) {
  return (
    <header className="app-header">
      <div className="brand">
        <div className="brand-mark">LA</div>
        <div>
          <h1 className="brand-title">Lyftr AI Gateway</h1>
          <p className="brand-subtitle">
            Multi-turn chat with LiteLLM key failover &amp; response caching
          </p>
        </div>
      </div>

      <div className="header-actions">
        <div
          className="status-pill"
          title={
            health
              ? `Gateway OK • ${health.keys_configured} keys • Cache ${health.cache_enabled ? 'on' : 'off'}`
              : healthError || 'Checking gateway...'
          }
        >
          <span className={`status-dot ${health ? 'ok' : healthError ? 'err' : ''}`} />
          {health ? (
            <span>
              {health.keys_configured} keys &middot; cache:{' '}
              {health.cache_enabled ? 'on' : 'off'}
            </span>
          ) : (
            <span>{healthError ? 'gateway offline' : 'connecting...'}</span>
          )}
        </div>

        <button
          type="button"
          className="btn"
          onClick={onRefreshHealth}
          title="Refresh gateway health"
        >
          <RefreshCw size={14} />
          Health
        </button>

        <button type="button" className="btn" onClick={onNewSession}>
          <Plus size={14} />
          New Session
        </button>
      </div>
    </header>
  );
}
