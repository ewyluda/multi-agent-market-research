import { useState, useEffect, useCallback } from 'react';

const SECTIONS = [
  { id: 'section-company_overview', label: 'Company Overview' },
  { id: 'section-earnings', label: 'Earnings' },
  { id: 'section-earnings_review', label: 'Earnings Review' },
  { id: 'section-thesis', label: 'Thesis' },
  { id: 'section-risk_diff', label: 'Risk Analysis' },
  { id: 'section-technicals_options', label: 'Technicals & Options' },
  { id: 'section-sentiment', label: 'Sentiment' },
  { id: 'section-news', label: 'News' },
  { id: 'section-leadership', label: 'Leadership' },
  { id: 'section-council', label: 'Council' },
];

export default function SectionNav({ searchBarHeight = 49 }) {
  const [activeId, setActiveId] = useState(SECTIONS[0].id);

  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            setActiveId(entry.target.id);
          }
        }
      },
      { rootMargin: '-120px 0px -60% 0px', threshold: 0 }
    );

    SECTIONS.forEach(({ id }) => {
      const el = document.getElementById(id);
      if (el) observer.observe(el);
    });

    return () => observer.disconnect();
  }, []);

  const handleClick = useCallback((sectionId) => {
    const el = document.getElementById(sectionId);
    if (el) {
      const offset = searchBarHeight + 48;
      const top = el.getBoundingClientRect().top + window.scrollY - offset;
      window.scrollTo({ top, behavior: 'smooth' });
    }
  }, [searchBarHeight]);

  return (
    <div
      className="sticky z-[35] flex px-6 py-3 overflow-x-auto"
      style={{
        top: `${searchBarHeight}px`,
        background: 'rgba(9,9,11,0.9)',
        backdropFilter: 'blur(8px)',
        borderBottom: '1px solid rgba(255,255,255,0.04)',
        gap: '16px',
      }}
    >
      {SECTIONS.map(({ id, label }) => {
        const isActive = activeId === id;
        return (
          <button
            key={id}
            onClick={() => handleClick(id)}
            className="border-none cursor-pointer whitespace-nowrap transition-all duration-150"
            style={{
              padding: '10px 20px',
              borderRadius: '9999px',
              fontSize: '0.8rem',
              fontWeight: 500,
              background: isActive ? 'var(--accent-blue)' : 'transparent',
              color: isActive ? '#ffffff' : 'var(--text-muted)',
              border: isActive ? 'none' : '1px solid rgba(255,255,255,0.06)',
            }}
            onMouseEnter={(e) => {
              if (!isActive) {
                e.currentTarget.style.background = 'rgba(255,255,255,0.06)';
                e.currentTarget.style.color = 'var(--text-secondary)';
              }
            }}
            onMouseLeave={(e) => {
              if (!isActive) {
                e.currentTarget.style.background = 'transparent';
                e.currentTarget.style.color = 'var(--text-muted)';
              }
            }}
          >
            {label}
          </button>
        );
      })}
    </div>
  );
}
