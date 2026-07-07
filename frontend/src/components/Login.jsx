import React, { useState } from "react";
import { supabase } from "../supabase";
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import { faBookOpen } from "@fortawesome/free-solid-svg-icons";
import "../styles/base.css";
import "../styles/auth.css";

export default function Login({ onSuccess, onClose }) {
  const [mode, setMode] = useState("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  async function handleGoogleLogin() {
    await supabase.auth.signInWithOAuth({
      provider: "google",
      options: {
        redirectTo: window.location.origin,
      },
    });
  }

  async function handleEmailAuth() {
    setError("");
    setMessage("");
    if (!email || !password) {
      setError("Please enter your email and password.");
      return;
    }
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(email)) {
      setError("Please enter a valid email address.");
      return;
    }
    if (password.length < 6) {
      setError("Password must be at least 6 characters.");
      return;
    }
    if (mode === "signup" && password !== confirmPassword) {
      setError("Passwords do not match.");
      return;
    }
    setLoading(true);
    try {
      if (mode === "signup") {
        const { error } = await supabase.auth.signUp({ email, password });
        if (error) {
          if (error.message.includes("already registered")) {
            throw new Error(
              "An account with this email already exists. Try signing in instead.",
            );
          }
          if (error.message.includes("Password should contain")) {
            throw new Error(
              "Password must include at least one uppercase letter, one lowercase letter, one number, and one symbol.",
            );
          }
          throw error;
        }
        setMessage(
          "Almost there! Check your inbox and click the confirmation link to finish signing up.",
        );
      } else {
        const { error } = await supabase.auth.signInWithPassword({
          email,
          password,
        });
        if (error) {
          if (error.message.includes("Invalid login credentials")) {
            throw new Error(
              "Incorrect email or password. If you signed up with Google, try that instead.",
            );
          }
          if (error.message.includes("Email not confirmed")) {
            throw new Error(
              "Please confirm your email first. Check your inbox for the confirmation link.",
            );
          }
          throw error;
        }
        if (onSuccess) onSuccess();
      }
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  async function handlePasswordReset() {
    setError("");
    setMessage("");
    if (!email) {
      setError("Please enter your email address first.");
      return;
    }
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(email)) {
      setError("Please enter a valid email address.");
      return;
    }
    setLoading(true);
    try {
      const { error } = await supabase.auth.resetPasswordForEmail(email, {
        redirectTo: `${window.location.origin}/reset-password`,
      });
      if (error) throw error;
      setMessage("Password reset link sent! Check your inbox.");
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="login-card">
      {onClose && (
        <button className="login-modal-close" onClick={onClose}>
          ✕
        </button>
      )}
      <div className="login-logo">
        <FontAwesomeIcon
          icon={faBookOpen}
          style={{ fontSize: 28, color: "white" }}
        />
      </div>
      <h1 className="login-title">StudySprinter</h1>
      <p className="login-sub">
        {mode === "signup"
          ? "Create an account to get started."
          : "Turn your notes into flashcards and quizzes instantly."}
      </p>
      <button
        className="login-google-btn"
        onClick={handleGoogleLogin}
        disabled={loading}>
        <img
          src="https://www.google.com/favicon.ico"
          alt="Google"
          width={18}
          height={18}
        />
        {mode === "signup" ? "Sign up with Google" : "Sign in with Google"}
      </button>
      <div className="login-divider">
        <span>or</span>
      </div>

      <input
        className="login-input"
        type="email"
        placeholder="Email"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        disabled={loading}
      />
      <input
        className="login-input"
        type="password"
        placeholder="Password"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        onKeyDown={(e) => e.key === "Enter" && handleEmailAuth()}
        disabled={loading}
      />

      {mode === "login" && (
        <div style={{ textAlign: "right", marginBottom: 10 }}>
          <button
            onClick={handlePasswordReset}
            disabled={loading}
            style={{
              background: "none",
              border: "none",
              color: "#059669",
              fontSize: 13,
              cursor: "pointer",
              padding: 0,
            }}>
            Forgot password?
          </button>
        </div>
      )}

      {mode === "signup" && (
        <input
          className="login-input"
          type="password"
          placeholder="Confirm password"
          value={confirmPassword}
          onChange={(e) => setConfirmPassword(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleEmailAuth()}
          disabled={loading}
        />
      )}

      {error && <div className="login-error">{error}</div>}
      {message && <div className="login-message">{message}</div>}

      <button
        className="btn-primary"
        style={{ width: "100%", marginTop: 12 }}
        onClick={handleEmailAuth}
        disabled={loading}>
        {loading ? "Loading..." : mode === "login" ? "Sign in" : "Sign up"}
      </button>

      <div className="login-switch">
        {mode === "login" ? (
          <>
            Don't have an account?{" "}
            <button
              onClick={() => {
                setMode("signup");
                setEmail("");
                setPassword("");
                setConfirmPassword("");
                setError("");
                setMessage("");
              }}>
              Sign up
            </button>{" "}
          </>
        ) : (
          <>
            Already have an account?{" "}
            <button
              onClick={() => {
                setMode("login");
                setEmail("");
                setPassword("");
                setConfirmPassword("");
                setError("");
                setMessage("");
              }}>
              Sign in
            </button>{" "}
          </>
        )}
      </div>
    </div>
  );
}
