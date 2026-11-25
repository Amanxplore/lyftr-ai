import { useCallback, useEffect, useState } from 'react';
import { createMessageId, createSessionId } from '../lib/session';
import {
  ApiError,
  fetchHealth,
  fetchSessionMessages,
  sendChatMessage,
} from '../services/api';
import type {
  HealthResponsePayload,
  UiChatMessage,
} from '../types/chat';

export function useChatSession() {
  // Always start a brand-new session on each page load
  const [sessionId, setSessionId] = useState<string>(() => createSessionId());
  const [messages, setMessages] = useState<UiChatMessage[]>([]);
  const [systemPrompt, setSystemPrompt] = useState<string>('');
  const [simulateFailure, setSimulateFailure] = useState<string>('');
  const [isSending, setIsSending] = useState<boolean>(false);
  const [health, setHealth] = useState<HealthResponsePayload | null>(null);
  const [healthError, setHealthError] = useState<string | null>(null);

  const refreshHealth = useCallback(async () => {
    try {
      const data = await fetchHealth();
      setHealth(data);
      setHealthError(null);
    } catch (err) {
      setHealth(null);
      setHealthError(
        err instanceof Error ? err.message : 'Backend unreachable'
      );
    }
  }, []);

  useEffect(() => {
    void refreshHealth();
  }, [refreshHealth]);

  const sendMessage = useCallback(
    async (rawMessage: string) => {
      if (isSending) {
        return;
      }

      const trimmed = rawMessage.trim();
      const displayUserText = trimmed || rawMessage;

      const userEntry: UiChatMessage = {
        id: createMessageId(),
        role: 'user',
        content: displayUserText,
        createdAt: new Date().toISOString(),
      };

      setMessages((prev) => [...prev, userEntry]);
      setIsSending(true);

      try {
        const response = await sendChatMessage(
          {
            session_id: sessionId,
            message: rawMessage,
            ...(systemPrompt.trim()
              ? { system_prompt: systemPrompt.trim() }
              : {}),
          },
          simulateFailure
        );

        const assistantEntry: UiChatMessage = {
          id: createMessageId(),
          role: 'assistant',
          content: response.reply,
          metadata: response.metadata,
          createdAt: new Date().toISOString(),
        };

        setMessages((prev) => [...prev, assistantEntry]);
      } catch (err) {
        const statusCode = err instanceof ApiError ? err.statusCode : undefined;
        const detail =
          err instanceof Error
            ? err.message
            : 'Unexpected error communicating with backend';

        const errorEntry: UiChatMessage = {
          id: createMessageId(),
          role: 'error',
          content: detail,
          statusCode,
          failedPrompt: statusCode === 422 ? undefined : rawMessage,
          createdAt: new Date().toISOString(),
        };

        setMessages((prev) => [...prev, errorEntry]);
      } finally {
        setIsSending(false);
      }
    },
    [isSending, sessionId, simulateFailure, systemPrompt]
  );

  const startNewSession = useCallback(() => {
    setSessionId(createSessionId());
    setMessages([]);
  }, []);

  const reloadSessionFromServer = useCallback(async () => {
    try {
      const data = await fetchSessionMessages(sessionId);
      const hydrated: UiChatMessage[] = data.messages.map((m) => {
        if (m.role === 'user') {
          return {
            id: createMessageId(),
            role: 'user',
            content: m.content,
            createdAt: new Date().toISOString(),
          };
        }
        return {
          id: createMessageId(),
          role: 'assistant',
          content: m.content,
          metadata: {
            resolution_source: m.metadata?.resolution_source ?? 'LIVE_INFERENCE',
            model: m.metadata?.model ?? 'unknown',
            latency_ms: m.metadata?.latency_ms ?? 0,
            input_tokens: m.metadata?.input_tokens ?? 0,
            output_tokens: m.metadata?.output_tokens ?? 0,
            key_id: m.metadata?.key_id ?? null,
            fallback_attempts: m.metadata?.fallback_attempts ?? 0,
          },
          createdAt: new Date().toISOString(),
        };
      });
      setMessages(hydrated);
    } catch (err) {
      const statusCode = err instanceof ApiError ? err.statusCode : undefined;
      const detail =
        err instanceof Error ? err.message : 'Unable to fetch session history';
      setMessages((prev) => [
        ...prev,
        {
          id: createMessageId(),
          role: 'error',
          content: detail,
          statusCode,
          createdAt: new Date().toISOString(),
        },
      ]);
    }
  }, [sessionId]);

  return {
    sessionId,
    messages,
    systemPrompt,
    setSystemPrompt,
    simulateFailure,
    setSimulateFailure,
    isSending,
    health,
    healthError,
    refreshHealth,
    sendMessage,
    startNewSession,
    reloadSessionFromServer,
  };
}
