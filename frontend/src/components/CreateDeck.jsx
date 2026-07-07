import React, { useState } from "react";
import { generateStudySet } from "../api/claude";

const EXAMPLE_NOTES = `Big O Notation is used to describe the performance or complexity of an algorithm, specifically how runtime or space requirements grow as the input size increases.

Common complexities from fastest to slowest:

O(1) Constant time: the operation takes the same time regardless of input size. Example: accessing an array element by index.

O(log n) Logarithmic: runtime grows slowly as input grows. Example: binary search.

O(n) Linear: runtime grows proportionally with input size. Example: iterating through an array.

O(n log n) Linearithmic: common in efficient sorting algorithms. Example: merge sort and quicksort.

O(n²) Quadratic: runtime grows with the square of input size. Example: nested loops and bubble sort.

O(2^n) Exponential: runtime doubles with each additional input. Example: recursive fibonacci.

Key rules:
Drop constants so O(2n) simplifies to O(n).
Drop non-dominant terms so O(n² + n) simplifies to O(n²).
Different inputs use different variables so O(a + b) not O(n + n).

Space complexity follows the same notation but measures memory usage instead of time.`;

export default function CreateDeck({
  onDeckCreated,
  onCancel,
  onGeneratingChange,
}) {
  const [title, setTitle] = useState("");
  const [notes, setNotes] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function handleGenerate() {
    if (!title.trim()) {
      setError("Give your deck a name first.");
      return;
    }
    if (notes.trim().length < 300) {
      setError(
        `Add more content to your notes. You have ${notes.trim().length} characters, aim for at least 300 for a good study set.`,
      );
      return;
    }
    setError("");
    setLoading(true);
    if (onGeneratingChange) onGeneratingChange(true);
    try {
      const result = await generateStudySet(notes, title.trim());
      console.log(JSON.stringify(result));
      onDeckCreated({ ...result, notes });
    } catch (e) {
      if (e.message.includes("fetch") || e.message.includes("Failed")) {
        setError("Couldn't connect to the backend. Make sure it's running.");
      } else {
        setError(e.message || "Something went wrong. Try again.");
      }
    } finally {
      setLoading(false);
      if (onGeneratingChange) onGeneratingChange(false);
    }
  }

  return (
    <div className="create-deck">
      <div className="create-deck-header">
        <h2 className="create-deck-title">Create a new deck</h2>
        <button className="btn-secondary" onClick={onCancel}>
          Cancel
        </button>
      </div>
      <div className="card">
        <div className="card-label">Deck Name</div>
        <input
          className="deck-name-input"
          value={title}
          onChange={(e) => {
            setTitle(e.target.value);
            setError("");
          }}
          placeholder="e.g. Big O Notation, Week 3 Lecture..."
        />
        {error && error.includes("name") && (
          <p className="error-msg">{error}</p>
        )}
      </div>
      <div className="card">
        <div className="card-label">Your Notes</div>
        <textarea
          value={notes}
          onChange={(e) => {
            setNotes(e.target.value);
            setError("");
          }}
          placeholder="Paste your lecture notes, textbook content, or anything you need to study..."
          rows={12}
        />
        {error && !error.includes("name") && (
          <p className="error-msg">{error}</p>
        )}
        <div className="action-row">
          <button
            className="btn-primary"
            onClick={handleGenerate}
            disabled={loading}>
            {loading ? (
              <>
                <span className="spinner" /> Generating your study set...
              </>
            ) : (
              "Generate Study Set"
            )}
          </button>
          <button
            className="btn-secondary"
            onClick={() => {
              setTitle("Big O Notation");
              setNotes(EXAMPLE_NOTES);
              setError("");
            }}
            disabled={loading}>
            Try an example
          </button>
        </div>
      </div>
    </div>
  );
}
