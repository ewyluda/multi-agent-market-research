/**
 * NewsFeed - News articles with relevance scores, sentiment badges, and source attribution
 */

import React from 'react';
import { motion } from 'framer-motion';
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

  // Sort by relevance (highest first)
  const sortedArticles = [...displayArticles].sort(
    (a, b) => (b.relevance_score || 0) - (a.relevance_score || 0)
  );

  if (sortedArticles.length === 0) {
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

      return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    } catch {
      return '';
    }
  };

  const getSentimentBorderColor = (article) => {
    const score = article.av_overall_sentiment_score ?? article.av_ticker_sentiment_score;
    if (score == null) return 'border-l-accent-blue/30 hover:border-l-accent-blue/60';
    if (score > 0.15) return 'border-l-success/40 hover:border-l-success/70';
    if (score < -0.15) return 'border-l-danger/40 hover:border-l-danger/70';
    return 'border-l-warning/40 hover:border-l-warning/70';
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay: 0.2 }}
      className="glass-card-elevated rounded-xl p-5"
    >
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-gray-300 uppercase tracking-wider flex items-center space-x-2">
          <NewspaperIcon className="w-4 h-4" />
          <span>News</span>
        </h3>
        <span className="text-[10px] font-medium font-mono px-2 py-0.5 rounded-full bg-accent-blue/15 text-accent-blue border border-accent-blue/20">
          {newsData.total_count || sortedArticles.length} articles
        </span>
      </div>

      <div className="space-y-2">
        {sortedArticles.map((article, index) => (
          <div
            key={index}
            className={`p-3 bg-dark-inset rounded-lg border-l-2 ${getSentimentBorderColor(article)} hover:bg-dark-card-hover hover:shadow-lg hover:shadow-black/20 hover:-translate-y-px transition-all duration-200`}
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

            <div className="flex items-center flex-wrap gap-1.5 text-[10px]">
              {article.source && (
                <span className="px-2 py-0.5 rounded-full bg-gray-700/50 text-gray-400 font-medium">
                  {article.source}
                </span>
              )}
              <span className="text-gray-500">{formatDate(article.published_at)}</span>

              {/* Relevance score */}
              {article.relevance_score != null && (
                <span className={`px-1.5 py-0.5 rounded font-mono font-medium ${
                  article.relevance_score > 0.7 ? 'bg-success/15 text-success-400' :
                  article.relevance_score > 0.4 ? 'bg-primary/15 text-accent-blue' :
                  'bg-gray-700/50 text-gray-500'
                }`}>
                  {(article.relevance_score * 100).toFixed(0)}% rel
                </span>
              )}

              {/* Per-article sentiment (AV-only) */}
              {article.av_overall_sentiment_score != null && (
                <span className={`px-1.5 py-0.5 rounded font-mono font-medium ${
                  article.av_overall_sentiment_score > 0.15 ? 'bg-success/15 text-success-400' :
                  article.av_overall_sentiment_score < -0.15 ? 'bg-danger/15 text-danger-400' :
                  'bg-warning/15 text-warning-400'
                }`}>
                  {article.av_overall_sentiment_score > 0.15 ? '+Pos' :
                   article.av_overall_sentiment_score < -0.15 ? '-Neg' : '~Neu'}
                </span>
              )}

              {/* AV sentiment label fallback */}
              {article.av_overall_sentiment_label && article.av_overall_sentiment_score == null && (
                <span className="px-1.5 py-0.5 rounded bg-accent-purple/15 text-accent-purple font-medium">
                  {article.av_overall_sentiment_label}
                </span>
              )}
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
        <div className="mt-3 pt-3 border-t border-white/5 text-[10px] text-gray-500 font-mono">
          {newsData.recent_count} articles in the last 24 hours
        </div>
      )}
    </motion.div>
  );
};

export default NewsFeed;
