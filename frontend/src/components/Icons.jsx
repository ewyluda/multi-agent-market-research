/**
 * SVG Icon Components - Consistent 20x20 line-art icons
 */

import React from 'react';

const iconProps = {
  width: 20,
  height: 20,
  viewBox: '0 0 20 20',
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 1.5,
  strokeLinecap: 'round',
  strokeLinejoin: 'round',
};

export const ChartBarIcon = (props) => (
  <svg {...iconProps} {...props}>
    <path d="M3 17V10M8 17V6M13 17V3M18 17V8" />
  </svg>
);

export const BuildingIcon = (props) => (
  <svg {...iconProps} {...props}>
    <path d="M4 17V5a1 1 0 011-1h6a1 1 0 011 1v12M4 17h8M4 17H2M12 17h2M12 17v-4h4a1 1 0 011 1v3M17 17h1" />
    <path d="M7 7h2M7 10h2M7 13h2" />
  </svg>
);

export const NewspaperIcon = (props) => (
  <svg {...iconProps} {...props}>
    <path d="M3 4h11a1 1 0 011 1v11a1 1 0 01-1 1H5a2 2 0 01-2-2V4z" />
    <path d="M15 8h1a1 1 0 011 1v6a2 2 0 01-2 2" />
    <path d="M6 7h5M6 10h5M6 13h3" />
  </svg>
);

export const ChartLineIcon = (props) => (
  <svg {...iconProps} {...props}>
    <path d="M3 17l4-6 3 3 4-7 3 4" />
    <circle cx="3" cy="17" r="1" fill="currentColor" stroke="none" />
    <circle cx="7" cy="11" r="1" fill="currentColor" stroke="none" />
    <circle cx="10" cy="14" r="1" fill="currentColor" stroke="none" />
    <circle cx="14" cy="7" r="1" fill="currentColor" stroke="none" />
    <circle cx="17" cy="11" r="1" fill="currentColor" stroke="none" />
  </svg>
);

export const BrainIcon = (props) => (
  <svg {...iconProps} {...props}>
    <path d="M10 3C7.5 3 5.5 4.5 5 6.5c-1.5.5-2.5 2-2.5 3.5 0 1.5 1 3 2.5 3.5.5 2 2.5 3.5 5 3.5s4.5-1.5 5-3.5c1.5-.5 2.5-2 2.5-3.5s-1-3-2.5-3.5C14.5 4.5 12.5 3 10 3z" />
    <path d="M10 3v14M6 8h8M6 12h8" />
  </svg>
);

export const SparklesIcon = (props) => (
  <svg {...iconProps} {...props}>
    <path d="M10 2l1.5 4.5L16 8l-4.5 1.5L10 14l-1.5-4.5L4 8l4.5-1.5L10 2z" />
    <path d="M15 12l.75 2.25L18 15l-2.25.75L15 18l-.75-2.25L12 15l2.25-.75L15 12z" />
  </svg>
);

export const GlobeIcon = (props) => (
  <svg {...iconProps} {...props}>
    <circle cx="10" cy="10" r="7" />
    <path d="M3 10h14" />
    <path d="M10 3c2 2.5 2 11.5 0 14" />
    <path d="M10 3c-2 2.5-2 11.5 0 14" />
  </svg>
);

export const DocumentIcon = (props) => (
  <svg {...iconProps} {...props}>
    <path d="M5 3h7l4 4v10a1 1 0 01-1 1H5a1 1 0 01-1-1V4a1 1 0 011-1z" />
    <path d="M12 3v4h4" />
    <path d="M7 10h6M7 13h4" />
  </svg>
);

export const ShieldExclamationIcon = (props) => (
  <svg {...iconProps} {...props}>
    <path d="M10 2l7 3v4c0 4.5-3 8.5-7 10-4-1.5-7-5.5-7-10V5l7-3z" />
    <path d="M10 7v4M10 13v.5" />
  </svg>
);

export const LightbulbIcon = (props) => (
  <svg {...iconProps} {...props}>
    <path d="M10 2a5 5 0 013 9v2a1 1 0 01-1 1H8a1 1 0 01-1-1v-2a5 5 0 013-9z" />
    <path d="M8 16h4M9 18h2" />
  </svg>
);

export const ArrowUpIcon = (props) => (
  <svg {...iconProps} {...props}>
    <path d="M10 17V3M5 8l5-5 5 5" />
  </svg>
);

