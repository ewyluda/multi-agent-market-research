/**
 * NewsFeed - Displays recent news articles
 */

import React from 'react';

const NewsFeed = ({ analysis }) => {
  if (!analysis || !analysis.agent_results?.news) {
    return null;
  }

  const newsData = analysis.agent_results.news.data || {};
  const articles = newsData.articles || [];
  const keyHeadlines = newsData.key_headlines || [];

  const displayArticles = keyHeadlines.length > 0 ? keyHeadlines : articles.slice(0, 10);

  if (displayArticles.length === 0) {
    return (
      <div className="bg-dark-card border border-dark-border rounded-lg p-6">
        <h3 className="text-lg font-semibold mb-4">News</h3>
        <div className="text-gray-500 text-center py-8">
          No news articles found
        </div>
      </div>
    );
  }

  const formatDate = (dateString) => {
    if (!dateString) return '';
    try {
      const date = new Date(dateString);
      return date.toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      });
    } catch {
      return '';
    }
  };

  return (
    <div className="bg-dark-card border border-dark-border rounded-lg p-6">
      <h3 className="text-lg font-semibold mb-4">
        News
        <span className="text-sm text-gray-400 ml-2">
          ({newsData.total_count || displayArticles.length} articles)
        </span>
      </h3>

      <div className="space-y-3 max-h-[600px] overflow-y-auto">
        {displayArticles.map((article, index) => (
          <div
            key={index}
            className="p-4 bg-dark-bg rounded-md hover:bg-gray-800 transition-colors"
          >
            <div className="flex justify-between items-start mb-2">
              <h4 className="font-medium text-sm flex-1">
                {article.url ? (
                  <a
                    href={article.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-accent-blue hover:underline"
                  >
                    {article.title}
                  </a>
                ) : (
                  article.title
                )}
              </h4>
            </div>

            <div className="flex items-center justify-between text-xs text-gray-400">
              <span>{article.source || 'Unknown Source'}</span>
              <span>{formatDate(article.published_at)}</span>
            </div>

            {article.description && (
              <p className="mt-2 text-xs text-gray-300 line-clamp-2">
                {article.description}
              </p>
            )}
          </div>
        ))}
      </div>

      {newsData.recent_count !== undefined && (
        <div className="mt-4 pt-4 border-t border-dark-border text-xs text-gray-400">
          {newsData.recent_count} articles in the last 24 hours
        </div>
      )}
    </div>
  );
};

export default NewsFeed;
