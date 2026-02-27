import { useState, useEffect } from 'react';
import { api } from '../api';
import './SettingsModal.css';

export default function SettingsModal({ isOpen, onClose }) {
    const [apiKey, setApiKey] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const [isSaving, setIsSaving] = useState(false);
    const [error, setError] = useState(null);
    const [success, setSuccess] = useState(false);

    useEffect(() => {
        if (isOpen) {
            loadSettings();
            setSuccess(false);
            setError(null);
        }
    }, [isOpen]);

    const loadSettings = async () => {
        setIsLoading(true);
        try {
            const data = await api.getSettings();
            setApiKey(data.openrouter_api_key || '');
        } catch (err) {
            setError('Failed to load settings from server.');
        } finally {
            setIsLoading(false);
        }
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        setIsSaving(true);
        setError(null);
        setSuccess(false);

        try {
            await api.updateSettings({ openrouter_api_key: apiKey });
            setSuccess(true);
            setTimeout(() => {
                onClose();
            }, 1500);
        } catch (err) {
            setError('Failed to save API key. Please try again.');
        } finally {
            setIsSaving(false);
        }
    };

    if (!isOpen) return null;

    return (
        <div className="settings-overlay">
            <div className="settings-modal flex-col items-center">
                <div className="settings-header">
                    <h2>Configuration</h2>
                    <button className="close-btn" onClick={onClose} aria-label="Close">
                        &times;
                    </button>
                </div>

                <div className="settings-body">
                    {isLoading ? (
                        <div className="settings-loading">
                            <div className="spinner"></div> Loading settings...
                        </div>
                    ) : (
                        <form onSubmit={handleSubmit}>
                            <div className="form-group">
                                <label htmlFor="openrouter-api-key">OpenRouter API Key (.env)</label>
                                <input
                                    type="password"
                                    id="openrouter-api-key"
                                    value={apiKey}
                                    onChange={(e) => setApiKey(e.target.value)}
                                    placeholder="sk-or-v1-..."
                                />
                                <small className="help-text">
                                    This key will be saved directly to your local `.env` file and applied instantly.
                                    It will be used for all models (GPT-4, Claude, Gemini, etc.) via OpenRouter.
                                </small>
                            </div>

                            {error && <div className="settings-alert error">{error}</div>}
                            {success && <div className="settings-alert success">Settings saved successfully!</div>}

                            <div className="form-actions">
                                <button type="button" className="btn-secondary" onClick={onClose} disabled={isSaving}>
                                    Cancel
                                </button>
                                <button type="submit" className="btn-primary" disabled={isSaving}>
                                    {isSaving ? 'Saving...' : 'Save Changes'}
                                </button>
                            </div>
                        </form>
                    )}
                </div>
            </div>
        </div>
    );
}
