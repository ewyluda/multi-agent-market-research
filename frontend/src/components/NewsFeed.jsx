/**
 * NewsFeed - Displays recent news articles with source badges
 */

import React from 'react';
import { NewspaperIcon } from './Icons';

const NewsFeed = ({ analysis }) => {
  if (!analysis || !analysis.agent_results?.news) {
    return (
      <div className="glass-card-elevated rounded-xl p-5">
        <div className="flex items-center space-x-2 mb-4">
          <NewspaperIcon className="w-4 h-4 text-gray-500" />
          <span className="text-sm text-gray-500">No news data available</span>
        </div>
      </div>
    );
  }

  const newsData = analysis.agent_results.news.data || {};
  const articles = newsData.articles || [];
  const keyHeadlines = newsData.key_headlines || [];

  const displayArticles = keyHeadlines.length > 0 ? keyHeadlines : articles.slice(0, 10);

  if (displayArticles.length === 0) {
    return (
      <div className="glass-card-elevated rounded-xl p-5">
        <div className="flex items-center space-x-2">
          <NewspaperIcon className="w-4 h-4 text-gray-500" />
          <span className="text-sm text-gray-500">No news articles found</span>
        </div>
      </div>
    );
  }

  const formatDate = (dateString) => {
    if (!dateString) return '';
    try {
      const date = new Date(dateString);
      const now = new Date();
      const diffMs = now - date;
      const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
      const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

      if (diffHours < 1) return 'Just now';
      if (diffHours < 24) return `${diffHours}h ago`;
      if (diffDays < 7) return `${diffDays}d ago`;

      return date.toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
      });
    } catch {
      return '';
    }
  };

  return (
    <div className="glass-card-elevated rounded-xl p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-gray-300 uppercase tracking-wider flex items-center space-x-2">
          <NewspaperIcon className="w-4 h-4" />
          <span>News</span>
        </h3>
        <span className="text-[10px] font-medium px-2 py-0.5 rounded-full bg-accent-blue/15 text-accent-blue border border-accent-blue/20">
          {newsData.total_count || displayArticles.length} articles
        </span>
      </div>

      <div className="space-y-2 max-h-[500px] overflow-y-auto pr-1">
        {displayArticles.map((article, index) => (
          <div
            key={index}
            className="p-3 bg-dark-inset rounded-lg border-l-2 border-l-accent-blue/30 hover:border-l-accent-blue/60 hover:bg-dark-card-hover transition-all"
          >
            <h4 className="text-xs font-medium leading-relaxed mb-1.5">
              {article.url ? (
                <a
                  href={article.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-gray-200 hover:text-accent-blue transition-colors"
                >
                  {article.title}
                </a>
              ) : (
                <span className="text-gray-200">{article.title}</span>
              )}
            </h4>

            <div className="flex items-center space-x-2 text-[10px]">
              {article.source && (
                <span className="px-1.5 py-0.5 rounded bg-gray-700/50 text-gray-400 font-medium">
                  {article.source}
                </span>
              )}
              <span className="text-gray-500">{formatDate(article.published_at)}</span>
            </div>

            {article.description && (
              <p className="mt-1.5 text-[11px] text-gray-400 line-clamp-2 leading-relaxed">
                {article.description}
              </p>
            )}
          </div>
        ))}
      </div>

      {newsData.recent_count !== undefined && (
        <div className="mt-3 pt-3 border-t border-white/5 text-[10px] text-gray-500">
          {newsData.recent_count} articles in the last 24 hours
        </div>
      )}
    </div>
  );
};

export default NewsFeed;
