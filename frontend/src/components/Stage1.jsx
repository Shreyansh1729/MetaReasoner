import { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import './Stage1.css';

export default function Stage1({ responses }) {
  const [activeTab, setActiveTab] = useState(0);

  if (!responses || responses.length === 0) {
    return null;
  }

  return (
    <div className="stage stage1">
      {/* --- CHANGED --- Added active council badges to the header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '16px' }}>
        <h3 className="stage-title" style={{ margin: 0 }}>Stage 1: Individual Responses</h3>
        <div className="active-council-badges" style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
          {responses.map((resp, idx) => (
            <span key={idx} className="council-badge" style={{
              fontSize: '0.7em',
              padding: '2px 8px',
              background: '#e0e7ff',
              color: '#3730a3',
              borderRadius: '12px',
              fontWeight: 600
            }}>
              {resp.model.split('/').pop()}
            </span>
          ))}
        </div>
      </div>

      <div className="tabs">
        {responses.map((resp, index) => (
          <button
            key={index}
            className={`tab ${activeTab === index ? 'active' : ''}`}
            onClick={() => setActiveTab(index)}
          >
            {resp.model.split('/')[1] || resp.model}
          </button>
        ))}
      </div>

      <div className="tab-content">
        <div className="model-name">{responses[activeTab].model}</div>
        <div className="response-text markdown-content">
          <ReactMarkdown>{responses[activeTab].response}</ReactMarkdown>
        </div>
      </div>
    </div>
  );
}
