export type ResolutionSource = 'LIVE_INFERENCE' | 'LLM_CACHE';

export interface ChatMetadata {
  resolution_source: ResolutionSource;
  model: string;
  latency_ms: number;
  input_tokens: number;
  output_tokens: number;
  key_id: string | null;
  fallback_attempts: number;
}

export interface ChatRequestPayload {
  session_id: string;
  message: string;
  system_prompt?: string;
}

export interface ChatResponsePayload {
  session_id: string;
  reply: string;
  metadata: ChatMetadata;
}

export interface HealthResponsePayload {
  status: string;
  keys_configured: number;
  cache_enabled: boolean;
}

export interface SessionHistoryMessage {
  role: 'user' | 'assistant';
  content: string;
  metadata?: Partial<ChatMetadata> & {
    resolution_source: ResolutionSource;
    input_tokens: number;
    output_tokens: number;
  };
}

export interface SessionMessagesResponsePayload {
  session_id: string;
  messages: SessionHistoryMessage[];
}

export interface UiChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'error';
  content: string;
  metadata?: ChatMetadata;
  statusCode?: number;
  failedPrompt?: string;
  createdAt: string;
}
