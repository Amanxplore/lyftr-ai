import { Database, ShieldAlert } from 'lucide-react';

interface GatewayPanelProps {
  sessionId: string;
  systemPrompt: string;
  onSystemPromptChange: (value: string) => void;
  simulateFailure: string;
  onSimulateFailureChange: (value: string) => void;
  onReloadSession: () => void;
}

export function GatewayPanel({
  sessionId,
  systemPrompt,
  onSystemPromptChange,
  simulateFailure,
  onSimulateFailureChange,
  onReloadSession,
}: GatewayPanelProps) {
  return (
    <aside className="gateway-sidebar">
      <div className="panel-section">
        <span className="panel-label">Active Session</span>
        <div className="session-chip">
          <span>{sessionId}</span>
        </div>
        <button
          type="button"
          className="btn"
          onClick={onReloadSession}
          title="Load persisted turns from SQLite via GET /sessions/{id}/messages"
        >
          <Database size={14} />
          Verify SQLite History
        </button>
        <p className="field-hint">
          A fresh session starts automatically on every page load.
        </p>
      </div>

      <div className="panel-section">
        <label htmlFor="system-prompt-input" className="panel-label">
          System Prompt (Optional)
        </label>
        <textarea
          id="system-prompt-input"
          data-testid="system-prompt-input"
          className="field-textarea"
          placeholder="Override the default assistant system prompt for this session..."
          value={systemPrompt}
          onChange={(e) => onSystemPromptChange(e.target.value)}
        />
        <p className="field-hint">
          Included in the LiteLLM cache key and persisted per session, never shown in
          message history.
        </p>
      </div>

      <div className="panel-section">
        <label htmlFor="simulate-failure-select" className="panel-label">
          <ShieldAlert size={12} style={{ verticalAlign: '-1px', marginRight: 4 }} />
          Failover Test Hook (X-Simulate-Failure)
        </label>
        <select
          id="simulate-failure-select"
          className="field-select"
          value={simulateFailure}
          onChange={(e) => onSimulateFailureChange(e.target.value)}
        >
          <option value="">None (Normal Routing)</option>
          <option value="key_1=429">key_1=429 (Failover to key_2)</option>
          <option value="key_1=500">key_1=500 (Failover to key_2)</option>
          <option value="*=429">*=429 (All Keys Fail &rarr; 503)</option>
        </select>
        <p className="field-hint">
          Honored when backend has <code>ENABLE_FAILURE_SIMULATION=true</code>.
        </p>
      </div>
    </aside>
  );
}