export const ArrowDownIcon = (props) => (
  <svg {...iconProps} {...props}>
    <path d="M10 3v14M5 12l5 5 5-5" />
  </svg>
);

export const ClockIcon = (props) => (
  <svg {...iconProps} {...props}>
    <circle cx="10" cy="10" r="7" />
    <path d="M10 6v4l3 2" />
  </svg>
);

export const SearchIcon = (props) => (
  <svg {...iconProps} {...props}>
    <circle cx="8.5" cy="8.5" r="5.5" />
    <path d="M13 13l4 4" />
  </svg>
);

export const CheckCircleIcon = (props) => (
  <svg {...iconProps} {...props}>
    <circle cx="10" cy="10" r="7" />
    <path d="M7 10l2 2 4-4" />
  </svg>
);

export const XCircleIcon = (props) => (
  <svg {...iconProps} {...props}>
    <circle cx="10" cy="10" r="7" />
    <path d="M7.5 7.5l5 5M12.5 7.5l-5 5" />
  </svg>
);

export const PulseIcon = (props) => (
  <svg {...iconProps} {...props}>
    <path d="M2 10h3l2-5 3 10 2-5h6" />
  </svg>
);

export const TrendingUpIcon = (props) => (
  <svg {...iconProps} {...props}>
    <path d="M3 15l5-5 3 3 6-6" />
    <path d="M14 7h3v3" />
  </svg>
);

export const TrendingDownIcon = (props) => (
  <svg {...iconProps} {...props}>
    <path d="M3 5l5 5 3-3 6 6" />
    <path d="M14 13h3v-3" />
  </svg>
);

export const ChevronDownIcon = (props) => (
  <svg {...iconProps} {...props}>
    <path d="M5 7.5l5 5 5-5" />
  </svg>
);

export const TargetIcon = (props) => (
  <svg {...iconProps} {...props}>
    <circle cx="10" cy="10" r="7" />
    <circle cx="10" cy="10" r="4" />
    <circle cx="10" cy="10" r="1" fill="currentColor" stroke="none" />
  </svg>
);

export const HistoryIcon = (props) => (
  <svg {...iconProps} {...props}>
    <circle cx="10" cy="10" r="7" />
    <path d="M10 6v4l2 2" />
    <path d="M3 10H1M10 3V1" />
  </svg>
);

export const FilterIcon = (props) => (
  <svg {...iconProps} {...props}>
    <path d="M3 4h14M5 8h10M7 12h6M9 16h2" />
  </svg>
);

export const TrashIcon = (props) => (
  <svg {...iconProps} {...props}>
    <path d="M5 5h10M8 5V3h4v2M6 5v10a1 1 0 001 1h6a1 1 0 001-1V5" />
    <path d="M8 8v5M12 8v5" />
  </svg>
);

export const ChevronLeftIcon = (props) => (
  <svg {...iconProps} {...props}>
    <path d="M12.5 5l-5 5 5 5" />
  </svg>
);

export const ChevronRightIcon = (props) => (
  <svg {...iconProps} {...props}>
    <path d="M7.5 5l5 5-5 5" />
  </svg>
);

export const ArrowLeftIcon = (props) => (
  <svg {...iconProps} {...props}>
    <path d="M17 10H3M8 5l-5 5 5 5" />
  </svg>
);

export const OptionsIcon = (props) => (
  <svg {...iconProps} {...props}>
    <path d="M3 10h14M10 3v14M6 6l8 8M14 6l-8 8" />
  </svg>
);

export const BellIcon = (props) => (
  <svg {...iconProps} {...props}>
    <path d="M10 2a1 1 0 011 1v1a5 5 0 014 4.9V12l2 3H3l2-3V8.9A5 5 0 019 4V3a1 1 0 011-1z" />
    <path d="M8 15a2 2 0 004 0" />
  </svg>
);

export const LoadingSpinner = ({ className = '', size = 20 }) => (
  <svg
    width={size}
    height={size}
    viewBox="0 0 20 20"
    fill="none"
    className={`animate-spin-slow ${className}`}
  >
    <circle cx="10" cy="10" r="8" stroke="currentColor" strokeWidth="2" opacity="0.25" />
    <path
      d="M10 2a8 8 0 018 8"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
    />
  </svg>
);
