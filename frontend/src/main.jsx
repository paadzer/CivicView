import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import "./styles.css";

class ErrorBoundary extends React.Component {
  state = { hasError: false, error: null };
  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }
  componentDidCatch(error, info) {
    console.error("App error:", error, info);
  }
  render() {
    if (this.state.hasError && this.state.error) {
      return (
        <div style={{ padding: "2rem", fontFamily: "sans-serif", maxWidth: "600px" }}>
          <h1>Something went wrong</h1>
          <pre style={{ background: "#f0f0f0", padding: "1rem", overflow: "auto" }}>
            {this.state.error.message}
          </pre>
          <p>Check the browser console (F12) for more details.</p>
        </div>
      );
    }
    return this.props.children;
  }
}

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <ErrorBoundary>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </ErrorBoundary>
  </React.StrictMode>
);


