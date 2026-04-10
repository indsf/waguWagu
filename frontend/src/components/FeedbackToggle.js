import React from 'react';
import { useNavigate } from 'react-router-dom';
import './FeedbackToggle.css';

const FeedbackToggle = () => {
    const navigate = useNavigate();

    const handleClick = () => {
        navigate('/feedback-dashboard');
    };

    return (
        <button 
            className="feedback-toggle-btn"
            onClick={handleClick}
            title="피드백 현황 보기"
        >
            <span className="feedback-icon">📊</span>
        </button>
    );
};

export default FeedbackToggle;