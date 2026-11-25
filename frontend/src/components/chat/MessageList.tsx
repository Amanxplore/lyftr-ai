import { useEffect, useRef } from 'react';
import { AlertTriangle, Loader2, RotateCcw } from 'lucide-react';
import type { UiChatMessage } from '../../types/chat';
import { MessageMetadata } from '../metadata/MessageMetadata';

interface MessageListProps {
  messages: UiChatMessage[];
  isSending: boolean;
  onSelectSuggestion: (text: string) => void;
  onRetryPrompt: (text: string) => void;
}

const SUGGESTIONS = [
  'What is the capital of France?',
  'Explain circuit breakers in 3 bullet points.',
  'Write a haiku about resilient distributed systems.',
];

export function MessageList({
  messages,
  isSending,
  onSelectSuggestion,
  onRetryPrompt,
}: MessageListProps) {
  const bottomRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isSending]);

  if (messages.length === 0 && !isSending) {
    return (
      <div className="message-stream">
        <div className="empty-state">
          <h2>Start a Multi-Turn Conversation</h2>
          <p>
            Every reply displays its resolution source (<code>LIVE_INFERENCE</code> or{' '}
            <code>LLM_CACHE</code>), answering model, server latency, and per-request
            token usage.
          </p>
          <div className="suggestion-row">
            {SUGGESTIONS.map((prompt) => (
              <button
                key={prompt}
                type="button"
                className="suggestion-chip"
                onClick={() => onSelectSuggestion(prompt)}
              >
                {prompt}
              </button>
            ))}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="message-stream">
      {messages.map((msg) => {
        if (msg.role === 'user') {
          return (
            <div key={msg.id} className="msg-row user">
              <span className="msg-role-label">You</span>
              <div className="msg-bubble user">{msg.content}</div>
            </div>
          );
        }

        if (msg.role === 'error') {
          return (
            <div key={msg.id} className="msg-row error" role="alert">
              <span className="msg-role-label">Gateway Error</span>
              <div className="msg-bubble error">
                <div className="error-header">
                  <AlertTriangle size={15} />
                  <span>
                    {msg.statusCode ? `HTTP ${msg.statusCode}` : 'Request Error'}
                  </span>
                </div>
                <div>{msg.content}</div>
                {msg.failedPrompt && (
                  <button
                    type="button"
                    className="btn"
                    style={{ marginTop: 10 }}
                    disabled={isSending}
                    onClick={() => onRetryPrompt(msg.failedPrompt!)}
                  >
                    <RotateCcw size={13} />
                    Retry
                  </button>
                )}
              </div>
            </div>
          );
        }

        return (
          <div
            key={msg.id}
            data-testid="assistant-message"
            className="msg-row assistant"
          >
            <span className="msg-role-label">Assistant</span>
            <div className="msg-bubble assistant">
              <div>{msg.content}</div>
              {msg.metadata && <MessageMetadata metadata={msg.metadata} />}
            </div>
          </div>
        );
      })}

      {isSending && (
        <div className="msg-row assistant">
          <div className="msg-bubble assistant typing-indicator">
            <Loader2 size={15} className="spin" />
            <span>Running LiteLLM gateway inference...</span>
          </div>
        </div>
      )}

      <div ref={bottomRef} />
    </div>
  );
}
