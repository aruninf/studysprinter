import React, { useState, useEffect } from "react";
import { getDeckStats } from "../api/claude";
import { getGuestDeckStats } from "../guestStorage";

export default function StatsTab({ deckId, lastUpdated, isGuest }) {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchStats() {
      setLoading(true);
      try {
        const data = isGuest
          ? getGuestDeckStats(deckId)
          : await getDeckStats(deckId);
        setStats(data);
      } catch (e) {
        console.error(e);
      } finally {
        setLoading(false);
      }
    }
    fetchStats();
  }, [deckId, lastUpdated]);

  if (loading)
    return (
      <div className="empty-sub" style={{ padding: "2rem" }}>
        Loading stats...
      </div>
    );

  if (!stats)
    return (
      <div className="empty-sub" style={{ padding: "2rem" }}>
        No stats yet.
      </div>
    );
  return (
    <div className="stats-view">
      <div className="stats-grid">
        <div className="stat-card">
          <div className="stat-num">{stats.times_reviewed}</div>
          <div className="stat-label">Quizzes Taken</div>
        </div>
        <div className="stat-card">
          <div className="stat-num">
            {stats.best_score !== null ? `${stats.best_score}%` : "—"}
          </div>
          <div className="stat-label">Best Quiz Score</div>
        </div>
        <div className="stat-card">
          <div className="stat-num" style={{ fontSize: "22px" }}>
            {stats.last_reviewed
              ? new Date(stats.last_reviewed).toLocaleDateString("en-AU", {
                  day: "numeric",
                  month: "short",
                  year: "numeric",
                })
              : "—"}
          </div>
          <div className="stat-label">Last Studied</div>
        </div>
      </div>

      {stats.times_reviewed === 0 && (
        <div
          className="empty-state"
          style={{ height: "auto", marginTop: "2rem" }}>
          <div className="empty-title">No activity yet</div>
          <div className="empty-sub">
            Complete a quiz to see your stats here.
          </div>
        </div>
      )}
    </div>
  );
}
