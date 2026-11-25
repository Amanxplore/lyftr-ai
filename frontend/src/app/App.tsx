import { ChatComposer } from '../components/chat/ChatComposer';
import { MessageList } from '../components/chat/MessageList';
import { Header } from '../components/layout/Header';
import { GatewayPanel } from '../components/settings/GatewayPanel';
import { useChatSession } from '../hooks/useChatSession';

export function App() {
  const {
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
  } = useChatSession();

  return (
    <div className="app-shell">
      <Header
        health={health}
        healthError={healthError}
        onRefreshHealth={() => void refreshHealth()}
        onNewSession={startNewSession}
      />

      <div className="workspace-grid">
        <GatewayPanel
          sessionId={sessionId}
          systemPrompt={systemPrompt}
          onSystemPromptChange={setSystemPrompt}
          simulateFailure={simulateFailure}
          onSimulateFailureChange={setSimulateFailure}
          onReloadSession={() => void reloadSessionFromServer()}
        />

        <main className="chat-main">
          <MessageList
            messages={messages}
            isSending={isSending}
            onSelectSuggestion={(text) => void sendMessage(text)}
            onRetryPrompt={(text) => void sendMessage(text)}
          />
          <ChatComposer isSending={isSending} onSend={sendMessage} />
        </main>
      </div>
    </div>
  );
}

export default App;
