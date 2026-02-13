/**
 * SocialBuzz - Twitter/X social sentiment panel
 * Shows tweet volume, engagement metrics, and top tweets by engagement
 */

import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { XLogoIcon, HeartIcon, RepeatIcon, ChatBubbleIcon, FireIcon, ChevronDownIcon } from './Icons';

const SocialBuzz = ({ analysis }) => {
  const [expanded, setExpanded] = useState(true);

  const newsData = analysis?.agent_results?.news?.data;
  const twitterBuzz = newsData?.twitter_buzz;
  const twitterPosts = newsData?.twitter_posts || [];

  // Don't render if no Twitter data at all
  if (!twitterBuzz || twitterBuzz.total_tweets === 0) return null;

  const topTweets = twitterBuzz.top_tweets || [];
  const totalTweets = twitterBuzz.total_tweets;
  const totalEngagement = twitterBuzz.total_engagement;
  const avgEngagement = twitterBuzz.avg_engagement;

  // Buzz intensity level for visual treatment
  const getBuzzLevel = () => {
    if (totalTweets >= 40 && avgEngagement >= 5) return 'high';
    if (totalTweets >= 20 || avgEngagement >= 2) return 'medium';
    return 'low';
  };

  const buzzLevel = getBuzzLevel();

  const buzzColors = {
    high: { text: 'text-accent-amber', bg: 'bg-accent-amber/15', border: 'border-accent-amber/30', glow: 'shadow-[0_0_12px_rgba(245,165,36,0.1)]' },
    medium: { text: 'text-accent-cyan', bg: 'bg-accent-cyan/15', border: 'border-accent-cyan/30', glow: '' },
    low: { text: 'text-gray-400', bg: 'bg-white/5', border: 'border-white/10', glow: '' },
  };

  const colors = buzzColors[buzzLevel];

  const buzzLabels = { high: 'Trending', medium: 'Active', low: 'Quiet' };

  const formatDate = (dateString) => {
    if (!dateString) return '';
    try {
      const date = new Date(dateString);
      const now = new Date();
      const diffMs = now - date;
      const diffMin = Math.floor(diffMs / 60000);
      const diffHours = Math.floor(diffMs / 3600000);

      if (diffMin < 1) return 'just now';
      if (diffMin < 60) return `${diffMin}m`;
      if (diffHours < 24) return `${diffHours}h`;
      return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    } catch {
      return '';
    }
  };

  const formatNumber = (n) => {
    if (n >= 1000) return `${(n / 1000).toFixed(1)}k`;
    return String(n);
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay: 0.18 }}
      className={`space-y-0 ${colors.glow}`}
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center space-x-2">
          <div className="w-7 h-7 rounded-lg bg-white/10 flex items-center justify-center">
            <XLogoIcon className="w-4 h-4 text-white" />
          </div>
          <h3 className="text-sm font-semibold text-gray-300 uppercase tracking-wider">Social Buzz</h3>
        </div>
        <div className="flex items-center space-x-2">
          <span className={`text-xs font-semibold px-2 py-0.5 rounded ${colors.bg} ${colors.text} ${colors.border} border`}>
            {buzzLabels[buzzLevel]}
          </span>
        </div>
      </div>

      {/* Metrics Row */}
      <div className="grid grid-cols-3 gap-3 mb-4">
        <div className="bg-dark-inset rounded-lg p-3 border border-white/5">
          <div className="text-[10px] text-gray-500 uppercase tracking-wider mb-1">Tweets</div>
          <div className="text-lg font-bold font-mono tabular-nums">{totalTweets}</div>
          <div className="text-[10px] text-gray-500">7-day window</div>
        </div>
        <div className="bg-dark-inset rounded-lg p-3 border border-white/5">
          <div className="text-[10px] text-gray-500 uppercase tracking-wider mb-1">Engagement</div>
          <div className="text-lg font-bold font-mono tabular-nums">{formatNumber(totalEngagement)}</div>
          <div className="text-[10px] text-gray-500">total interactions</div>
        </div>
        <div className="bg-dark-inset rounded-lg p-3 border border-white/5">
          <div className="text-[10px] text-gray-500 uppercase tracking-wider mb-1">Avg / Tweet</div>
          <div className="text-lg font-bold font-mono tabular-nums">{avgEngagement.toFixed(1)}</div>
          <div className="text-[10px] text-gray-500">engagement</div>
        </div>
      </div>

      {/* Engagement Spark Bar - visual density indicator */}
      <div className="mb-4">
        <div className="flex items-center justify-between mb-1.5">
          <span className="text-[10px] text-gray-500 uppercase tracking-wider">Buzz Level</span>
          <span className={`text-[10px] font-mono font-medium ${colors.text}`}>
            {totalTweets} mentions
          </span>
        </div>
        <div className="h-1.5 bg-dark-inset rounded-full overflow-hidden">
          <motion.div
            className={`h-full rounded-full ${
              buzzLevel === 'high' ? 'bg-gradient-to-r from-accent-amber/70 to-accent-amber' :
              buzzLevel === 'medium' ? 'bg-gradient-to-r from-accent-cyan/50 to-accent-cyan' :
              'bg-gradient-to-r from-gray-600/50 to-gray-500'
            }`}
            initial={{ width: 0 }}
            animate={{ width: `${Math.min((totalTweets / 50) * 100, 100)}%` }}
            transition={{ duration: 0.8, ease: 'easeOut' }}
          />
        </div>
      </div>

      {/* Top Tweets (collapsible) */}
      {topTweets.length > 0 && (
        <div>
          <button
            onClick={() => setExpanded(!expanded)}
            className="flex items-center justify-between w-full px-3 py-2 rounded-lg text-xs font-medium text-gray-400 hover:text-gray-200 hover:bg-white/[0.03] transition-all"
          >
            <span className="uppercase tracking-wider text-[10px]">Top Tweets</span>
            <motion.div
              animate={{ rotate: expanded ? 180 : 0 }}
              transition={{ duration: 0.2 }}
            >
              <ChevronDownIcon className="w-3.5 h-3.5" />
            </motion.div>
          </button>

          <motion.div
            initial={false}
            animate={{ height: expanded ? 'auto' : 0, opacity: expanded ? 1 : 0 }}
            transition={{ duration: 0.25, ease: 'easeInOut' }}
            className="overflow-hidden"
          >
            <div className="space-y-2 pt-2 max-h-[400px] overflow-y-auto pr-1">
              {topTweets.map((tweet, index) => (
                <motion.div
                  key={tweet.id || index}
                  initial={{ opacity: 0, x: -8 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ duration: 0.2, delay: index * 0.04 }}
                  className="p-3 bg-dark-inset rounded-lg border border-white/5 hover:border-white/10 transition-all group"
                >
                  {/* Tweet text */}
                  <div className="text-xs text-gray-300 leading-relaxed mb-2 line-clamp-3">
                    {tweet.url ? (
                      <a
                        href={tweet.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="hover:text-accent-cyan transition-colors"
                      >
                        {tweet.text}
                      </a>
                    ) : (
                      tweet.text
                    )}
                  </div>

                  {/* Metrics row */}
                  <div className="flex items-center space-x-4 text-[10px] text-gray-500">
                    <span className="flex items-center space-x-1 group-hover:text-danger-400 transition-colors">
                      <HeartIcon className="w-3 h-3" />
                      <span className="font-mono">{tweet.metrics?.likes || 0}</span>
                    </span>
                    <span className="flex items-center space-x-1 group-hover:text-success-400 transition-colors">
                      <RepeatIcon className="w-3 h-3" />
                      <span className="font-mono">{tweet.metrics?.retweets || 0}</span>
                    </span>
                    <span className="flex items-center space-x-1 group-hover:text-accent-cyan transition-colors">
                      <ChatBubbleIcon className="w-3 h-3" />
                      <span className="font-mono">{tweet.metrics?.replies || 0}</span>
                    </span>
                    <span className="ml-auto text-gray-600">{formatDate(tweet.created_at)}</span>
                  </div>
                </motion.div>
              ))}
            </div>
          </motion.div>
        </div>
      )}

      {/* Footer */}
      <div className="mt-3 pt-3 border-t border-white/5 flex items-center justify-between text-[10px] text-gray-600 font-mono">
        <span>Cashtag search via X API v2</span>
        <span className="flex items-center space-x-1">
          <XLogoIcon className="w-2.5 h-2.5" />
          <span>twitter.com</span>
        </span>
      </div>
    </motion.div>
  );
};

export default SocialBuzz;
