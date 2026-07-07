import React, { useState, useEffect } from "react";
import FlashcardsTab from "./FlashcardsTab";
import QuizTab from "./QuizTab";
import StatsTab from "./StatsTab";
import { recordStats } from "../api/claude";
import { recordGuestStats } from "../guestStorage";

export default function StudyView({ deck, onStatsRecorded, isGuest }) {
  const [activeTab, setActiveTab] = useState("flashcards");
  const [statsKey, setStatsKey] = useState(0);

  useEffect(() => {
    setActiveTab("flashcards");
  }, [deck.id]);

  async function handleScore(pct) {
    try {
      if (isGuest) {
        recordGuestStats(deck.id, pct);
      } else {
        await recordStats(deck.id, pct, 0);
      }
      if (onStatsRecorded) onStatsRecorded();
      setStatsKey((prev) => prev + 1);
    } catch (e) {
      console.error(e);
    }
  }

  return (
    <div className="study-view">
      <div className="study-view-header">
        <h2 className="study-view-title">{deck.title}</h2>
        {deck.created_at && !isNaN(new Date(deck.created_at)) && (
          <div className="study-view-meta">
            Created{" "}
            {new Date(deck.created_at).toLocaleDateString("en-AU", {
              day: "numeric",
              month: "short",
              year: "numeric",
            })}
          </div>
        )}
        <p className="study-view-summary">{deck.summary}</p>
      </div>
      <div className="study-tabs">
        <button
          className={`study-tab ${activeTab === "flashcards" ? "active" : ""}`}
          onClick={() => setActiveTab("flashcards")}>
          Flashcards
        </button>
        <button
          className={`study-tab ${activeTab === "quiz" ? "active" : ""}`}
          onClick={() => setActiveTab("quiz")}>
          Quiz
        </button>
        <button
          className={`study-tab ${activeTab === "stats" ? "active" : ""}`}
          onClick={() => setActiveTab("stats")}>
          Stats
        </button>
        <button
          className={`study-tab ${activeTab === "notes" ? "active" : ""}`}
          onClick={() => setActiveTab("notes")}>
          Notes
        </button>
      </div>
      <div className="study-content">
        <div style={{ display: activeTab === "flashcards" ? "block" : "none" }}>
          <FlashcardsTab
            flashcards={deck.flashcards}
            onCardReviewed={() => {}}
          />
        </div>
        <div style={{ display: activeTab === "quiz" ? "block" : "none" }}>
          <QuizTab quiz={deck.quiz} onScore={handleScore} />
        </div>
        <div style={{ display: activeTab === "stats" ? "block" : "none" }}>
          <StatsTab deckId={deck.id} lastUpdated={statsKey} isGuest={isGuest} />
        </div>
        <div style={{ display: activeTab === "notes" ? "block" : "none" }}>
          <div className="notes-view">
            <div className="notes-content">{deck.notes}</div>
          </div>
        </div>
      </div>
    </div>
  );
}
