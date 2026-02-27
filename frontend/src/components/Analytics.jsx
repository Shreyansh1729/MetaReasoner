import { useState, useEffect } from 'react';
import { api } from '../api';
import './Analytics.css';

export default function Analytics() {
    const [data, setData] = useState(null);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState(null);

    useEffect(() => {
        const fetchAnalytics = async () => {
            try {
                const response = await fetch('http://localhost:8000/api/analytics');
                if (!response.ok) {
                    throw new Error('Failed to fetch analytics');
                }
                const analyticsData = await response.json();
                setData(analyticsData);
            } catch (err) {
                setError(err.message);
            } finally {
                setIsLoading(false);
            }
        };

        fetchAnalytics();
    }, []);

    if (isLoading) {
        return (
            <div className="analytics-container loading">
                <div className="spinner"></div>
                <p>Loading analytics...</p>
            </div>
        );
    }

    if (error) {
        return (
            <div className="analytics-container error">
                <h2>Error Loading Analytics</h2>
                <p>{error}</p>
            </div>
        );
    }

    return (
        <div className="analytics-container">
            <div className="analytics-header">
                <h2>MetaReasoner Analytics</h2>
                <p>Total Conversations: <strong>{data.total_conversations}</strong></p>
            </div>

            <div className="analytics-section">
                <h3>Model Leaderboard (Elo Rating)</h3>
                <p className="analytics-description">
                    Rankings are calculated using standard K=32 pairwise Elo updates based on peer evaluations in Stage 2.
                </p>
                <div className="table-responsive">
                    <table className="analytics-table leaderboard-table">
                        <thead>
                            <tr>
                                <th>Rank</th>
                                <th>Model</th>
                                <th>Elo Rating</th>
                                <th>Wins</th>
                                <th>Losses</th>
                                <th>Appearances</th>
                            </tr>
                        </thead>
                        <tbody>
                            {data.elo_ratings.map((model, index) => (
                                <tr key={model.model} className={index === 0 ? 'top-rank' : ''}>
                                    <td>{index + 1}</td>
                                    <td className="model-name">{model.model.split('/').pop()}</td>
                                    <td className="elo-score">{model.elo}</td>
                                    <td className="wins">{model.wins}</td>
                                    <td className="losses">{model.losses}</td>
                                    <td>{model.appearances}</td>
                                </tr>
                            ))}
                            {data.elo_ratings.length === 0 && (
                                <tr>
                                    <td colSpan="6" className="empty-row">No peer evaluations recorded yet.</td>
                                </tr>
                            )}
                        </tbody>
                    </table>
                </div>
            </div>

            <div className="analytics-section">
                <h3>Cost & Usage Summary</h3>
                <p className="analytics-description">
                    Total tokens processed by each model across all conversations.
                </p>
                <div className="table-responsive">
                    <table className="analytics-table cost-table">
                        <thead>
                            <tr>
                                <th>Model</th>
                                <th>Tokens In</th>
                                <th>Tokens Out</th>
                                <th>Total Tokens</th>
                            </tr>
                        </thead>
                        <tbody>
                            {data.cost_summary
                                .sort((a, b) => (b.total_tokens_in + b.total_tokens_out) - (a.total_tokens_in + a.total_tokens_out))
                                .map((model) => (
                                    <tr key={model.model}>
                                        <td className="model-name">{model.model.split('/').pop()}</td>
                                        <td>{model.total_tokens_in.toLocaleString()}</td>
                                        <td>{model.total_tokens_out.toLocaleString()}</td>
                                        <td>{(model.total_tokens_in + model.total_tokens_out).toLocaleString()}</td>
                                    </tr>
                                ))}
                            {data.cost_summary.length === 0 && (
                                <tr>
                                    <td colSpan="4" className="empty-row">No token usage recorded yet.</td>
                                </tr>
                            )}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    );
}
