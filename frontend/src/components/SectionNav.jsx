import { useState, useEffect, useCallback } from 'react';

const SECTIONS = [
  { id: 'section-fundamentals', label: 'Fundamentals' },
  { id: 'section-technical', label: 'Technical' },
  { id: 'section-sentiment', label: 'Sentiment' },
  { id: 'section-macro', label: 'Macro' },
  { id: 'section-news', label: 'News' },
  { id: 'section-options', label: 'Options' },
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
      className="sticky z-[35] flex gap-1 px-6 py-2"
      style={{
        top: `${searchBarHeight}px`,
        background: 'rgba(9,9,11,0.9)',
        backdropFilter: 'blur(8px)',
        borderBottom: '1px solid rgba(255,255,255,0.04)',
      }}
    >
      {SECTIONS.map(({ id, label }) => {
        const isActive = activeId === id;
        return (
          <button
            key={id}
            onClick={() => handleClick(id)}
            className={`px-3.5 py-1.5 rounded-md text-[0.75rem] font-medium transition-colors border-none cursor-pointer ${
              isActive
                ? 'text-[#006fee] bg-[rgba(0,111,238,0.08)]'
                : 'text-white/35 bg-transparent hover:text-white/55 hover:bg-white/[0.03]'
            }`}
          >
            {label}
          </button>
        );
      })}
    </div>
  );
}
