import React from 'react';

const AdvisorCard = ({ advisor }) => {
  const Icon = advisor.icon;

  return (
    <div className="advisor-card">
      <div 
        className="advisor-card-icon" 
        style={{ backgroundColor: advisor.bgColor }}
      >
        <Icon style={{ color: advisor.color }} />
      </div>
      <h3 className="advisor-card-title">{advisor.name}</h3>
      <p 
        className="advisor-card-role" 
        style={{ color: advisor.color }}
      >
        {advisor.role}
      </p>
      <p className="advisor-card-description">{advisor.description}</p>
    </div>
  );
};

export default AdvisorCard;