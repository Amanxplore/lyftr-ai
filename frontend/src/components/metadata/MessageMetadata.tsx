import type { ChatMetadata } from '../../types/chat';

interface MessageMetadataProps {
  metadata: ChatMetadata;
}

export function MessageMetadata({ metadata }: MessageMetadataProps) {
  const isCache = metadata.resolution_source === 'LLM_CACHE';

  return (
    <div className="meta-bar">
      <span
        data-testid="meta-source"
        className={`meta-pill ${isCache ? 'source-cache' : 'source-live'}`}
      >
        {metadata.resolution_source}
      </span>

      <span className="meta-pill">
        Model: <strong data-testid="meta-model">{metadata.model}</strong>
      </span>

      <span className="meta-pill">
        Latency: <strong data-testid="meta-latency">{metadata.latency_ms} ms</strong>
      </span>

      <span className="meta-pill">
        In: <strong data-testid="meta-input-tokens">{metadata.input_tokens}</strong>
      </span>

      <span className="meta-pill">
        Out: <strong data-testid="meta-output-tokens">{metadata.output_tokens}</strong>
      </span>

      {metadata.key_id && (
        <span className="meta-pill">
          Key: <strong>{metadata.key_id}</strong>
        </span>
      )}

      {metadata.fallback_attempts > 0 && (
        <span className="meta-pill failover">
          Failover &times;{metadata.fallback_attempts}
        </span>
      )}
    </div>
  );
}
