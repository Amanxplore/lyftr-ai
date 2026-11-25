import { KeyboardEvent, useState } from 'react';
import { Send } from 'lucide-react';

interface ChatComposerProps {
  isSending: boolean;
  onSend: (message: string) => Promise<void>;
}

export function ChatComposer({ isSending, onSend }: ChatComposerProps) {
  const [draft, setDraft] = useState('');

  const handleSubmit = async () => {
    if (isSending || draft.length === 0) {
      return;
    }
    const toSend = draft;
    setDraft('');
    await onSend(toSend);
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      void handleSubmit();
    }
  };

  return (
    <div className="composer-bar">
      <div className="composer-inner">
        <textarea
          data-testid="chat-input"
          className="composer-textarea"
          placeholder="Ask anything... (Enter to send, Shift+Enter for newline)"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={handleKeyDown}
          rows={1}
          disabled={isSending}
        />
        <button
          data-testid="send-button"
          type="button"
          className="btn btn-primary"
          onClick={() => void handleSubmit()}
          disabled={isSending || draft.length === 0}
        >
          <Send size={15} />
          Send
        </button>
      </div>
      <div className="composer-footer">
        <span>History persists in SQLite per session</span>
        <span>{draft.trim().length} / 4000 chars</span>
      </div>
    </div>
  );
}
