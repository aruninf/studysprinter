import React, { useState, useEffect } from "react";
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import { supabase } from "./supabase";
import Login from "./components/Login";
import {
  faBookOpen,
  faUser,
  faPlus,
  faSun,
  faMoon,
  faXmark,
} from "@fortawesome/free-solid-svg-icons";
import "./styles/base.css";
import "./styles/sidebar.css";
import "./styles/study.css";
import "./styles/forms.css";
import "./styles/auth.css";
import "./styles/modals.css";
import Sidebar from "./components/Sidebar";
import CreateDeck from "./components/CreateDeck";
import StudyView from "./components/StudyView";
import ResetPassword from "./components/ResetPassword";
import { EXAMPLE_DECKS } from "./exampleDecks";
import {
  getStudySets,
  getStudySet,
  deleteStudySet,
  togglePin,
  deleteAccount,
} from "./api/claude";
import {
  getGuestStudySets,
  getGuestStudySet,
  getExampleFirstSeen,
  deleteGuestStudySet,
  toggleGuestPin,
  saveGuestDeck,
  getAllGuestDecks,
  clearGuestData,
  dismissExampleDeck,
  getDismissedExamples,
  toggleExamplePin,
  getPinnedExamples,
} from "./guestStorage";

export default function App() {
  const [dark, setDark] = useState(
    () => localStorage.getItem("theme") === "dark",
  );
  const [decks, setDecks] = useState([]);
  const [selectedDeck, setSelectedDeck] = useState(null);
  const [view, setView] = useState("empty");
  const [globalStatsKey, setGlobalStatsKey] = useState(0);
  const [loading, setLoading] = useState(true);
  const [isGenerating, setIsGenerating] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(window.innerWidth > 768);
  const [user, setUser] = useState(null);
  const [authLoading, setAuthLoading] = useState(true);
  const [migrating, setMigrating] = useState(false);
  const [showSaveNudge, setShowSaveNudge] = useState(false);
  const [showUserMenu, setShowUserMenu] = useState(false);
  const [showDeleteAccountConfirm, setShowDeleteAccountConfirm] =
    useState(false);
  const [passwordRecovery, setPasswordRecovery] = useState(false);
  const [showLoginModal, setShowLoginModal] = useState(false);
  const nudgeShownRef = React.useRef(false);

  useEffect(() => {
    document.body.classList.toggle("dark", dark);
  }, [dark]);

  useEffect(() => {
    if (!migrating) {
      fetchDecks();
    }
  }, [user, migrating]);

  useEffect(() => {
    function handleResize() {
      const sidebar = document.querySelector(".sidebar");
      if (sidebar) sidebar.style.transition = "none";
      setSidebarOpen(window.innerWidth > 768);
      setTimeout(() => {
        const sidebar = document.querySelector(".sidebar");
        if (sidebar) sidebar.style.transition = "";
      }, 50);
    }
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);

  useEffect(() => {
    if (selectedDeck) {
      document.title = `${selectedDeck.title} - StudySprinter`;
    } else {
      document.title = "StudySprinter";
    }
  }, [selectedDeck]);

  useEffect(() => {
    supabase.auth.getSession().then(({ data: { session } }) => {
      setUser(session?.user ?? null);
      setAuthLoading(false);
    });
    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, session) => {
      const newUser = session?.user ?? null;
      setUser(newUser);
      if (_event === "PASSWORD_RECOVERY") {
        setPasswordRecovery(true);
      }
      // When a guest logs in, check for local decks to migrate
      if (newUser && _event === "SIGNED_IN") {
        const guestDecks = getAllGuestDecks();
        clearGuestData();
        if (guestDecks.length > 0) {
          setMigrating(true);
          setLoading(true); // force loading state immediately
          setDecks([]);
          handleMigrateDecks(guestDecks, newUser);
        }
      }
    });
    return () => subscription.unsubscribe();
  }, []);

  async function fetchDecks() {
    setLoading(true);
    try {
      let data;
      if (user) {
        data = await getStudySets();
      } else {
        const dismissed = getDismissedExamples();
        const pinnedExamples = getPinnedExamples();
        const exampleStats = JSON.parse(
          localStorage.getItem("studysprinter_example_stats") || "{}",
        );
        const examples = EXAMPLE_DECKS.filter(
          (d) => !dismissed.includes(d.id),
        ).map((d) => ({
          ...d,
          created_at: getExampleFirstSeen(d.id),
          last_studied: exampleStats[d.id]?.last_reviewed || null,
          pinned: pinnedExamples.includes(d.id),
        }));
        data = [...getGuestStudySets(), ...examples];
      }
      const sorted = data.sort((a, b) => {
        if ((a.pinned || false) !== (b.pinned || false))
          return (b.pinned ? 1 : 0) - (a.pinned ? 1 : 0);
        const aDate = a.last_studied || a.created_at;
        const bDate = b.last_studied || b.created_at;
        return new Date(bDate) - new Date(aDate);
      });
      setDecks(sorted);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }

  async function handleSelectDeck(id) {
    try {
      setSelectedDeck(null);
      const exampleDeck = EXAMPLE_DECKS.find((d) => d.id === id);
      if (exampleDeck) {
        setSelectedDeck(exampleDeck);
        setView("study");
        if (window.innerWidth <= 768) setSidebarOpen(false);
        return;
      }
      const data = user ? await getStudySet(id) : getGuestStudySet(id);
      const sidebarDeck = decks.find((d) => d.id === id);
      setSelectedDeck({ ...data, created_at: sidebarDeck?.created_at });
      setView("study");
      if (window.innerWidth <= 768) setSidebarOpen(false);
    } catch (e) {
      console.error(e);
    }
  }

  function handleStatsRecorded() {
    const now = new Date().toISOString();
    setDecks((prev) =>
      prev.map((d) =>
        d.id === selectedDeck?.id ? { ...d, last_studied: now } : d,
      ),
    );
  }

  async function handleDeleteAccount() {
    try {
      await deleteAccount();
    } catch (e) {
      console.error(e);
      alert("Failed to delete account. Please try again.");
      return;
    }
    setShowDeleteAccountConfirm(false);
    // Clear Supabase session from localStorage manually
    Object.keys(localStorage).forEach((key) => {
      if (key.startsWith("sb-")) localStorage.removeItem(key);
    });
    setUser(null);
  }

  async function handleDeleteDeck(id) {
    if (EXAMPLE_DECKS.find((d) => d.id === id)) {
      dismissExampleDeck(id);
      setDecks(decks.filter((d) => d.id !== id));
      if (selectedDeck?.id === id) {
        setSelectedDeck(null);
        setView("empty");
      }
      return;
    }
    user ? await deleteStudySet(id) : deleteGuestStudySet(id);
    setDecks(decks.filter((d) => d.id !== id));
    if (selectedDeck?.id === id) {
      setSelectedDeck(null);
      setView("empty");
    }
  }

  async function handlePinDeck(id) {
    if (EXAMPLE_DECKS.find((d) => d.id === id)) {
      const result = toggleExamplePin(id);
      setDecks((prev) => {
        const updated = prev.map((d) =>
          d.id === id ? { ...d, pinned: result.pinned } : d,
        );
        const pinned = updated.filter((d) => d.pinned);
        const unpinned = updated
          .filter((d) => !d.pinned)
          .sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
        return [...pinned, ...unpinned];
      });
      return;
    }
    try {
      const result = user ? await togglePin(id) : toggleGuestPin(id);
      setDecks((prev) => {
        const updated = prev.map((d) =>
          d.id === id ? { ...d, pinned: result.pinned } : d,
        );
        const pinned = updated.filter((d) => d.pinned);
        const unpinned = updated
          .filter((d) => !d.pinned)
          .sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
        return [...pinned, ...unpinned];
      });
    } catch (e) {
      console.error(e);
    }
  }

  function handleDeckCreated(deck) {
    if (!user) {
      const savedDeck = saveGuestDeck(deck);
      setDecks([savedDeck, ...decks]);
      setSelectedDeck(savedDeck);
      setView("study");
      if (!nudgeShownRef.current) {
        setShowSaveNudge(true);
        nudgeShownRef.current = true;
      }
      return;
    }
    setDecks([deck, ...decks]);
    setSelectedDeck(deck);
    setView("study");
  }

  async function handleMigrateDecks(decksToMigrate, currentUser) {
    const token = (await supabase.auth.getSession()).data.session?.access_token;

    const exampleStats = JSON.parse(
      localStorage.getItem("studysprinter_example_stats") || "{}",
    );

    // Wait for ALL imports to finish before doing anything else
    await Promise.all(
      decksToMigrate.map(async (deck) => {
        try {
          const deckStats = deck.stats ||
            exampleStats[deck.id] || { times_reviewed: 0, best_score: null };
          await fetch(
            `${process.env.REACT_APP_BACKEND_URL || "http://localhost:8000"}/import`,
            {
              method: "POST",
              headers: {
                "Content-Type": "application/json",
                Authorization: `Bearer ${token}`,
              },
              body: JSON.stringify({
                title: deck.title,
                notes: deck.notes,
                summary: deck.summary,
                flashcards: deck.flashcards,
                quiz: deck.quiz,
                best_score: deckStats.best_score,
                times_reviewed: deckStats.times_reviewed,
                pinned: deck.pinned || false,
              }),
            },
          );
        } catch (e) {
          console.error("Failed to migrate deck:", deck.title, e);
        }
      }),
    );

    setSelectedDeck(null);
    setView("empty");
    fetchDecks();
    setGlobalStatsKey((prev) => prev + 1);
    setMigrating(false);
  }

  if (passwordRecovery) {
    return <ResetPassword onComplete={() => setPasswordRecovery(false)} />;
  }
  if (authLoading) return null;

  return (
    <div className="layout">
      <header className="main-nav">
        <div className="main-nav-inner">
          <div className="logo">
            <FontAwesomeIcon
              icon={faBookOpen}
              style={{ fontSize: 18, color: "white" }}
            />
          </div>
          <span className="nav-brand">
            Study<span>Sprinter</span>
          </span>
          <button
            className="theme-btn"
            onClick={() => {
              setDark((d) => {
                localStorage.setItem("theme", !d ? "dark" : "light");
                return !d;
              });
            }}
            aria-label={dark ? "Switch to light mode" : "Switch to dark mode"}>
            <FontAwesomeIcon icon={dark ? faSun : faMoon} />
          </button>
          <div style={{ position: "relative" }}>
            {user ? (
              <>
                <button
                  className="theme-btn"
                  onClick={() => setShowUserMenu((p) => !p)}
                  title="Account">
                  {user?.user_metadata?.avatar_url ? (
                    <img
                      src={user.user_metadata.avatar_url}
                      alt="avatar"
                      style={{ width: 20, height: 20, borderRadius: "50%" }}
                      onError={(e) => {
                        e.target.style.display = "none";
                        e.target.nextSibling.style.display = "inline";
                      }}
                    />
                  ) : null}
                  <FontAwesomeIcon
                    icon={faUser}
                    style={{
                      display: user?.user_metadata?.avatar_url
                        ? "none"
                        : "inline",
                    }}
                  />
                </button>
                {showUserMenu && (
                  <div className="user-menu">
                    <div className="user-menu-email">{user?.email}</div>
                    <button
                      className="user-menu-item"
                      onClick={() => {
                        supabase.auth.signOut();
                      }}>
                      Sign out
                    </button>
                    <button
                      className="user-menu-item user-menu-item-danger"
                      onClick={() => {
                        setShowUserMenu(false);
                        setShowDeleteAccountConfirm(true);
                      }}>
                      Delete account
                    </button>
                  </div>
                )}
              </>
            ) : (
              <button
                className="nav-signin-btn"
                onClick={() => setShowLoginModal(true)}>
                Sign in
              </button>
            )}
          </div>
        </div>
      </header>

      <div className="app-body">
        <Sidebar
          decks={decks}
          loading={loading}
          selectedId={selectedDeck?.id}
          onSelect={handleSelectDeck}
          onDelete={handleDeleteDeck}
          onPin={handlePinDeck}
          onNewDeck={() => setView("create")}
          isGenerating={isGenerating}
          isOpen={sidebarOpen}
          onToggle={() => {
            const sidebar = document.querySelector(".sidebar");
            if (sidebar) sidebar.style.transition = "";
            setSidebarOpen((p) => !p);
          }}
        />
        <main className="main-content">
          {showSaveNudge && !user && (
            <div
              className="save-nudge-overlay"
              onClick={() => setShowSaveNudge(false)}>
              <div className="save-nudge" onClick={(e) => e.stopPropagation()}>
                <button
                  className="login-modal-close"
                  onClick={() => setShowSaveNudge(false)}>
                  <FontAwesomeIcon icon={faXmark} />
                </button>
                <div className="save-nudge-title">Deck created!</div>
                <div className="save-nudge-sub">
                  Sign in to save your deck to your account and access it from
                  any device.
                </div>
                <div className="save-nudge-actions">
                  <button
                    className="save-nudge-dismiss"
                    onClick={() => setShowSaveNudge(false)}>
                    Not now
                  </button>
                  <button
                    className="save-nudge-signin"
                    onClick={() => {
                      setShowSaveNudge(false);
                      setShowLoginModal(true);
                    }}>
                    Sign in
                  </button>
                </div>
              </div>
            </div>
          )}
          {view !== "create" && (
            <button
              className="mobile-fab"
              onClick={() => setView("create")}
              disabled={isGenerating}>
              <FontAwesomeIcon icon={faPlus} />
            </button>
          )}
          {view === "empty" && (
            <div className="empty-state">
              <div className="empty-title">No deck selected</div>
              <div className="empty-sub">
                Pick a deck from the left or create a new one to get started.
              </div>
              <button
                className="btn-primary"
                style={{ marginTop: "1.5rem" }}
                onClick={() => setView("create")}>
                Create a deck
              </button>
            </div>
          )}
          {view === "create" && (
            <CreateDeck
              onDeckCreated={handleDeckCreated}
              onCancel={() => setView(selectedDeck ? "study" : "empty")}
              onGeneratingChange={setIsGenerating}
            />
          )}
          {view === "study" && selectedDeck && (
            <StudyView
              deck={selectedDeck}
              onStatsRecorded={handleStatsRecorded}
              isGuest={!user}
              globalStatsKey={globalStatsKey}
            />
          )}
        </main>
      </div>

      {/* Login modal overlay */}
      {showLoginModal && (
        <div
          className="delete-overlay"
          onClick={() => setShowLoginModal(false)}>
          <div
            className="login-modal-container"
            onClick={(e) => e.stopPropagation()}>
            <Login
              onSuccess={() => setShowLoginModal(false)}
              onClose={() => setShowLoginModal(false)}
            />
          </div>
        </div>
      )}

      {/* Delete account confirmation */}
      {showDeleteAccountConfirm && (
        <div
          className="delete-overlay"
          onClick={() => setShowDeleteAccountConfirm(false)}>
          <div className="delete-modal" onClick={(e) => e.stopPropagation()}>
            <div className="delete-modal-title">Delete your account?</div>
            <div className="delete-modal-sub">
              This will permanently delete your account and all your decks,
              flashcards, quiz questions, and stats. This action cannot be
              undone.
            </div>
            <div className="delete-modal-actions">
              <button
                className="delete-cancel-btn"
                onClick={() => setShowDeleteAccountConfirm(false)}>
                Cancel
              </button>
              <button
                className="delete-confirm-btn"
                onClick={handleDeleteAccount}>
                Delete account
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
