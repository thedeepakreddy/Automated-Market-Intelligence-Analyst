import React from 'react';

export function Logo({ className = '' }: { className?: string }) {
  return (
    <svg 
      viewBox="0 0 100 110" 
      fill="none" 
      xmlns="http://www.w3.org/2000/svg"
      className={className}
    >
      {/* Top Pill */}
      <mask id="top-pill">
        <rect x="0" y="0" width="100" height="30" rx="15" fill="white" />
      </mask>
      <g mask="url(#top-pill)">
        <rect x="0" y="0" width="30" height="30" fill="#295DBC" />
        <rect x="30" y="0" width="70" height="30" fill="#4BCEC1" />
      </g>
      
      {/* Middle Pill */}
      <mask id="mid-pill">
        <rect x="0" y="40" width="100" height="30" rx="15" fill="white" />
      </mask>
      <g mask="url(#mid-pill)">
        <rect x="0" y="40" width="30" height="30" fill="#42BCA4" />
        <rect x="30" y="40" width="70" height="30" fill="#E8762D" />
      </g>

      {/* Bottom Circle */}
      <mask id="bot-circle">
        <rect x="0" y="80" width="30" height="30" rx="15" fill="white" />
      </mask>
      <g mask="url(#bot-circle)">
        <rect x="0" y="80" width="15" height="30" fill="#E6992E" />
        <rect x="15" y="80" width="15" height="30" fill="#B91D2F" />
      </g>
    </svg>
  );
}
