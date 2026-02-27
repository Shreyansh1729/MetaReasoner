import ReactMarkdown from 'react-markdown';
import './Stage3.css';

export default function Stage3({ finalResponse, validationStatus }) {
  if (!finalResponse) {
    return null;
  }

  return (
    <div className="stage stage3">
      <h3 className="stage-title">Stage 3: Final Council Answer</h3>
      <div className="final-response">
        <div className="chairman-label" style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <span>Chairman: {finalResponse.model.includes('/') ? finalResponse.model.split('/')[1] : finalResponse.model}</span>
          {validationStatus && validationStatus.triggered !== undefined && (
            <span className={`validation-badge ${validationStatus.triggered ? 'revised' : 'validated'}`}>
              {validationStatus.triggered ? '⚠ Revised after validation' : '✓ Validated by council'}
            </span>
          )}
        </div>
        <div className="final-text markdown-content">
          <ReactMarkdown>{finalResponse.response}</ReactMarkdown>
        </div>
      </div>
    </div>
  );
}
