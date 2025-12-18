/**
 * Frontend configuration constants.
 * Centralizes magic strings and default values.
 */

export const CONFIG = {
    // Models
    DEFAULT_MODEL: "google/gemini-2.0-flash-exp:free",
    FALLBACK_MODEL: "meta-llama/llama-3.2-3b-instruct:free",
    
    // Timing
    POLL_DELAYS: [500, 2000, 5000],  // Graph refresh polling intervals (ms)
    REQUEST_TIMEOUT_MS: 60000,
    LOADING_WARNING_THRESHOLD_S: 5,  // Show warning after N seconds
    
    // RAG
    RAG_SCORE_THRESHOLD: 0.4,
    
    // Chat defaults
    DEFAULT_TEMPERATURE: 0.7,
    DEFAULT_MAX_TOKENS: 1024,
    
    // UI
    API_HEADERS: { "Content-Type": "application/json" },
};

/**
 * CSS variable colors for programmatic use.
 */
export const COLORS = {
    green: "var(--ctp-green)",
    red: "var(--ctp-red)",
    blue: "var(--ctp-blue)",
    peach: "var(--ctp-peach)",
    teal: "var(--ctp-teal)",
    surface2: "var(--ctp-surface2)",
    subtext0: "var(--ctp-subtext0)",
};
