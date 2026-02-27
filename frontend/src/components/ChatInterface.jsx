import { useState, useEffect, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import { api } from '../api';
import Stage1 from './Stage1';
import Stage2 from './Stage2';
import Stage3 from './Stage3';
import './ChatInterface.css';

export default function ChatInterface({
  conversation,
  onSendMessage,
  isLoading,
}) {
  const [input, setInput] = useState('');
  const [availableModels, setAvailableModels] = useState([]);
  const [selectedModels, setSelectedModels] = useState([]);
  const messagesEndRef = useRef(null);

  // --- CHANGED --- Fetch available models on mount
  useEffect(() => {
    api.getAvailableModels().then((data) => {
      setAvailableModels(data.council_models || []);
      setSelectedModels(data.council_models || []);
    }).catch(console.error);
  }, []);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [conversation]);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (input.trim() && !isLoading && selectedModels.length >= 2) {
      // --- CHANGED --- Pass selected models to handler
      onSendMessage(input, selectedModels);
      setInput('');
    }
  };

  const toggleModel = (model) => {
    setSelectedModels(prev =>
      prev.includes(model) ? prev.filter(m => m !== model) : [...prev, model]
    );
  };

  const handleExport = () => {
    if (!conversation || !conversation.messages || conversation.messages.length === 0) return;

    let markdown = `# ${conversation.title || 'Conversation Export'}\n\n`;

    conversation.messages.forEach(msg => {
      if (msg.role === 'user') {
        markdown += `## User Query\n\n${msg.content}\n\n`;
      } else if (msg.role === 'assistant') {
        markdown += `## Council Responses\n\n`;

        // Stage 1
        if (msg.stage1 && msg.stage1.length > 0) {
          msg.stage1.forEach(r => {
            markdown += `### ${r.model.split('/').pop()}\n\n${r.response}\n\n`;
          });
        }

        // Stage 2
        if (msg.metadata?.aggregate_rankings) {
          markdown += `## Aggregate Rankings\n\n`;
          msg.metadata.aggregate_rankings.forEach((r, idx) => {
            markdown += `${idx + 1}. **${r.model.split('/').pop()}**: ${r.total_score} pts\n`;
          });
          markdown += `\n`;
        }

        // Stage 3
        if (msg.stage3 && msg.stage3.response) {
          markdown += `## Final Synthesis\n\n${msg.stage3.response}\n\n`;
        }

        markdown += `---\n\n`;
      }
    });

    const blob = new Blob([markdown], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `conversation_${conversation.id || 'export'}.md`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const handleKeyDown = (e) => {
    // Submit on Enter (without Shift)
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  if (!conversation) {
    return (
      <div className="chat-interface">
        <div className="empty-state">
          <h2>Welcome to MetaReasoner</h2>
          <p>Create a new conversation to get started</p>
        </div>
      </div>
    );
  }

  return (
    <div className="chat-interface">
      <div className="messages-container">
        {conversation.messages.length > 0 && (
          <button
            className="export-btn"
            onClick={handleExport}
          >
            Export to MD
          </button>
        )}

        {conversation.messages.length === 0 ? (
          <div className="empty-state">
            <h2>Start a conversation</h2>
            <p>Ask a question to consult MetaReasoner</p>
          </div>
        ) : (
          conversation.messages.map((msg, index) => (
            <div key={index} className="message-group">
              {msg.role === 'user' ? (
                <div className="user-message">
                  <div className="message-label">You</div>
                  <div className="message-content">
                    <div className="markdown-content">
                      <ReactMarkdown>{msg.content}</ReactMarkdown>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="assistant-message">
                  <div className="message-label">MetaReasoner</div>

                  {/* Stage 1 */}
                  {msg.loading?.stage1 && (
                    <div className="stage-loading">
                      <div className="spinner"></div>
                      <span>Running Stage 1: Collecting individual responses...</span>
                    </div>
                  )}
                  {msg.stage1 && <Stage1 responses={msg.stage1} metadata={msg.metadata} />}

                  {/* Stage 2 */}
                  {msg.loading?.stage2 && (
                    <div className="stage-loading">
                      <div className="spinner"></div>
                      <span>Running Stage 2: Peer rankings...</span>
                    </div>
                  )}
                  {msg.stage2 && (
                    <Stage2
                      rankings={msg.stage2}
                      labelToModel={msg.metadata?.label_to_model}
                      aggregateRankings={msg.metadata?.aggregate_rankings}
                    />
                  )}

                  {/* Stage 3 */}
                  {msg.loading?.stage3 && (
                    <div className="stage-loading">
                      <div className="spinner"></div>
                      <span>Running Stage 3: Final synthesis...</span>
                    </div>
                  )}
                  {msg.stage3 && <Stage3 finalResponse={msg.stage3} />}
                </div>
              )}
            </div>
          ))
        )}

        {isLoading && (
          <div className="loading-indicator">
            <div className="spinner"></div>
            <span>Consulting the council...</span>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* --- CHANGED --- Added Model Selector Panel */}
      <div className="model-selector-panel">
        <div className="model-selector-header">Select Council Models:</div>
        <div className="model-badges">
          {availableModels.map(model => (
            <label key={model} className="model-badge">
              <input
                type="checkbox"
                checked={selectedModels.includes(model)}
                onChange={() => toggleModel(model)}
                disabled={isLoading}
              />
              {model.split('/').pop()}
            </label>
          ))}
        </div>
        {selectedModels.length < 2 && (
          <div className="model-warning">
            Warning: At least 2 models must be selected for consensus to work.
          </div>
        )}
      </div>

      {/* Always render the input form allowing endless multi-turn conversations */}
      <form className="input-form" onSubmit={handleSubmit}>
        <textarea
          className="message-input"
          placeholder="Ask your question... (Shift+Enter for new line, Enter to send)"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={isLoading}
          rows={3}
        />
        <button
          type="submit"
          className="send-button"
          disabled={!input.trim() || isLoading || selectedModels.length < 2}
        >
          Send
        </button>
      </form>
    </div>
  );
}
