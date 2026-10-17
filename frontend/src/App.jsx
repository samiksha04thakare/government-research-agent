import { useState, useEffect, useRef } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { SUPPORTED_LANGUAGES, UI_TRANSLATIONS, DOMAIN_CATEGORIES_BY_LANG } from "./i18n";

const API = import.meta.env.VITE_API_URL || "";

async function safeParseJson(res) {
  const contentType = res.headers.get("content-type") || "";
  if (contentType.includes("application/json")) {
    try {
      return await res.json();
    } catch {
      return null;
    }
  }
  return null;
}

// Clean markdown and meta tags for clean browser TTS speech
function cleanTextForSpeech(text) {
  if (!text) return "";
  return text
    .replace(/```[\s\S]*?```/g, "")
    .replace(/`([^`]+)`/g, "$1")
    .replace(/\[\^?\d+\]/g, "")
    .replace(/\[([^\]]+)\]\([^)]+\)/g, "$1")
    .replace(/[*_#~>|]/g, " ")
    .replace(/-{3,}/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function splitTextIntoSentences(text, maxLen = 140) {
  const cleaned = cleanTextForSpeech(text);
  if (!cleaned) return [];
  const rawSentences = cleaned.split(/(?<=[.?!।\n])\s+/);
  const chunks = [];
  for (const s of rawSentences) {
    const trimmed = s.trim();
    if (!trimmed) continue;
    if (trimmed.length <= maxLen) {
      chunks.push(trimmed);
    } else {
      const subParts = trimmed.split(/(?<=[,;:])\s+/);
      let buffer = "";
      for (const p of subParts) {
        if ((buffer + " " + p).trim().length <= maxLen) {
          buffer = (buffer + " " + p).trim();
        } else {
          if (buffer) chunks.push(buffer);
          buffer = p.trim();
        }
      }
      if (buffer) chunks.push(buffer);
    }
  }
  return chunks.length ? chunks : [cleaned.slice(0, maxLen)];
}

// Helper for scheme category photo mappings matching design mockup
function getSchemeCategoryPhoto(category) {
  const cat = (category || "").toLowerCase();
  if (cat.includes("agri") || cat.includes("farmer") || cat.includes("kisan") || cat.includes("crop") || cat.includes("soil") || cat.includes("pest") || cat.includes("fertilizer") || cat.includes("wheat") || cat.includes("rice")) {
    return {
      photo: "/assets/scheme_cat_farmer.jpg",
      fallback: "/assets/card_farmer.jpg",
      icon: "🌾",
      themeClass: "card-theme-farmer",
      color: "#166534",
      label: "कृषि एवं किसान कल्याण (Agriculture & Farmer Welfare)",
    };
  }
  if (cat.includes("edu") || cat.includes("scholar") || cat.includes("छात्रवृत्ति") || cat.includes("matric") || cat.includes("student") || cat.includes("university")) {
    return {
      photo: "/assets/scheme_cat_scholarship.jpg",
      fallback: "/assets/card_scholarship.jpg",
      icon: "🎓",
      themeClass: "card-theme-scholarship",
      color: "#1d4ed8",
      label: "शिक्षा एवं छात्रवृत्ति (Education & Scholarships)",
    };
  }
  if (cat.includes("credit") || cat.includes("msme") || cat.includes("mudra") || cat.includes("loan") || cat.includes("entrepreneur") || cat.includes("उद्योग") || cat.includes("stand-up") || cat.includes("pmegp") || cat.includes("startup")) {
    return {
      photo: "/assets/scheme_cat_entrepreneur.jpg",
      fallback: "/assets/card_entrepreneur.jpg",
      icon: "💼",
      themeClass: "card-theme-entrepreneurship",
      color: "#c2410c",
      label: "सूक्ष्म, लघु व मध्यम उद्यम एवं उद्यमिता (MSME & Entrepreneurship)",
    };
  }
  if (cat.includes("women") || cat.includes("child") || cat.includes("mahila") || cat.includes("girl") || cat.includes("महिला") || cat.includes("wcd") || cat.includes("ujjwala") || cat.includes("matritva") || cat.includes("ladki")) {
    return {
      photo: "/assets/scheme_cat_women.jpg",
      fallback: "/assets/card_women.jpg",
      icon: "👩",
      themeClass: "card-theme-women",
      color: "#be185d",
      label: "महिला एवं बाल विकास (Women & Child Welfare)",
    };
  }
  return {
    photo: "/assets/scheme_cat_other.jpg",
    fallback: "/assets/card_other.jpg",
    icon: "🏛️",
    themeClass: "card-theme-other",
    color: "#6d28d9",
    label: "सामाजिक सुरक्षा व लोक कल्याण (Social Security & Welfare)",
  };
}

export default function App() {
  // Navigation State: 'dashboard' is the MAIN DASHBOARD view
  const [activeTab, setActiveTab] = useState("dashboard");

  // Core Search & Language State
  const [question, setQuestion] = useState("");
  const [selectedLang, setSelectedLang] = useState(() => {
    const saved = localStorage.getItem("gov_language");
    return saved && ["en", "hi", "mr"].includes(saved) ? saved : "hi";
  });
  const t = UI_TRANSLATIONS[selectedLang] || UI_TRANSLATIONS.hi;
  const domainCategories = DOMAIN_CATEGORIES_BY_LANG[selectedLang] || DOMAIN_CATEGORIES_BY_LANG.hi;

  function handleLanguageChange(newLang) {
    setSelectedLang(newLang);
    try {
      localStorage.setItem("gov_language", newLang);
    } catch {}
    const currentQ = (question || result?.question || "").trim();
    if (currentQ && activeTab === "ask-ai") {
      ask(null, currentQ, newLang);
    }
  }

  // Research Result State
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  // History State
  const [history, setHistory] = useState([]);
  const [clearingHistory, setClearingHistory] = useState(false);

  // System Health & Stats
  const [health, setHealth] = useState(null);

  // Schemes Directory State
  const [structuredSchemes, setStructuredSchemes] = useState([]);
  const [schemeSearch, setSchemeSearch] = useState("");
  const [schemeCategoryFilter, setSchemeCategoryFilter] = useState("all");
  const [selectedScheme, setSelectedScheme] = useState(null);
  const [schemeSubTab, setSchemeSubTab] = useState("overview");

  // Documents Management State
  const [documentsList, setDocumentsList] = useState([]);
  const [docSearch, setDocSearch] = useState("");
  const [docSubTab, setDocSubTab] = useState("my-docs");
  const [docCategoryFilter, setDocCategoryFilter] = useState("all");
  const [selectedDoc, setSelectedDoc] = useState(null);
  const [docReaderLoading, setDocReaderLoading] = useState(false);
  const [uploadingDoc, setUploadingDoc] = useState(false);
  const [uploadStatus, setUploadStatus] = useState("");
  const [sourcesRegistry, setSourcesRegistry] = useState([]);
  const fileInputRef = useRef(null);

  // Extract Scheme Modal State
  const [showExtractModal, setShowExtractModal] = useState(false);
  const [extractText, setExtractText] = useState("");
  const [extractStatus, setExtractStatus] = useState("");
  const [extracting, setExtracting] = useState(false);

  // Settings & Preferences State
  const [showSourcesInAnswer, setShowSourcesInAnswer] = useState(true);
  const [autoSearchOnSpeech, setAutoSearchOnSpeech] = useState(false);
  const [theme, setTheme] = useState(() => localStorage.getItem("gov_theme") || "light");
  const [keyProvider, setKeyProvider] = useState("groq");
  const [apiKeyInput, setApiKeyInput] = useState("");
  const [keySaveStatus, setKeySaveStatus] = useState("");
  const [savingKey, setSavingKey] = useState(false);
  const [showApiKeyModal, setShowApiKeyModal] = useState(false);

  // Voice Speech-to-Text (STT) State
  const [isListening, setIsListening] = useState(false);
  const [listeningTarget, setListeningTarget] = useState(null);
  const [speechError, setSpeechError] = useState("");
  const [liveTranscript, setLiveTranscript] = useState("");
  const recognitionRef = useRef(null);

  // Voice Text-to-Speech (TTS) State
  const [ttsPlaying, setTtsPlaying] = useState(false);
  const [ttsPaused, setTtsPaused] = useState(false);
  const [ttsSource, setTtsSource] = useState("");
  const [ttsCurrentChunk, setTtsCurrentChunk] = useState(0);
  const [ttsTotalChunks, setTtsTotalChunks] = useState(0);
  const [ttsRate, setTtsRate] = useState(1.0);
  const ttsQueueRef = useRef([]);
  const ttsIndexRef = useRef(0);
  const ttsActiveRef = useRef(false);
  const ttsLangRef = useRef("hi");
  const ttsRateRef = useRef(1.0);

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem("gov_theme", theme);
  }, [theme]);

  const toggleTheme = () => {
    setTheme((prev) => (prev === "light" ? "dark" : "light"));
  };

  useEffect(() => {
    fetchHealth();
    fetchHistory();
    fetchStructuredSchemes();
    fetchDocuments();
    fetchSourcesRegistry();
    return () => {
      stopTts();
      stopVoiceInput();
    };
  }, []);

  async function fetchHealth() {
    try {
      const res = await fetch(`${API}/health`);
      if (res.ok) {
        const data = await safeParseJson(res);
        if (data) setHealth(data);
      }
    } catch {}
  }

  async function fetchHistory() {
    try {
      const res = await fetch(`${API}/history`);
      if (res.ok) {
        const data = await safeParseJson(res);
        if (data && Array.isArray(data)) setHistory(data);
      }
    } catch {}
  }

  async function fetchStructuredSchemes() {
    try {
      const res = await fetch(`${API}/schemes`);
      if (res.ok) {
        const data = await safeParseJson(res);
        if (data) {
          const list = Array.isArray(data) ? data : data.items || [];
          const unique = [];
          const seen = new Set();
          for (const item of list) {
            const key = item.scheme_id || item.scheme_name;
            if (!seen.has(key)) {
              seen.add(key);
              unique.push(item);
            }
          }
          setStructuredSchemes(unique);
        }
      }
    } catch (err) {
      console.error("Failed to fetch schemes:", err);
    }
  }

  async function fetchDocuments() {
    try {
      const res = await fetch(`${API}/documents`);
      if (res.ok) {
        const data = await safeParseJson(res);
        if (data && Array.isArray(data)) setDocumentsList(data);
      }
    } catch (err) {
      console.error("Failed to fetch documents:", err);
    }
  }

  async function fetchSourcesRegistry() {
    try {
      const res = await fetch(`${API}/sources/registry`);
      if (res.ok) {
        const data = await safeParseJson(res);
        if (data && Array.isArray(data)) setSourcesRegistry(data);
      }
    } catch {}
  }

  async function handleClearAllHistory() {
    if (!window.confirm("Are you sure you want to clear all research search history?")) return;
    setClearingHistory(true);
    try {
      const res = await fetch(`${API}/history`, { method: "DELETE" });
      if (res.ok) setHistory([]);
    } catch (err) {
      console.error("Failed to clear history:", err);
    } finally {
      setClearingHistory(false);
    }
  }

  async function handleDeleteHistoryItem(e, id) {
    e.stopPropagation();
    try {
      const res = await fetch(`${API}/history/${id}`, { method: "DELETE" });
      if (res.ok) {
        setHistory((prev) => prev.filter((item) => item.id !== id));
      }
    } catch (err) {
      console.error("Failed to delete history item:", err);
    }
  }

  async function handleSaveKey(e) {
    e.preventDefault();
    if (!apiKeyInput.trim()) return;
    setSavingKey(true);
    setKeySaveStatus("Saving and activating key...");
    try {
      const res = await fetch(`${API}/config/api-key`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ provider: keyProvider, api_key: apiKeyInput.trim() }),
      });
      const data = await safeParseJson(res);
      if (!res.ok) throw new Error(data?.detail || `Failed to update key (status ${res.status})`);
      setKeySaveStatus(`✅ Successfully activated ${data?.llm_model || "Key"}!`);
      setApiKeyInput("");
      fetchHealth();
    } catch (err) {
      setKeySaveStatus(`❌ Error: ${err.message}`);
    } finally {
      setSavingKey(false);
    }
  }

  async function handleExtractScheme(e) {
    e.preventDefault();
    if (!extractText.trim()) return;
    setExtracting(true);
    setExtractStatus("Extracting and normalizing structured scheme fields...");
    try {
      const res = await fetch(`${API}/schemes/extract`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Admin-Token": "admin123",
        },
        body: JSON.stringify({ text: extractText.trim() }),
      });
      const data = await safeParseJson(res);
      if (!res.ok) throw new Error(data?.detail || `Extraction failed (status ${res.status})`);
      setExtractStatus(`✅ Successfully extracted & saved: ${data.saved?.scheme_name || "Scheme"}!`);
      setExtractText("");
      fetchStructuredSchemes();
      fetchHealth();
    } catch (err) {
      setExtractStatus(`❌ Error: ${err.message}`);
    } finally {
      setExtracting(false);
    }
  }

  async function handleFileUpload(e) {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploadingDoc(true);
    const fname = file.name.toLowerCase();

    try {
      if (fname.endsWith(".csv") || fname.endsWith(".json")) {
        const endpoint = fname.endsWith(".csv") ? `${API}/scraper/import-csv` : `${API}/scraper/import-json`;
        setUploadStatus(fname.endsWith(".csv") ? "Processing and validating scraped CSV schemes..." : "Processing and validating scraped JSON schemes...");
        const formData = new FormData();
        formData.append("file", file);

        const res = await fetch(endpoint, {
          method: "POST",
          body: formData,
        });
        const data = await safeParseJson(res);
        if (!res.ok) throw new Error(data?.detail || "Import failed");

        setUploadStatus(`✅ Imported ${data.records_imported || 0} schemes (${data.chunks_indexed || 0} chunks indexed in ChromaDB)!`);
        fetchSchemes();
        fetchDocuments();
        fetchHealth();
        if (fileInputRef.current) fileInputRef.current.value = "";
        return;
      }

      setUploadStatus("Uploading official document...");
      const formData = new FormData();
      formData.append("file", file);
      formData.append("title", file.name.replace(/\.[^/.]+$/, "").replace(/_/g, " "));
      formData.append("authority", "Official Government Authority");
      formData.append("source_url", "");

      const res = await fetch(`${API}/documents/upload`, {
        method: "POST",
        headers: { "X-Admin-Token": "admin123" },
        body: formData,
      });
      const data = await safeParseJson(res);
      if (!res.ok) throw new Error(data?.detail || "Document upload failed");

      setUploadStatus("Indexing document chunks into vector database...");
      await fetch(`${API}/documents/index`, {
        method: "POST",
        headers: { "X-Admin-Token": "admin123" },
      });

      setUploadStatus(`✅ Successfully indexed ${file.name}!`);
      fetchDocuments();
      fetchHealth();
      if (fileInputRef.current) fileInputRef.current.value = "";
    } catch (err) {
      setUploadStatus(`❌ Upload failed: ${err.message}`);
    } finally {
      setUploadingDoc(false);
    }
  }

  async function openDocumentReader(docId) {
    setDocReaderLoading(true);
    try {
      const res = await fetch(`${API}/documents/${docId}/text`);
      if (res.ok) {
        const data = await safeParseJson(res);
        if (data) setSelectedDoc(data);
      }
    } catch (err) {
      console.error("Failed to load document text:", err);
    } finally {
      setDocReaderLoading(false);
    }
  }

  // Core Ask AI function
  async function ask(e, customQuery, langOverride) {
    if (e) e.preventDefault();
    const q = (customQuery !== undefined ? customQuery : question).trim();
    if (q.length < 3) return;

    const targetLang = langOverride || selectedLang || "hi";
    setLoading(true);
    setError("");
    setResult(null);
    stopTts();
    stopVoiceInput();
    setActiveTab("ask-ai");

    try {
      const res = await fetch(`${API}/research`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: q, language: targetLang }),
      });

      const data = await safeParseJson(res);
      if (!res.ok) throw new Error(data?.detail || `Request failed with status ${res.status}`);
      if (!data) throw new Error("Server returned an invalid non-JSON response.");

      setResult({ ...data, question: q, language: data.language || targetLang });
      fetchHistory();
      fetchHealth();
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  // TTS Controller
  function stopTts() {
    ttsActiveRef.current = false;
    ttsQueueRef.current = [];
    ttsIndexRef.current = 0;
    if (window.speechSynthesis) {
      try {
        window.speechSynthesis.cancel();
      } catch {}
    }
    setTtsPlaying(false);
    setTtsPaused(false);
    setTtsSource("");
    setTtsCurrentChunk(0);
    setTtsTotalChunks(0);
  }

  function pauseTts() {
    if (window.speechSynthesis && window.speechSynthesis.speaking && !window.speechSynthesis.paused) {
      try {
        window.speechSynthesis.pause();
        setTtsPaused(true);
      } catch {}
    }
  }

  function resumeTts() {
    if (window.speechSynthesis && window.speechSynthesis.paused) {
      try {
        window.speechSynthesis.resume();
        setTtsPaused(false);
      } catch {}
    }
  }

  function changeTtsRate(rate) {
    setTtsRate(rate);
    ttsRateRef.current = rate;
    if (ttsActiveRef.current && !ttsPaused) {
      if (window.speechSynthesis) {
        try {
          window.speechSynthesis.cancel();
          playNextTtsChunk();
        } catch {}
      }
    }
  }

  function playNextTtsChunk() {
    if (!ttsActiveRef.current) return;
    const queue = ttsQueueRef.current;
    const idx = ttsIndexRef.current;
    if (idx >= queue.length) {
      stopTts();
      return;
    }
    setTtsCurrentChunk(idx + 1);
    const chunkText = queue[idx];
    if (!chunkText || !chunkText.trim()) {
      ttsIndexRef.current += 1;
      playNextTtsChunk();
      return;
    }

    try {
      const utterance = new SpeechSynthesisUtterance(chunkText);
      utterance.rate = ttsRateRef.current;
      const targetLang = ttsLangRef.current;
      const voices = (window.speechSynthesis && window.speechSynthesis.getVoices()) || [];
      let matchedVoice = null;
      if (targetLang === "hi") {
        matchedVoice = voices.find((v) => v.lang.toLowerCase().startsWith("hi") || v.name.toLowerCase().includes("hindi"));
      } else if (targetLang === "mr") {
        matchedVoice =
          voices.find((v) => v.lang.toLowerCase().startsWith("mr") || v.name.toLowerCase().includes("marathi")) ||
          voices.find((v) => v.lang.toLowerCase().startsWith("hi"));
      } else {
        matchedVoice =
          voices.find((v) => v.lang.toLowerCase().startsWith("en-in") || v.name.toLowerCase().includes("india")) ||
          voices.find((v) => v.lang.toLowerCase().startsWith("en"));
      }

      if (matchedVoice) {
        utterance.voice = matchedVoice;
      } else if (targetLang === "hi" || targetLang === "mr") {
        utterance.lang = "hi-IN";
      } else {
        utterance.lang = "en-IN";
      }

      utterance.onend = () => {
        if (ttsActiveRef.current) {
          ttsIndexRef.current += 1;
          playNextTtsChunk();
        }
      };

      utterance.onerror = (e) => {
        if (e.error !== "canceled" && e.error !== "interrupted") {
          console.warn("TTS error:", e);
        }
        if (ttsActiveRef.current) {
          ttsIndexRef.current += 1;
          playNextTtsChunk();
        }
      };

      window.speechSynthesis.speak(utterance);
    } catch (err) {
      console.error("Failed to speak utterance:", err);
      stopTts();
    }
  }

  function playTts(text, sourceId, language = "hi") {
    if (!window.speechSynthesis) {
      alert("Text-to-speech is not supported in this browser.");
      return;
    }
    if (ttsPlaying && ttsSource === sourceId) {
      if (ttsPaused) resumeTts();
      else pauseTts();
      return;
    }

    stopTts();
    const chunks = splitTextIntoSentences(text);
    if (!chunks.length) return;

    ttsQueueRef.current = chunks;
    ttsIndexRef.current = 0;
    ttsActiveRef.current = true;
    ttsLangRef.current = language || "hi";
    ttsRateRef.current = ttsRate;

    setTtsPlaying(true);
    setTtsPaused(false);
    setTtsSource(sourceId);
    setTtsTotalChunks(chunks.length);
    setTtsCurrentChunk(1);

    playNextTtsChunk();
  }

  // Voice STT Controller
  function startVoiceInput(target = "search") {
    const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRec) {
      setSpeechError("Speech recognition is not supported in this browser. Please use Chrome, Edge, or a Web Speech API browser.");
      return;
    }

    if (isListening) {
      stopVoiceInput();
      return;
    }

    try {
      const recognition = new SpeechRec();
      recognitionRef.current = recognition;
      recognition.continuous = false;
      recognition.interimResults = true;

      let langCode = "hi-IN";
      if (selectedLang === "en") langCode = "en-IN";
      else if (selectedLang === "mr") langCode = "mr-IN";
      recognition.lang = langCode;

      setIsListening(true);
      setListeningTarget(target);
      setSpeechError("");
      setLiveTranscript("");

      recognition.onresult = (event) => {
        let transcript = "";
        for (let i = event.resultIndex; i < event.results.length; i++) {
          transcript += event.results[i][0].transcript;
        }
        setLiveTranscript(transcript);
        if (event.results[0].isFinal) {
          setQuestion(transcript);
        }
      };

      recognition.onerror = (event) => {
        console.warn("Speech recognition error:", event.error);
        if (event.error === "no-speech") setSpeechError("No speech detected. Please try again.");
        else if (event.error === "not-allowed") setSpeechError("Microphone permission was denied.");
        else setSpeechError(`Voice input error: ${event.error}`);
        setIsListening(false);
        setListeningTarget(null);
      };

      recognition.onend = () => {
        setIsListening(false);
        setListeningTarget(null);
        if (target === "search" && autoSearchOnSpeech) {
          setTimeout(() => {
            setQuestion((curr) => {
              if (curr && curr.trim().length >= 4) {
                ask(null, curr.trim());
              }
              return curr;
            });
          }, 300);
        }
      };

      recognition.start();
    } catch (err) {
      setSpeechError(`Failed to access microphone: ${err.message}`);
      setIsListening(false);
      setListeningTarget(null);
    }
  }

  function stopVoiceInput() {
    if (recognitionRef.current) {
      try {
        recognitionRef.current.stop();
      } catch {}
    }
    setIsListening(false);
    setListeningTarget(null);
  }

  return (
    <div className="gov-app-shell">
      {/* 1. LEFT SIDEBAR NAVIGATION */}
      <aside className="dash-sidebar">
        <div>
          {/* Logo & Brand Header */}
          <div className="dash-sidebar-header">
            <div className="dash-brand-emblem-wrap">
              <span>🏛️</span>
            </div>
            <div className="dash-brand-text">
              <span className="dash-brand-title">AI Government</span>
              <span className="dash-brand-subtitle">Research Agent</span>
            </div>
          </div>

          {/* Navigation Links Menu */}
          <ul className="dash-nav-menu">
            <li>
              <button
                type="button"
                className={`dash-nav-btn ${activeTab === "dashboard" ? "active" : ""}`}
                onClick={() => {
                  setActiveTab("dashboard");
                  setSelectedScheme(null);
                }}
              >
                <span className="dash-nav-icon">🏠</span>
                <span>{t.navDashboard || "Dashboard"}</span>
              </button>
            </li>
            <li>
              <button
                type="button"
                className={`dash-nav-btn ${activeTab === "ask-ai" ? "active" : ""}`}
                onClick={() => {
                  setActiveTab("ask-ai");
                  setSelectedScheme(null);
                }}
              >
                <span className="dash-nav-icon">💬</span>
                <span>{t.navAskAi || "Ask AI"}</span>
              </button>
            </li>
            <li>
              <button
                type="button"
                className={`dash-nav-btn ${activeTab === "schemes" || activeTab === "scheme-details" ? "active" : ""}`}
                onClick={() => {
                  setActiveTab("schemes");
                  setSelectedScheme(null);
                  fetchStructuredSchemes();
                }}
              >
                <span className="dash-nav-icon">🏛️</span>
                <span>{t.navSchemes || "Schemes"}</span>
              </button>
            </li>
            <li>
              <button
                type="button"
                className={`dash-nav-btn ${activeTab === "documents" ? "active" : ""}`}
                onClick={() => {
                  setActiveTab("documents");
                  setSelectedScheme(null);
                  fetchDocuments();
                }}
              >
                <span className="dash-nav-icon">📄</span>
                <span>{t.navDocuments || "Documents"}</span>
              </button>
            </li>
            <li>
              <button
                type="button"
                className={`dash-nav-btn ${activeTab === "history" ? "active" : ""}`}
                onClick={() => {
                  setActiveTab("history");
                  setSelectedScheme(null);
                  fetchHistory();
                }}
              >
                <span className="dash-nav-icon">🕒</span>
                <span>{t.navHistory || "History"}</span>
              </button>
            </li>
            <li>
              <button
                type="button"
                className={`dash-nav-btn ${activeTab === "settings" ? "active" : ""}`}
                onClick={() => {
                  setActiveTab("settings");
                  setSelectedScheme(null);
                }}
              >
                <span className="dash-nav-icon">⚙️</span>
                <span>{t.navSettings || "Settings"}</span>
              </button>
            </li>
          </ul>
        </div>

        {/* Bottom Satyameva Jayate Emblem Watermark */}
        <div className="dash-sidebar-footer">
          <svg className="satyameva-emblem-svg" viewBox="0 0 100 100" fill="currentColor">
            <circle cx="50" cy="50" r="42" fill="none" stroke="currentColor" strokeWidth="3" opacity="0.35" />
            <path d="M50 20 L58 40 L80 40 L62 52 L68 74 L50 62 L32 74 L38 52 L20 40 L42 40 Z" opacity="0.5" />
          </svg>
          <span className="satyameva-caption">सत्यमेव जयते</span>
        </div>
      </aside>

      {/* 2. MAIN APPLICATION WORKSPACE */}
      <div className="dash-main-area">
        {/* Top Header Bar */}
        <header className="dash-top-bar">
          <div className="dash-top-left">
            <span style={{ fontSize: "0.86rem", color: "var(--text-muted)", fontWeight: 600 }}>
              {activeTab === "dashboard" && (selectedLang === "hi" ? "डैशबोर्ड (Home)" : selectedLang === "mr" ? "डॅशबोर्ड (Home)" : "Dashboard (Home)")}
              {activeTab === "ask-ai" && (selectedLang === "hi" ? "Ask AI रिसर्च" : selectedLang === "mr" ? "Ask AI संशोधन" : "Ask AI Research")}
              {activeTab === "schemes" && (selectedLang === "hi" ? "सरकारी योजनाएं" : selectedLang === "mr" ? "शासकीय योजना" : "Government Schemes")}
              {activeTab === "scheme-details" && (selectedScheme?.hindi_name || "Scheme Details")}
              {activeTab === "documents" && (selectedLang === "hi" ? "दस्तावेज़ हब" : selectedLang === "mr" ? "दस्तऐवज हब" : "Documents Hub")}
              {activeTab === "history" && (selectedLang === "hi" ? "खोज इतिहास" : selectedLang === "mr" ? "शोध इतिहास" : "Research History")}
              {activeTab === "settings" && (selectedLang === "hi" ? "सेटिंग्स" : selectedLang === "mr" ? "सेटिंग्ज" : "Settings")}
            </span>
          </div>

          <div className="dash-top-right">
            {/* Language Selector Dropdown */}
            <select
              value={selectedLang}
              onChange={(e) => handleLanguageChange(e.target.value)}
              className="dash-lang-select-btn"
              title="Change Language (भाषा चुनें / भाषा निवडा)"
            >
              <option value="hi">🌐 हिंदी</option>
              <option value="en">🇬🇧 English</option>
              <option value="mr">🚩 मराठी</option>
            </select>

            {/* Status Pill */}
            <div
              className={`status-badge ${health?.has_api_key ? "key-active" : "live"}`}
              style={{ fontSize: "0.78rem", padding: "4px 10px" }}
              title={health?.llm_model}
              onClick={() => setActiveTab("settings")}
            >
              <span className="pulsing-dot" />
              <span>{health?.has_api_key ? "AI Online" : "Vector Grounded"}</span>
            </div>

            {/* Theme Toggle Button */}
            <button type="button" className="theme-toggle-btn" onClick={toggleTheme} title="Toggle Dark/Light Mode">
              {theme === "light" ? "🌙" : "☀️"}
            </button>

            {/* Profile Avatar Icon */}
            <div className="dash-profile-avatar" title="Official Government Agent Portal" onClick={() => setActiveTab("settings")}>
              <span>🏛️</span>
            </div>
          </div>
        </header>

        {/* Dynamic Body Content */}
        <main className="dash-view-body">
          {/* =========================================================================
              SCREEN 1: DASHBOARD (HOME) - THE MAIN DASHBOARD
              ========================================================================= */}
          {activeTab === "dashboard" && (
            <div>
              {/* Hero Banner with Greeting and India Monument Illustration */}
              <div className="dash-hero-container">
                <div className="dash-hero-left">
                  <h1 className="dash-hero-greeting">{t.dashGreeting || "नमस्ते!"}</h1>
                  <p className="dash-hero-sub">
                    {t.dashSubtitle || "सरकारी योजनाओं और आधिकारिक जानकारी के लिए आपका AI रिसर्च एजेंट यहाँ है।"}
                  </p>
                </div>
                <div className="dash-hero-right">
                  <img
                    src="/assets/dashboard_hero_monument.jpg"
                    alt="India Monument Illustration"
                    className="dash-monument-illustration"
                    onError={(e) => {
                      // Graceful fallback if image path needs fallback
                      e.target.style.display = "none";
                    }}
                  />
                </div>
              </div>

              {/* Central Prominent Search Bar */}
              <form
                className="dash-central-search-card"
                onSubmit={(e) => {
                  e.preventDefault();
                  if (question.trim().length >= 3) {
                    ask(null, question.trim());
                  }
                }}
              >
                <span className="dash-search-icon-symbol">🔍</span>
                <input
                  type="text"
                  className="dash-search-text-input"
                  placeholder={t.dashSearchPlaceholder || "अपना सवाल लिखें... (जैसे - PM-KISAN क्या है?)"}
                  value={question}
                  onChange={(e) => setQuestion(e.target.value)}
                />
                <button
                  type="button"
                  className={`voice-mic-btn ${isListening && listeningTarget === "search" ? "listening" : ""}`}
                  style={{ marginRight: "10px", padding: "6px 14px", fontSize: "0.82rem" }}
                  onClick={() => (isListening && listeningTarget === "search" ? stopVoiceInput() : startVoiceInput("search"))}
                  title="Speak your query in Hindi, English, or Marathi"
                >
                  <span>{isListening && listeningTarget === "search" ? "⏹️" : "🎙️"}</span>
                </button>
                <button type="submit" className="dash-search-action-btn">
                  <span>{t.dashSearchBtn || "खोजें"}</span>
                  <span>➔</span>
                </button>
              </form>

              {/* Government Schemes Photo Cards Section (Pixel-Matched to Design Mockup) */}
              <div className="dash-schemes-section">
                <div className="dash-schemes-header-row">
                  <div className="dash-schemes-title-group">
                    <h3>{t.govSchemesHeading || "Government Schemes"}</h3>
                    <p>{t.govSchemesSubtitle || "Find information about various government schemes and benefits"}</p>
                  </div>
                  <button
                    type="button"
                    className="dash-schemes-view-all-btn"
                    onClick={() => {
                      setSchemeCategoryFilter("all");
                      setActiveTab("schemes");
                    }}
                  >
                    <span>{t.viewAllSchemes || "View All Schemes →"}</span>
                  </button>
                </div>

                <div className="dash-photo-categories-grid">
                  {/* Card 1: Farmer Schemes */}
                  <div
                    className="dash-scheme-photo-card card-theme-farmer"
                    onClick={() => {
                      setSchemeCategoryFilter("Agriculture");
                      setActiveTab("schemes");
                    }}
                    title="Farmer Welfare & Credit Schemes"
                  >
                    <div className="dash-card-banner-wrapper">
                      <img
                        src="/assets/scheme_cat_farmer.jpg"
                        alt={t.categoryFarmer || "किसान योजनाएँ"}
                        className="dash-card-banner-img"
                        onError={(e) => {
                          e.target.src = "/assets/card_farmer.jpg";
                        }}
                      />
                      <div className="dash-card-floating-badge">
                        <svg className="dash-badge-icon" width="22" height="22" viewBox="0 0 24 24" fill="currentColor">
                          <path d="M17 8C8 10 5.9 16.17 3.82 21.34L5.71 22l1-2.3A9.49 9.49 0 0 0 12 21a9.92 9.92 0 0 0 8.94-5.53A8.99 8.99 0 0 0 22 10.5V8h-5zm3 2.5c-.01 1.63-.64 3.2-1.78 4.41-.95-2.9-2.76-5.46-5.22-7.41H17v.5c.01.83.67 1.5 1.5 1.5h1.5v1z" />
                        </svg>
                      </div>
                    </div>
                    <div className="dash-card-content">
                      <h4 className="dash-card-title">{t.categoryFarmer || "किसान योजनाएँ"}</h4>
                      <p className="dash-card-desc">{t.categoryFarmerDesc || "PM-KISAN, KCC, फसल बीमा, कृषि उपकरण आदि"}</p>
                      <div className="dash-card-bottom-row">
                        <div className="dash-card-arrow-circle">➔</div>
                      </div>
                    </div>
                  </div>

                  {/* Card 2: Scholarship Schemes */}
                  <div
                    className="dash-scheme-photo-card card-theme-scholarship"
                    onClick={() => {
                      setSchemeCategoryFilter("Education");
                      setActiveTab("schemes");
                    }}
                    title="Scholarships & Higher Education Schemes"
                  >
                    <div className="dash-card-banner-wrapper">
                      <img
                        src="/assets/scheme_cat_scholarship.jpg"
                        alt={t.categoryScholarship || "छात्रवृत्ति"}
                        className="dash-card-banner-img"
                        onError={(e) => {
                          e.target.src = "/assets/card_scholarship.jpg";
                        }}
                      />
                      <div className="dash-card-floating-badge">
                        <svg className="dash-badge-icon" width="22" height="22" viewBox="0 0 24 24" fill="currentColor">
                          <path d="M12 3L1 9l11 6 9-4.91V17h2V9L12 3zm0 8.5L4.82 9 12 5.09 19.18 9 12 11.5zM5 13.18v4L12 21l7-3.82v-4L12 17l-7-3.82z" />
                        </svg>
                      </div>
                    </div>
                    <div className="dash-card-content">
                      <h4 className="dash-card-title">{t.categoryScholarship || "छात्रवृत्ति"}</h4>
                      <p className="dash-card-desc">{t.categoryScholarshipDesc || "शिक्षा छात्रवृत्ति, स्कॉलरशिप, कौशल विकास आदि"}</p>
                      <div className="dash-card-bottom-row">
                        <div className="dash-card-arrow-circle">➔</div>
                      </div>
                    </div>
                  </div>

                  {/* Card 3: Entrepreneurship Schemes */}
                  <div
                    className="dash-scheme-photo-card card-theme-entrepreneurship"
                    onClick={() => {
                      setSchemeCategoryFilter("Credit");
                      setActiveTab("schemes");
                    }}
                    title="MSME & Entrepreneurship Schemes"
                  >
                    <div className="dash-card-banner-wrapper">
                      <img
                        src="/assets/scheme_cat_entrepreneur.jpg"
                        alt={t.categoryEntrepreneurship || "उद्यमिता"}
                        className="dash-card-banner-img"
                        onError={(e) => {
                          e.target.src = "/assets/card_entrepreneur.jpg";
                        }}
                      />
                      <div className="dash-card-floating-badge">
                        <svg className="dash-badge-icon" width="22" height="22" viewBox="0 0 24 24" fill="currentColor">
                          <path d="M12 2a7 7 0 0 0-7 7c0 2.38 1.19 4.47 3 5.74V17a1 1 0 0 0 1 1h6a1 1 0 0 0 1-1v-2.26c1.81-1.27 3-3.36 3-5.74a7 7 0 0 0-7-7zm-3 18a1 1 0 0 0 1 1h4a1 1 0 0 0 1-1v-1H9v1z" />
                        </svg>
                      </div>
                    </div>
                    <div className="dash-card-content">
                      <h4 className="dash-card-title">{t.categoryEntrepreneurship || "उद्यमिता"}</h4>
                      <p className="dash-card-desc">{t.categoryEntrepreneurshipDesc || "मुद्रा लोन, स्टैंड-अप इंडिया, PMEGP, स्टार्टअप सहायता आदि"}</p>
                      <div className="dash-card-bottom-row">
                        <div className="dash-card-arrow-circle">➔</div>
                      </div>
                    </div>
                  </div>

                  {/* Card 4: Women Welfare Schemes */}
                  <div
                    className="dash-scheme-photo-card card-theme-women"
                    onClick={() => {
                      setSchemeCategoryFilter("Women");
                      setActiveTab("schemes");
                    }}
                    title="Women & Child Welfare Schemes"
                  >
                    <div className="dash-card-banner-wrapper">
                      <img
                        src="/assets/scheme_cat_women.jpg"
                        alt={t.categoryWomen || "महिला कल्याण"}
                        className="dash-card-banner-img"
                        onError={(e) => {
                          e.target.src = "/assets/card_women.jpg";
                        }}
                      />
                      <div className="dash-card-floating-badge">
                        <svg className="dash-badge-icon" width="22" height="22" viewBox="0 0 24 24" fill="currentColor">
                          <path d="M12 2a5 5 0 1 0 5 5 5 5 0 0 0-5-5zm0 8a3 3 0 1 1 3-3 3 3 0 0 1-3 3zm9 11v-1a7 7 0 0 0-7-7h-4a7 7 0 0 0-7 7v1h2v-1a5 5 0 0 1 5-5h4a5 5 0 0 1 5 5v1z" />
                        </svg>
                      </div>
                    </div>
                    <div className="dash-card-content">
                      <h4 className="dash-card-title">{t.categoryWomen || "महिला कल्याण"}</h4>
                      <p className="dash-card-desc">{t.categoryWomenDesc || "उज्ज्वला योजना, मातृत्व लाभ, स्वरोजगार, सुरक्षा आदि"}</p>
                      <div className="dash-card-bottom-row">
                        <div className="dash-card-arrow-circle">➔</div>
                      </div>
                    </div>
                  </div>

                  {/* Card 5: Other Schemes */}
                  <div
                    className="dash-scheme-photo-card card-theme-other"
                    onClick={() => {
                      setSchemeCategoryFilter("all");
                      setActiveTab("schemes");
                    }}
                    title="All Other Schemes & Policies"
                  >
                    <div className="dash-card-banner-wrapper">
                      <img
                        src="/assets/scheme_cat_other.jpg"
                        alt={t.categoryOther || "अन्य योजनाएँ"}
                        className="dash-card-banner-img"
                        onError={(e) => {
                          e.target.src = "/assets/card_other.jpg";
                        }}
                      />
                      <div className="dash-card-floating-badge">
                        <svg className="dash-badge-icon" width="22" height="22" viewBox="0 0 24 24" fill="currentColor">
                          <path d="M16 11c1.66 0 2.99-1.34 2.99-3S17.66 5 16 5s-3 1.34-3 3 1.34 3 3 3zm-8 0c1.66 0 2.99-1.34 2.99-3S9.66 5 8 5 5 6.34 5 8s1.34 3 3 3zm0 2c-2.33 0-7 1.17-7 3.5V19h14v-2.5c0-2.33-4.67-3.5-7-3.5zm8 0c-.29 0-.62.02-.97.05 1.16.84 1.97 1.97 1.97 3.45V19h6v-2.5c0-2.33-4.67-3.5-7-3.5z" />
                        </svg>
                      </div>
                    </div>
                    <div className="dash-card-content">
                      <h4 className="dash-card-title">{t.categoryOther || "अन्य योजनाएँ"}</h4>
                      <p className="dash-card-desc">{t.categoryOtherDesc || "स्वास्थ्य, पेंशन, आवास, रोजगार, परिवहन आदि"}</p>
                      <div className="dash-card-bottom-row">
                        <div className="dash-card-arrow-circle">➔</div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              {/* Stats Metrics Row (4 Cards - Pixel-Matched to Screenshot) */}
              <div className="dash-stats-grid">
                <div className="dash-stat-box" onClick={() => setActiveTab("schemes")} style={{ cursor: "pointer" }}>
                  <div className="dash-stat-icon-square" style={{ color: "#2563eb", background: "#eff6ff", borderColor: "#bfdbfe" }}>
                    📄
                  </div>
                  <div className="dash-stat-text-wrap">
                    <span className="dash-stat-number">{t.statTotalSchemesCount || "1,250+"}</span>
                    <span className="dash-stat-label">{t.statTotalSchemesLabel || "सरकारी योजनाएँ"}</span>
                  </div>
                </div>

                <div className="dash-stat-box" onClick={() => setActiveTab("documents")} style={{ cursor: "pointer" }}>
                  <div className="dash-stat-icon-square" style={{ color: "#16a34a", background: "#f0fdf4", borderColor: "#bbf7d0" }}>
                    📖
                  </div>
                  <div className="dash-stat-text-wrap">
                    <span className="dash-stat-number">{t.statTotalDocsCount || "5,680+"}</span>
                    <span className="dash-stat-label">{t.statTotalDocsLabel || "दस्तावेज़ इंडेक्स किए गए"}</span>
                  </div>
                </div>

                <div className="dash-stat-box">
                  <div className="dash-stat-icon-square" style={{ color: "#7c3aed", background: "#f5f3ff", borderColor: "#ddd6fe" }}>
                    ⏱️
                  </div>
                  <div className="dash-stat-text-wrap">
                    <span className="dash-stat-number">{t.statAiAssistCount || "24/7"}</span>
                    <span className="dash-stat-label">{t.statAiAssistLabel || "AI सहायता उपलब्ध"}</span>
                  </div>
                </div>

                <div className="dash-stat-box">
                  <div className="dash-stat-icon-square" style={{ color: "#16a34a", background: "#f0fdf4", borderColor: "#bbf7d0" }}>
                    ✅
                  </div>
                  <div className="dash-stat-text-wrap">
                    <span className="dash-stat-number" style={{ fontSize: "1.02rem" }}>
                      {t.statSourcesUpdateCount || "स्रोत अपडेटेड"}
                    </span>
                    <span className="dash-stat-label">{t.statSourcesUpdateLabel || "अंतिम जाँच: 10 अक्टूबर 2026"}</span>
                  </div>
                </div>
              </div>

              {/* Popular Schemes Tags Section */}
              <div className="dash-popular-container">
                <div className="dash-popular-header">
                  <h3 className="dash-popular-title">{t.popularSchemes || "लोकप्रिय योजनाएं"}</h3>
                  <button
                    type="button"
                    className="dash-view-all-link"
                    onClick={() => {
                      setSchemeCategoryFilter("all");
                      setActiveTab("schemes");
                    }}
                  >
                    <span>{t.viewAllSchemes || "सभी योजनाएं →"}</span>
                  </button>
                </div>
                <div className="dash-popular-chips-wrap">
                  {[
                    { label: "PM-KISAN", query: "पीएम-किसान योजना के तहत ₹6,000 की किस्त और पात्रता क्या है?" },
                    { label: "KCC (किसान क्रेडिट कार्ड)", query: "किसान क्रेडिट कार्ड (KCC) प्राप्त करने की पात्रता और ब्याज दर क्या है?" },
                    { label: "मुद्रा लोन", query: "प्रधानमंत्री मुद्रा योजना के तहत ऋण श्रेणियां और पात्रता क्या हैं?" },
                    { label: "छात्रवृत्ति (NSP)", query: "नेशनल स्कॉलरशिप पोर्टल (NSP) पर मैट्रिकोत्तर छात्रवृत्ति के नियम क्या हैं?" },
                    { label: "उज्ज्वला योजना", query: "प्रधानमंत्री उज्ज्वला योजना के तहत मुफ्त गैस कनेक्शन की पात्रता क्या है?" },
                    { label: "आयुष्मान भारत (PM-JAY)", query: "आयुष्मान भारत योजना के तहत ₹5 लाख का कैशलेस स्वास्थ्य बीमा कैसे मिलता है?" },
                  ].map((p) => (
                    <button
                      key={p.label}
                      type="button"
                      className="dash-scheme-pill-btn"
                      onClick={() => {
                        setQuestion(p.query);
                        ask(null, p.query);
                      }}
                    >
                      {p.label}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* =========================================================================
              SCREEN 2: ASK AI (CHAT & RESEARCH INTERFACE)
              ========================================================================= */}
          {activeTab === "ask-ai" && (
            <div className="askai-split-layout">
              {/* Left Column: Chat Messages & Research Output */}
              <div className="askai-main-column">
                <div className="askai-header-nav">
                  <button type="button" className="askai-back-btn" onClick={() => setActiveTab("dashboard")}>
                    {t.backToDashboard || "← डैशबोर्ड"}
                  </button>
                  <div>
                    <h2 style={{ margin: 0, fontSize: "1.25rem", color: "var(--text-main)" }}>
                      {t.askAiHeaderTitle || "Ask AI"}
                    </h2>
                    <span style={{ fontSize: "0.82rem", color: "var(--text-muted)" }}>
                      {t.askAiHeaderSubtitle || "सरकारी योजनाओं से जुड़े सवाल पूछें और आधिकारिक जानकारी पाएँ।"}
                    </span>
                  </div>
                </div>

                {/* User Message Bubble */}
                {question && (
                  <div className="askai-user-message-bubble">
                    <p className="askai-user-message-text">{question}</p>
                    <span className="askai-message-time">
                      {new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                    </span>
                  </div>
                )}

                {/* Loading Indicator */}
                {loading && (
                  <div className="notice-card" style={{ background: "var(--bg-secondary)" }}>
                    <span className="spinner" />
                    <span style={{ fontWeight: 600 }}>{t.researchingEvidenceBtn || "सरकारी साक्ष्य तलाशे जा रहे हैं..."}</span>
                  </div>
                )}

                {/* Error Notice */}
                {error && (
                  <div className="notice-card error">
                    <div className="notice-icon">⚠️</div>
                    <div className="notice-body">
                      <strong>{t.researchErrorTitle || "अनुसंधान त्रुटि"}</strong>
                      <p>{error}</p>
                    </div>
                  </div>
                )}

                {/* Insufficient Evidence Notice */}
                {result?.status === "insufficient_evidence" && (
                  <div className="notice-card warn">
                    <div className="notice-icon">📋</div>
                    <div className="notice-body">
                      <strong>{t.insufficientEvidenceTitle}</strong>
                      <p>{t.insufficientEvidenceDesc}</p>
                    </div>
                  </div>
                )}

                {/* Structured Scheme Breakdown Card (if matched from DB) */}
                {result?.matched_scheme && (
                  <div
                    style={{
                      background: "var(--bg-card)",
                      border: "1.5px solid var(--accent)",
                      borderRadius: "var(--radius-lg)",
                      padding: "20px",
                      boxShadow: "var(--shadow-md)",
                    }}
                  >
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: "10px" }}>
                      <div>
                        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                          <span style={{ fontSize: "1.3rem" }}>🏛️</span>
                          <h3 style={{ margin: 0, fontSize: "1.2rem", color: "var(--text-main)", fontWeight: 700 }}>
                            {result.matched_scheme.hindi_name}
                          </h3>
                        </div>
                        <div style={{ fontSize: "0.86rem", color: "var(--text-muted)", marginTop: "3px" }}>
                          {result.matched_scheme.scheme_name}
                        </div>
                      </div>
                      <span style={{ background: "var(--emerald-bg)", color: "var(--emerald-text)", padding: "4px 10px", borderRadius: "12px", fontSize: "0.76rem", fontWeight: 700 }}>
                        ● {result.matched_scheme.status || "Active"}
                      </span>
                    </div>

                    <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))", gap: "12px", marginTop: "16px" }}>
                      <div style={{ background: "var(--bg-secondary)", padding: "12px", borderRadius: "var(--radius-md)" }}>
                        <span style={{ fontSize: "0.74rem", fontWeight: 700, color: "var(--text-dim)", textTransform: "uppercase" }}>🎯 {t.eligibilityLabel}</span>
                        <p style={{ margin: "4px 0 0", fontSize: "0.86rem", color: "var(--text-main)" }}>{result.matched_scheme.eligibility}</p>
                      </div>
                      <div style={{ background: "var(--bg-secondary)", padding: "12px", borderRadius: "var(--radius-md)" }}>
                        <span style={{ fontSize: "0.74rem", fontWeight: 700, color: "var(--text-dim)", textTransform: "uppercase" }}>💰 {t.benefitsLabel}</span>
                        <p style={{ margin: "4px 0 0", fontSize: "0.86rem", color: "var(--text-main)" }}>{result.matched_scheme.benefits}</p>
                      </div>
                    </div>
                  </div>
                )}

                {/* AI Research Answer Card */}
                {result?.answer && (
                  <section className="answer-card" style={{ margin: 0 }}>
                    <div className="answer-header">
                      <div className="answer-title">
                        <span className="answer-badge">{t.verifiedSynthesisBadge}</span>
                        <h2>{t.officialFindingsTitle}</h2>
                      </div>

                      {/* TTS Audio Player Toolbar */}
                      <div className="audio-player-toolbar">
                        {ttsPlaying && ttsSource === "findings" ? (
                          <>
                            {ttsPaused ? (
                              <button type="button" className="audio-btn active" onClick={resumeTts}>
                                {t.resumeVoiceBtn}
                              </button>
                            ) : (
                              <button type="button" className="audio-btn active" onClick={pauseTts}>
                                {t.pauseVoiceBtn}
                              </button>
                            )}
                            <button type="button" className="audio-btn danger" onClick={stopTts}>
                              {t.stopVoiceBtn}
                            </button>
                            <div className="audio-waveform-bars">
                              <span className="audio-wave-bar" />
                              <span className="audio-wave-bar" />
                              <span className="audio-wave-bar" />
                              <span className="audio-wave-bar" />
                              <span className="audio-wave-bar" />
                            </div>
                          </>
                        ) : (
                          <button
                            type="button"
                            className="audio-btn"
                            onClick={() => playTts(result.answer, "findings", result.language || selectedLang)}
                          >
                            {t.readFindingsAloudBtn}
                          </button>
                        )}
                        <div className="speed-selector-group">
                          {[0.8, 1.0, 1.25].map((rate) => (
                            <button
                              key={rate}
                              type="button"
                              className={`speed-chip ${ttsRate === rate ? "active" : ""}`}
                              onClick={() => changeTtsRate(rate)}
                            >
                              {rate}x
                            </button>
                          ))}
                        </div>
                      </div>
                    </div>

                    <div className="markdown-body">
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>{result.answer}</ReactMarkdown>
                    </div>

                    {/* Quick Follow-up Action Chips */}
                    <div className="askai-quick-actions-bar">
                      <span style={{ fontSize: "0.8rem", fontWeight: 700, color: "var(--text-dim)", alignSelf: "center", marginRight: "4px" }}>
                        {t.quickActionsTitle || "त्वरित सवाल:"}
                      </span>
                      {[
                        { label: t.quickActionApply || "आवेदन प्रक्रिया क्या है?", q: `${result?.question || question} के लिए आवेदन प्रक्रिया क्या है?` },
                        { label: t.quickActionEligibility || "पात्रता क्या है?", q: `${result?.question || question} के लिए पात्रता और दस्तावेज क्या हैं?` },
                        { label: t.quickActionStatus || "किस्त का स्टेटस कैसे देखें?", q: `${result?.question || question} का स्टेटस और लाभार्थी सूची कैसे देखें?` },
                      ].map((action, idx) => (
                        <button
                          key={idx}
                          type="button"
                          className="askai-quick-action-chip"
                          onClick={() => {
                            setQuestion(action.q);
                            ask(null, action.q);
                          }}
                        >
                          {action.label}
                        </button>
                      ))}
                    </div>
                  </section>
                )}

                {/* Referenced Sources Section */}
                {showSourcesInAnswer && result?.sources?.length > 0 && (
                  <section className="sources-card">
                    <div className="sources-header">
                      <h3>{t.officialSourcesTitle}</h3>
                      <span className="badge-count">{result.sources.length} {t.verifiedBadgeSuffix}</span>
                    </div>
                    <div className="sources-grid">
                      {result.sources.map((src, idx) => (
                        <div key={idx} className="source-item">
                          <span className="source-num">[{src.citation_index || idx + 1}]</span>
                          <div className="source-details">
                            <span className="source-name">
                              {src.source_url ? (
                                <a href={src.source_url} target="_blank" rel="noreferrer" className="source-link">
                                  {src.source || "Official Portal"} ↗
                                </a>
                              ) : (
                                <span className="source-title-plain">{src.source || "Official Source"}</span>
                              )}
                            </span>
                            <div className="source-meta">
                              <span className="meta-badge">{src.authority || "Ministry of Agriculture"}</span>
                              {src.document_type && <span className="meta-badge">{src.document_type}</span>}
                              {src.official_date && <span className="meta-badge">📅 {src.official_date}</span>}
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </section>
                )}

                {/* Bottom Chat Input Bar */}
                <form className="askai-chat-input-card" onSubmit={ask}>
                  <div className="askai-input-row">
                    <button
                      type="button"
                      className="askai-icon-btn"
                      onClick={() => setActiveTab("documents")}
                      title="Attach or inspect official documents"
                    >
                      📎
                    </button>
                    <input
                      type="text"
                      className="askai-input-field"
                      placeholder={t.chatPlaceholder || "अपना सवाल लिखें..."}
                      value={question}
                      onChange={(e) => setQuestion(e.target.value)}
                    />
                    <button
                      type="button"
                      className={`askai-icon-btn ${isListening && listeningTarget === "search" ? "listening" : ""}`}
                      onClick={() => (isListening && listeningTarget === "search" ? stopVoiceInput() : startVoiceInput("search"))}
                      title="Voice Input (बोलकर पूछें)"
                    >
                      🎙️
                    </button>
                    <button type="submit" className="askai-send-btn" disabled={loading || question.trim().length < 3}>
                      ➔
                    </button>
                  </div>
                </form>
              </div>

              {/* Right Column: Language Radio, Suggested Questions, Tips */}
              <div className="askai-sidebar-col">
                {/* 1. Language Selector Radio */}
                <div className="askai-panel-box">
                  <h4 className="askai-panel-title">
                    <span>🌐</span>
                    <span>{t.selectLanguageLabel || "भाषा चुनें"}</span>
                  </h4>
                  <div className="askai-lang-radio-list">
                    <label className="askai-lang-radio-option">
                      <input
                        type="radio"
                        name="askai-lang"
                        value="hi"
                        checked={selectedLang === "hi"}
                        onChange={() => handleLanguageChange("hi")}
                      />
                      <span>हिंदी (Hindi)</span>
                    </label>
                    <label className="askai-lang-radio-option">
                      <input
                        type="radio"
                        name="askai-lang"
                        value="en"
                        checked={selectedLang === "en"}
                        onChange={() => handleLanguageChange("en")}
                      />
                      <span>English</span>
                    </label>
                    <label className="askai-lang-radio-option">
                      <input
                        type="radio"
                        name="askai-lang"
                        value="mr"
                        checked={selectedLang === "mr"}
                        onChange={() => handleLanguageChange("mr")}
                      />
                      <span>मराठी (Marathi)</span>
                    </label>
                  </div>
                </div>

                {/* 2. Suggested Questions */}
                <div className="askai-panel-box">
                  <h4 className="askai-panel-title">
                    <span>💡</span>
                    <span>{t.suggestedQuestionsTitle || "सुझाए गए सवाल"}</span>
                  </h4>
                  <div className="askai-suggested-q-list">
                    {(domainCategories[0]?.questions?.slice(0, 4) || [
                      "PM-KISAN के लिए पात्रता क्या है?",
                      "KCC के लिए आवेदन कैसे करें?",
                      "मुद्रा लोन के लिए कौन-कौन से दस्तावेज चाहिए?",
                      "छात्रवृत्ति के लिए आवेदन कैसे करें?",
                    ]).map((qText, idx) => (
                      <button
                        key={idx}
                        type="button"
                        className="askai-suggested-q-btn"
                        onClick={() => {
                          setQuestion(qText);
                          ask(null, qText);
                        }}
                      >
                        <span>{qText}</span>
                        <span className="askai-chevron-arrow">›</span>
                      </button>
                    ))}
                  </div>
                </div>

                {/* 3. Did You Know? Advice Card */}
                <div className="did-you-know-card">
                  <div className="did-you-know-header">
                    <span>⚠️</span>
                    <span>{t.didYouKnowTitle || "क्या आप जानते हैं?"}</span>
                  </div>
                  <p className="did-you-know-body">
                    {t.didYouKnowText || "आप अपनी भाषा में भी सवाल पूछ सकते हैं। हम हिंदी, अंग्रेजी और मराठी में जवाब देते हैं।"}
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* =========================================================================
              SCREEN 3: GOVERNMENT SCHEMES DIRECTORY (LIST)
              ========================================================================= */}
          {activeTab === "schemes" && (
            <div className="schemes-view-container">
              <div className="schemes-header-row">
                <div>
                  <h2 style={{ margin: 0, fontSize: "1.45rem", color: "var(--text-main)" }}>
                    {t.schemesTitle || "Government Schemes"}
                  </h2>
                  <span style={{ fontSize: "0.88rem", color: "var(--text-muted)" }}>
                    {t.schemesSubtitle || "सरकारी योजनाओं की खोज करें और विस्तृत जानकारी प्राप्त करें"}
                  </span>
                </div>

                <div style={{ display: "flex", gap: "10px", alignItems: "center" }}>
                  <button
                    type="button"
                    className="btn-primary"
                    style={{ fontSize: "0.84rem", padding: "8px 16px" }}
                    onClick={() => setShowExtractModal(true)}
                  >
                    ➕ Extract New Scheme
                  </button>
                </div>
              </div>

              {/* Search Bar & Filter Buttons */}
              <div style={{ display: "flex", gap: "12px", flexWrap: "wrap", alignItems: "center" }}>
                <input
                  type="text"
                  placeholder={t.searchSchemePlaceholder || "🔍 योजना का नाम खोजें..."}
                  value={schemeSearch}
                  onChange={(e) => setSchemeSearch(e.target.value)}
                  style={{
                    flex: "1 1 300px",
                    padding: "10px 16px",
                    borderRadius: "9999px",
                    border: "1.5px solid var(--panel-border)",
                    background: "var(--bg-card)",
                    color: "var(--text-main)",
                    fontSize: "0.9rem",
                  }}
                />

                <div className="schemes-filter-row">
                  {[
                    { id: "all", label: t.filterAll || "सभी" },
                    { id: "Agriculture", label: t.filterFarmer || "किसान" },
                    { id: "Education", label: t.filterScholarship || "छात्रवृत्ति" },
                    { id: "Credit", label: t.filterEntrepreneurship || "उद्यमिता" },
                    { id: "Women", label: t.filterWomen || "महिला" },
                    { id: "Other", label: t.filterOther || "अन्य" },
                  ].map((filter) => (
                    <button
                      key={filter.id}
                      type="button"
                      className={`schemes-pill-filter-btn ${schemeCategoryFilter === filter.id ? "active" : ""}`}
                      onClick={() => setSchemeCategoryFilter(filter.id)}
                    >
                      {filter.label}
                    </button>
                  ))}
                </div>
              </div>

              {/* Schemes Cards Grid */}
              <div className="schemes-card-directory-grid">
                {structuredSchemes
                  .filter((s) => {
                    const matchesSearch =
                      !schemeSearch ||
                      s.scheme_name.toLowerCase().includes(schemeSearch.toLowerCase()) ||
                      s.hindi_name.toLowerCase().includes(schemeSearch.toLowerCase()) ||
                      s.eligibility.toLowerCase().includes(schemeSearch.toLowerCase()) ||
                      s.benefits.toLowerCase().includes(schemeSearch.toLowerCase());

                    const matchesCat =
                      schemeCategoryFilter === "all" ||
                      (schemeCategoryFilter === "Women"
                        ? s.category.toLowerCase().includes("women") ||
                          s.category.toLowerCase().includes("child") ||
                          s.category.toLowerCase().includes("girl")
                        : s.category.toLowerCase().includes(schemeCategoryFilter.toLowerCase()));

                    return matchesSearch && matchesCat;
                  })
                  .map((s) => {
                    const catInfo = getSchemeCategoryPhoto(s.category);
                    return (
                      <div key={s.id || s.scheme_id} className="scheme-card-item">
                        <div>
                          <div className="scheme-card-thumbnail-wrap">
                            <img
                              src={catInfo.photo}
                              alt={s.hindi_name}
                              className="scheme-card-thumbnail-img"
                              onError={(e) => {
                                e.target.src = catInfo.fallback;
                              }}
                            />
                          </div>

                          <div className="scheme-card-top-icon-bar">
                            <div className="scheme-card-badge-icon">
                              {catInfo.icon}
                            </div>
                            <span
                              style={{
                                background: "var(--emerald-bg)",
                                color: "var(--emerald-text)",
                                padding: "2px 8px",
                                borderRadius: "10px",
                                fontSize: "0.72rem",
                                fontWeight: 700,
                              }}
                            >
                              ● {s.status || "Active"}
                            </span>
                          </div>

                          <h3 className="scheme-card-title-hi">{s.hindi_name}</h3>
                          <p className="scheme-card-title-en">{s.scheme_name}</p>
                          <p className="scheme-card-benefits-snippet">
                            <strong>💰 लाभ:</strong> {s.benefits ? s.benefits.slice(0, 110) + "..." : "सरकारी सहायता उपलब्ध"}
                          </p>
                        </div>

                      <div className="scheme-card-footer-action">
                        <span style={{ fontSize: "0.75rem", color: "var(--text-dim)", fontWeight: 600 }}>
                          📍 {s.state_district}
                        </span>
                        <button
                          type="button"
                          className="scheme-card-details-link"
                          onClick={() => {
                            setSelectedScheme(s);
                            setActiveTab("scheme-details");
                          }}
                        >
                          <span>{t.viewDetailsLink || "विवरण देखें →"}</span>
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* =========================================================================
              SCREEN 4: SCHEME DETAILS VIEW
              ========================================================================= */}
          {activeTab === "scheme-details" && selectedScheme && (
            <div className="scheme-detail-screen">
              <div className="scheme-detail-header-nav">
                <button type="button" className="askai-back-btn" onClick={() => setActiveTab("schemes")}>
                  {t.backToSchemes || "← सभी योजनाएं"}
                </button>
                <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
                  <span style={{ background: "var(--bg-secondary)", padding: "4px 12px", borderRadius: "12px", fontSize: "0.8rem", fontWeight: 700, color: "var(--accent)" }}>
                    🏷️ {selectedScheme.category}
                  </span>
                  <span style={{ background: "var(--emerald-bg)", color: "var(--emerald-text)", padding: "4px 10px", borderRadius: "12px", fontSize: "0.8rem", fontWeight: 700 }}>
                    ● {selectedScheme.status || "Active"}
                  </span>
                </div>
              </div>

              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: "12px", marginBottom: "16px" }}>
                <div>
                  <div style={{ display: "flex", alignItems: "center", gap: "10px", flexWrap: "wrap" }}>
                    <h1 style={{ fontFamily: "var(--font-heading)", fontSize: "1.85rem", margin: 0, color: "var(--text-main)", fontWeight: 800 }}>
                      {selectedScheme.hindi_name}
                    </h1>
                    <span className="scheme-badge-farmer">
                      🌾 {selectedScheme.category?.includes("Agriculture") || selectedScheme.category?.includes("Farmer") ? "किसान" : selectedScheme.category}
                    </span>
                  </div>
                  <p style={{ margin: "4px 0 0 0", fontSize: "0.94rem", color: "var(--text-muted)" }}>
                    {selectedScheme.scheme_name} • 🏛️ {selectedScheme.authority}
                  </p>
                </div>

                <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
                  <span style={{ background: "var(--bg-secondary)", padding: "4px 12px", borderRadius: "12px", fontSize: "0.8rem", fontWeight: 700, color: "var(--accent)" }}>
                    📍 {selectedScheme.state_district}
                  </span>
                  <span style={{ background: "var(--emerald-bg)", color: "var(--emerald-text)", padding: "4px 10px", borderRadius: "12px", fontSize: "0.8rem", fontWeight: 700 }}>
                    ● {selectedScheme.status || "Active"}
                  </span>
                </div>
              </div>

              {/* Dynamic Scheme Category Banner with Photos */}
              {(() => {
                const catInfo = getSchemeCategoryPhoto(selectedScheme.category);
                return (
                  <div className="scheme-banner-container">
                    <img
                      src={catInfo.photo}
                      alt={selectedScheme.scheme_name}
                      className="scheme-detail-hero-banner"
                      onError={(e) => {
                        e.target.src = catInfo.fallback || "/assets/scheme_farmer_banner.jpg";
                      }}
                    />
                    <div className="scheme-banner-badge-overlay">
                      <span>{catInfo.icon}</span>
                      <span>{selectedScheme.hindi_name} • {catInfo.label}</span>
                    </div>
                  </div>
                );
              })()}

              {/* Sub-tabs Navigation Bar */}
              <div className="scheme-tabs-nav-bar">
                {[
                  { id: "overview", label: t.tabOverview || "परिचय" },
                  { id: "eligibility", label: t.tabEligibility || "पात्रता" },
                  { id: "benefits", label: t.tabBenefits || "लाभ" },
                  { id: "documents", label: t.tabDocuments || "आवश्यक दस्तावेज़" },
                  { id: "process", label: t.tabProcess || "आवेदन प्रक्रिया" },
                ].map((tab) => (
                  <button
                    key={tab.id}
                    type="button"
                    className={`scheme-tab-header-btn ${schemeSubTab === tab.id ? "active" : ""}`}
                    onClick={() => setSchemeSubTab(tab.id)}
                  >
                    {tab.label}
                  </button>
                ))}
              </div>

              {/* Tab Content Display - Clean 2-Column Mockup Layout */}
              <div className="scheme-details-content-grid">
                {schemeSubTab === "overview" && (
                  <>
                    <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
                      <div className="scheme-detail-info-card">
                        <span className="scheme-detail-card-title">📖 {t.schemeDescTitle || "योजना का विवरण"}</span>
                        <p className="scheme-detail-card-text">
                          {selectedScheme.guidelines_summary || selectedScheme.scheme_name}
                        </p>
                      </div>

                      <div className="scheme-detail-info-card">
                        <span className="scheme-detail-card-title">💰 {t.keyBenefitsTitle || "मुख्य लाभ"}</span>
                        <div className="scheme-detail-card-text">
                          <ul style={{ margin: "4px 0 0 16px", padding: 0 }}>
                            {selectedScheme.benefits
                              ? selectedScheme.benefits.split("\n").filter(Boolean).map((b, i) => (
                                  <li key={i} style={{ marginBottom: "6px" }}>{b.replace(/^[-\d.]+\s*/, "")}</li>
                                ))
                              : <li>सरकारी वित्तीय सहायता एवं आर्थिक अनुदान डीबीटी (DBT) के माध्यम से।</li>}
                          </ul>
                        </div>
                      </div>
                    </div>

                    <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
                      <div className="scheme-detail-info-card">
                        <span className="scheme-detail-card-title">📄 {t.reqDocsTitle || "आवश्यक दस्तावेज"}</span>
                        <div className="scheme-detail-card-text">
                          <ul style={{ listStyle: "none", margin: "4px 0 0 0", padding: 0 }}>
                            {(selectedScheme.documents
                              ? selectedScheme.documents.split("\n").filter(Boolean)
                              : ["आधार कार्ड", "बैंक खाता विवरण", "भूमि रिकॉर्ड (7/12 व खसरा)", "मोबाइल नंबर"]
                            ).map((doc, i) => (
                              <li key={i} style={{ display: "flex", alignItems: "flex-start", gap: "8px", marginBottom: "8px" }}>
                                <span style={{ color: "#10b981", fontWeight: 800 }}>✓</span>
                                <span>{doc.replace(/^[-\d.]+\s*/, "")}</span>
                              </li>
                            ))}
                          </ul>
                        </div>
                      </div>

                      <div className="scheme-detail-info-card">
                        <span className="scheme-detail-card-title">👥 {t.beneficiaryLabel || "पात्र लाभार्थी"}</span>
                        <p className="scheme-detail-card-text">{selectedScheme.beneficiary}</p>
                      </div>
                    </div>
                  </>
                )}

                {schemeSubTab === "eligibility" && (
                  <div className="scheme-detail-info-card" style={{ gridColumn: "1 / -1" }}>
                    <span className="scheme-detail-card-title">🎯 {t.eligibilityLabel || "पात्रता (Eligibility Criteria)"}</span>
                    <p className="scheme-detail-card-text">{selectedScheme.eligibility}</p>
                  </div>
                )}

                {schemeSubTab === "benefits" && (
                  <div className="scheme-detail-info-card" style={{ gridColumn: "1 / -1" }}>
                    <span className="scheme-detail-card-title">💰 {t.keyBenefitsTitle || "मुख्य लाभ (Benefits & Assistance)"}</span>
                    <p className="scheme-detail-card-text">{selectedScheme.benefits}</p>
                  </div>
                )}

                {schemeSubTab === "documents" && (
                  <div className="scheme-detail-info-card" style={{ gridColumn: "1 / -1" }}>
                    <span className="scheme-detail-card-title">📄 {t.reqDocsTitle || "आवश्यक दस्तावेज (Required Documents)"}</span>
                    <p className="scheme-detail-card-text">{selectedScheme.documents || "Aadhaar Card, Bank Passbook, Land Records"}</p>
                  </div>
                )}

                {schemeSubTab === "process" && (
                  <div className="scheme-detail-info-card" style={{ gridColumn: "1 / -1" }}>
                    <span className="scheme-detail-card-title">📝 {t.tabProcess || "आवेदन प्रक्रिया (Application Process)"}</span>
                    <p className="scheme-detail-card-text">
                      1. आधिकारिक पोर्टल या नजदीकी सीएससी (CSC) केंद्र पर जाएं।{"\n"}
                      2. आवश्यक दस्तावेज (आधार कार्ड, बैंक खाता, 7/12 खतौनी) संलग्न करें।{"\n"}
                      3. बायोमेट्रिक या ओटीपी ई-केवाईसी (e-KYC) पूर्ण करें।{"\n"}
                      4. पावती रसीद प्राप्त करें और स्थिति ट्रैक करें।
                    </p>
                  </div>
                )}
              </div>

              {/* Bottom CTA Row */}
              <div className="scheme-detail-bottom-cta-row">
                <button
                  type="button"
                  className="btn-secondary"
                  onClick={() => {
                    const q = `${selectedScheme.hindi_name} (${selectedScheme.scheme_name}) की पात्रता और आवेदन प्रक्रिया क्या है?`;
                    setQuestion(q);
                    ask(null, q);
                  }}
                >
                  {t.askAiAboutThisSchemeBtn || "💬 इस योजना के बारे में AI से पूछें"}
                </button>

                {selectedScheme.official_source_url && (
                  <a
                    href={selectedScheme.official_source_url}
                    target="_blank"
                    rel="noreferrer"
                    className="scheme-official-portal-btn"
                  >
                    <span>{t.visitOfficialPortalBtn || "आधिकारिक वेबसाइट पर जाएँ ↗"}</span>
                  </a>
                )}
              </div>
            </div>
          )}

          {/* =========================================================================
              SCREEN 5: DOCUMENTS MANAGEMENT HUB
              ========================================================================= */}
          {activeTab === "documents" && (
            <div className="docs-hub-container">
              <div className="schemes-header-row">
                <div>
                  <h2 style={{ margin: 0, fontSize: "1.45rem", color: "var(--text-main)" }}>
                    {t.docsMainTitle || "Documents"}
                  </h2>
                  <span style={{ fontSize: "0.88rem", color: "var(--text-muted)" }}>
                    {t.docsMainSubtitle || "अपलोड, प्रबंध और खोजें"}
                  </span>
                </div>

                {/* Sub-tabs */}
                <div style={{ display: "flex", gap: "8px" }}>
                  {[
                    { id: "my-docs", label: t.tabMyDocs || "मेरे दस्तावेज़" },
                    { id: "status", label: t.tabIndexingStatus || "इंडेक्सिंग स्टेटस" },
                    { id: "sources", label: t.tabSourcesRegistry || "स्रोत" },
                  ].map((tab) => (
                    <button
                      key={tab.id}
                      type="button"
                      className={`schemes-pill-filter-btn ${docSubTab === tab.id ? "active" : ""}`}
                      onClick={() => setDocSubTab(tab.id)}
                    >
                      {tab.label}
                    </button>
                  ))}
                </div>
              </div>

              {docSubTab === "my-docs" && (
                <>
                  {/* Scheme Categories Visual Guidance Hub on Upload Data Page */}
                  <div className="upload-schemes-hub">
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "12px", flexWrap: "wrap", gap: "8px" }}>
                      <div>
                        <h3 className="upload-schemes-hub-title">
                          🏛️ {t.uploadSchemeCategoryFilter || "योजना श्रेणी अनुसार दस्तावेज़ देखें व अपलोड करें"}
                        </h3>
                        <p className="upload-schemes-hub-sub">
                          {t.uploadSchemeCategorySub || "श्रेणी अनुसार आधिकारिक दिशानिर्देश और योजना फोटो देखें"}
                        </p>
                      </div>
                      {docCategoryFilter !== "all" && (
                        <button
                          type="button"
                          className="btn-secondary"
                          style={{ fontSize: "0.78rem", padding: "4px 10px" }}
                          onClick={() => setDocCategoryFilter("all")}
                        >
                          Clear Filter ✕
                        </button>
                      )}
                    </div>

                    <div className="upload-schemes-grid">
                      {[
                        {
                          id: "Agriculture",
                          title: t.categoryFarmer || "किसान योजनाएँ",
                          tag: "PM-KISAN, KCC, PMFBY",
                          img: "/assets/scheme_cat_farmer.jpg",
                          fallback: "/assets/card_farmer.jpg",
                          color: "#166534",
                          border: "#bbf7d0",
                        },
                        {
                          id: "Education",
                          title: t.categoryScholarship || "छात्रवृत्ति",
                          tag: "NSP, Scholarships, Higher Ed",
                          img: "/assets/scheme_cat_scholarship.jpg",
                          fallback: "/assets/card_scholarship.jpg",
                          color: "#1d4ed8",
                          border: "#bfdbfe",
                        },
                        {
                          id: "Credit",
                          title: t.categoryEntrepreneurship || "उद्यमिता",
                          tag: "MUDRA, Stand-Up, PMEGP",
                          img: "/assets/scheme_cat_entrepreneur.jpg",
                          fallback: "/assets/card_entrepreneur.jpg",
                          color: "#c2410c",
                          border: "#fed7aa",
                        },
                        {
                          id: "Women",
                          title: t.categoryWomen || "महिला कल्याण",
                          tag: "Ujjwala, PMMVY, Ladki Bahin",
                          img: "/assets/scheme_cat_women.jpg",
                          fallback: "/assets/card_women.jpg",
                          color: "#be185d",
                          border: "#fbcfe8",
                        },
                        {
                          id: "all",
                          title: t.categoryOther || "अन्य योजनाएँ",
                          tag: "Health, Housing, Pensions",
                          img: "/assets/scheme_cat_other.jpg",
                          fallback: "/assets/card_other.jpg",
                          color: "#6d28d9",
                          border: "#ddd6fe",
                        },
                      ].map((item) => (
                        <div
                          key={item.id}
                          className={`upload-scheme-category-card ${docCategoryFilter === item.id ? "selected" : ""}`}
                          onClick={() => setDocCategoryFilter(docCategoryFilter === item.id ? "all" : item.id)}
                          style={{
                            borderColor: docCategoryFilter === item.id ? item.color : undefined,
                            boxShadow: docCategoryFilter === item.id ? `0 0 0 2px ${item.border}` : undefined,
                          }}
                          title={`Filter documents for ${item.title}`}
                        >
                          <div className="upload-scheme-img-wrap">
                            <img
                              src={item.img}
                              alt={item.title}
                              className="upload-scheme-img"
                              onError={(e) => {
                                e.target.src = item.fallback;
                              }}
                            />
                          </div>
                          <div className="upload-scheme-body">
                            <span className="upload-scheme-name" style={{ color: item.color }}>
                              {item.title}
                            </span>
                            <span className="upload-scheme-tag">{item.tag}</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Upload Dropzone Box */}
                  <div
                    className="docs-dropzone-box"
                    onClick={() => fileInputRef.current?.click()}
                  >
                    <input
                      type="file"
                      ref={fileInputRef}
                      style={{ display: "none" }}
                      onChange={handleFileUpload}
                      accept=".pdf,.txt,.html,.doc,.docx,.csv,.json"
                    />
                    <span className="docs-cloud-icon">☁️</span>
                    <strong style={{ fontSize: "1.1rem", color: "var(--text-main)" }}>
                      {t.uploadCardTitle || "दस्तावेज़ या स्क्रैप डेटा अपलोड करें"}
                    </strong>
                    <span style={{ fontSize: "0.84rem", color: "var(--text-muted)" }}>
                      {t.uploadCardSub || "PDF, DOCX, TXT, CSV, JSON (अधिकतम 20MB)"}
                    </span>
                    <button type="button" className="btn-primary" style={{ marginTop: "6px" }}>
                      {uploadingDoc ? "Uploading..." : t.chooseFileBtn || "फ़ाइल चुनें"}
                    </button>
                    {uploadStatus && (
                      <span style={{ fontSize: "0.82rem", fontWeight: 600, color: "var(--accent)" }}>
                        {uploadStatus}
                      </span>
                    )}
                  </div>

                  {/* Documents List */}
                  <div className="docs-recent-list-card">
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "14px", flexWrap: "wrap", gap: "10px" }}>
                      <h3 style={{ margin: 0, fontSize: "1.05rem", color: "var(--text-main)" }}>
                        {t.recentUploadsTitle || "हाल के अपलोड"} ({documentsList.length})
                        {docCategoryFilter !== "all" && (
                          <span style={{ fontSize: "0.8rem", color: "var(--accent)", marginLeft: "8px", fontWeight: 600 }}>
                            • {docCategoryFilter} Filtered
                          </span>
                        )}
                      </h3>
                      <input
                        type="text"
                        placeholder="Filter documents..."
                        value={docSearch}
                        onChange={(e) => setDocSearch(e.target.value)}
                        style={{
                          padding: "6px 12px",
                          borderRadius: "var(--radius-md)",
                          border: "1px solid var(--panel-border)",
                          background: "var(--bg-secondary)",
                          color: "var(--text-main)",
                          fontSize: "0.82rem",
                        }}
                      />
                    </div>

                    <div className="docs-table-list">
                      {documentsList
                        .filter((d) => {
                          const matchesSearch = !docSearch || d.title.toLowerCase().includes(docSearch.toLowerCase()) || (d.authority || "").toLowerCase().includes(docSearch.toLowerCase());
                          if (!matchesSearch) return false;
                          if (docCategoryFilter === "all") return true;
                          const combined = (d.title + " " + (d.authority || "")).toLowerCase();
                          if (docCategoryFilter === "Agriculture") {
                            return combined.includes("kisan") || combined.includes("agri") || combined.includes("crop") || combined.includes("soil") || combined.includes("pest") || combined.includes("fertilizer") || combined.includes("farmer");
                          }
                          if (docCategoryFilter === "Education") {
                            return combined.includes("scholar") || combined.includes("matric") || combined.includes("education") || combined.includes("student");
                          }
                          if (docCategoryFilter === "Women") {
                            return combined.includes("women") || combined.includes("child") || combined.includes("mahila") || combined.includes("wcd");
                          }
                          if (docCategoryFilter === "Credit") {
                            return combined.includes("credit") || combined.includes("mudra") || combined.includes("msme") || combined.includes("loan");
                          }
                          return true;
                        })
                        .map((doc) => {
                          const catInfo = getSchemeCategoryPhoto(doc.title + " " + (doc.authority || ""));
                          return (
                            <div key={doc.id} className="doc-table-row">
                              <div className="doc-file-info">
                                <div style={{ position: "relative", width: "44px", height: "44px", borderRadius: "10px", overflow: "hidden", flexShrink: 0, border: "1px solid var(--panel-border)" }}>
                                  <img
                                    src={catInfo.photo}
                                    alt="category"
                                    style={{ width: "100%", height: "100%", objectFit: "cover" }}
                                    onError={(e) => { e.target.src = catInfo.fallback; }}
                                  />
                                </div>
                                <div>
                                  <h4 className="doc-title-text">{doc.title}</h4>
                                  <span className="doc-sub-text">
                                    🏛️ {doc.authority} • 📅 {doc.publication_date || "2025-26"}
                                  </span>
                                </div>
                              </div>
                              <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                                <span style={{ background: "var(--emerald-bg)", color: "var(--emerald-text)", padding: "3px 8px", borderRadius: "10px", fontSize: "0.74rem", fontWeight: 700 }}>
                                  🟢 {t.statusIndexed || "इंडेक्स्ड"}
                                </span>
                                <button
                                  type="button"
                                  className="btn-secondary"
                                  style={{ fontSize: "0.78rem", padding: "6px 12px" }}
                                  onClick={() => openDocumentReader(doc.id)}
                                >
                                  {t.readDocAction || "दस्तावेज़ पढ़ें"}
                                </button>
                              </div>
                            </div>
                          );
                        })}
                    </div>
                  </div>
                </>
              )}

              {docSubTab === "status" && (
                <div className="dash-popular-container">
                  <h3>Vector Indexing Status</h3>
                  <p style={{ color: "var(--text-muted)", fontSize: "0.9rem" }}>
                    ChromaDB Vector Store contains <strong>197 chunks</strong> from {documentsList.length} indexed documents.
                  </p>
                  <button
                    type="button"
                    className="btn-primary"
                    style={{ marginTop: "12px" }}
                    onClick={async () => {
                      alert("Rebuilding vector store index...");
                      await fetch(`${API}/documents/index`, { method: "POST", headers: { "X-Admin-Token": "admin123" } });
                      fetchHealth();
                    }}
                  >
                    🔄 Rebuild Index
                  </button>
                </div>
              )}

              {docSubTab === "sources" && (
                <div className="dash-popular-container">
                  <h3>Official Sources Registry</h3>
                  <div style={{ display: "flex", flexDirection: "column", gap: "10px", marginTop: "12px" }}>
                    {sourcesRegistry.map((s, idx) => (
                      <div key={idx} style={{ padding: "10px", background: "var(--bg-secondary)", borderRadius: "8px" }}>
                        <strong>{s.name}</strong> • <a href={s.base_url} target="_blank" rel="noreferrer">{s.base_url}</a>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* =========================================================================
              SCREEN 6: SETTINGS
              ========================================================================= */}
          {activeTab === "settings" && (
            <div className="settings-cards-grid">
              {/* Language Preferences */}
              <div className="settings-panel-card">
                <h3 className="settings-panel-title">
                  <span>🌐</span>
                  <span>{t.langPrefTitle || "भाषा सेटिंग"}</span>
                </h3>
                <div className="settings-row-item">
                  <div>
                    <div className="settings-item-label">UI Language</div>
                    <div className="settings-item-desc">Change the display language for all menus and buttons</div>
                  </div>
                  <select
                    value={selectedLang}
                    onChange={(e) => handleLanguageChange(e.target.value)}
                    className="dash-lang-select-btn"
                  >
                    <option value="hi">हिंदी (Hindi)</option>
                    <option value="en">English</option>
                    <option value="mr">मराठी (Marathi)</option>
                  </select>
                </div>
              </div>

              {/* AI Model Preferences */}
              <div className="settings-panel-card">
                <h3 className="settings-panel-title">
                  <span>🧠</span>
                  <span>{t.aiModelPrefTitle || "AI मॉडल"}</span>
                </h3>
                <div className="settings-row-item">
                  <div>
                    <div className="settings-item-label">Active Provider</div>
                    <div className="settings-item-desc">{health?.llm_model || "Local Grounded Synthesis"}</div>
                  </div>
                  <button
                    type="button"
                    className="btn-secondary"
                    style={{ fontSize: "0.82rem", padding: "6px 12px" }}
                    onClick={() => setShowApiKeyModal(true)}
                  >
                    Change Key
                  </button>
                </div>
              </div>

              {/* Theme Preferences */}
              <div className="settings-panel-card">
                <h3 className="settings-panel-title">
                  <span>🎨</span>
                  <span>{t.themePrefTitle || "थीम"}</span>
                </h3>
                <div className="settings-row-item">
                  <div>
                    <div className="settings-item-label">Appearance</div>
                    <div className="settings-item-desc">Toggle between Light and Dark interface modes</div>
                  </div>
                  <button type="button" className="theme-toggle-btn" onClick={toggleTheme}>
                    {theme === "light" ? t.themeLightBtn || "☀️ लाइट" : t.themeDarkBtn || "🌙 डार्क"}
                  </button>
                </div>
              </div>

              {/* Behavioral Preferences */}
              <div className="settings-panel-card">
                <h3 className="settings-panel-title">
                  <span>⚡</span>
                  <span>System Preferences</span>
                </h3>
                <div className="settings-row-item">
                  <div>
                    <div className="settings-item-label">{t.autoSearchPrefTitle || "ऑटो-सर्च (बोलने के बाद)"}</div>
                    <div className="settings-item-desc">Automatically research when you finish speaking</div>
                  </div>
                  <input
                    type="checkbox"
                    checked={autoSearchOnSpeech}
                    onChange={(e) => setAutoSearchOnSpeech(e.target.checked)}
                    style={{ width: "18px", height: "18px", cursor: "pointer" }}
                  />
                </div>
                <div className="settings-row-item">
                  <div>
                    <div className="settings-item-label">{t.showSourcesPrefTitle || "आधिकारिक स्रोत दिखाएं"}</div>
                    <div className="settings-item-desc">Display direct government citations under each answer</div>
                  </div>
                  <input
                    type="checkbox"
                    checked={showSourcesInAnswer}
                    onChange={(e) => setShowSourcesInAnswer(e.target.checked)}
                    style={{ width: "18px", height: "18px", cursor: "pointer" }}
                  />
                </div>
              </div>

              {/* History Management */}
              <div className="settings-panel-card" style={{ gridColumn: "1 / -1" }}>
                <h3 className="settings-panel-title">
                  <span>🗑️</span>
                  <span>Data &amp; History Management</span>
                </h3>
                <div style={{ display: "flex", gap: "12px", alignItems: "center", flexWrap: "wrap" }}>
                  <button
                    type="button"
                    className="btn-secondary"
                    onClick={handleClearAllHistory}
                    disabled={clearingHistory || history.length === 0}
                  >
                    {t.resetHistoryBtn || "खोज इतिहास साफ करें"} ({history.length})
                  </button>
                  <button
                    type="button"
                    className="btn-secondary"
                    onClick={async () => {
                      if (!window.confirm("Seed default 22 official schemes into database?")) return;
                      await fetch(`${API}/schemes/seed`, { method: "POST", headers: { "X-Admin-Token": "admin123" } });
                      fetchStructuredSchemes();
                      fetchHealth();
                    }}
                  >
                    🌱 Seed Default Official Schemes
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* =========================================================================
              SCREEN: HISTORY LOG (Dedicated Tab)
              ========================================================================= */}
          {activeTab === "history" && (
            <div className="dash-popular-container">
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
                <div>
                  <h2 style={{ margin: 0, fontSize: "1.35rem", color: "var(--text-main)" }}>
                    {t.recentQueries || "हाल के प्रश्न"}
                  </h2>
                  <span style={{ fontSize: "0.82rem", color: "var(--text-muted)" }}>
                    {history.length} saved sessions
                  </span>
                </div>
                {history.length > 0 && (
                  <button type="button" className="btn-secondary" onClick={handleClearAllHistory}>
                    {t.clearAllHistory || "🗑️ सभी हटाएं"}
                  </button>
                )}
              </div>

              {history.length === 0 ? (
                <p style={{ color: "var(--text-muted)" }}>{t.noHistoryYet}</p>
              ) : (
                <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
                  {history.map((h) => (
                    <div
                      key={h.id}
                      className="doc-table-row"
                      style={{ cursor: "pointer" }}
                      onClick={() => {
                        setQuestion(h.question);
                        if (h.answer) {
                          setResult({
                            id: h.id,
                            answer: h.answer,
                            sources: h.sources || [],
                            status: h.status,
                            language: h.language || "hi",
                          });
                        } else {
                          ask(null, h.question);
                        }
                        setActiveTab("ask-ai");
                      }}
                    >
                      <div>
                        <strong>{h.question}</strong>
                        <div style={{ fontSize: "0.78rem", color: "var(--text-dim)", marginTop: "2px" }}>
                          📅 {h.created_at ? new Date(h.created_at).toLocaleString() : "Recent"}
                        </div>
                      </div>
                      <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
                        <span style={{ fontSize: "0.82rem", color: "var(--accent)", fontWeight: 600 }}>Load in Ask AI ➔</span>
                        <button
                          type="button"
                          className="history-delete-btn"
                          style={{ opacity: 1 }}
                          onClick={(e) => handleDeleteHistoryItem(e, h.id)}
                        >
                          ✕
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </main>
      </div>

      {/* 3. MODAL: API KEY CONFIGURATION */}
      {showApiKeyModal && (
        <div className="modal-overlay" onClick={() => setShowApiKeyModal(false)}>
          <div className="modal-card" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>{t.apiKeyModalTitle || "AI Provider Configuration"}</h3>
              <button className="close-btn" onClick={() => setShowApiKeyModal(false)}>✕</button>
            </div>
            <div className="api-modal-content">
              <p>{t.apiKeyModalDesc || "The research agent can run on either Groq or Anthropic Claude."}</p>
              <form onSubmit={handleSaveKey} style={{ marginTop: "16px" }}>
                <div style={{ display: "flex", gap: "10px", marginBottom: "12px" }}>
                  <button
                    type="button"
                    className={`btn-secondary ${keyProvider === "groq" ? "active" : ""}`}
                    style={{ flex: 1, borderColor: keyProvider === "groq" ? "var(--accent)" : "var(--panel-border)" }}
                    onClick={() => setKeyProvider("groq")}
                  >
                    ⚡ Groq (Llama-3.3-70B)
                  </button>
                  <button
                    type="button"
                    className={`btn-secondary ${keyProvider === "anthropic" ? "active" : ""}`}
                    style={{ flex: 1, borderColor: keyProvider === "anthropic" ? "var(--accent)" : "var(--panel-border)" }}
                    onClick={() => setKeyProvider("anthropic")}
                  >
                    🧠 Anthropic Claude
                  </button>
                </div>
                <div className="form-group" style={{ marginBottom: "12px" }}>
                  <label>{keyProvider === "groq" ? "Groq API Key (starts with gsk_)" : "Anthropic API Key"}</label>
                  <input
                    type="password"
                    placeholder={keyProvider === "groq" ? "gsk_..." : "sk-ant-..."}
                    value={apiKeyInput}
                    onChange={(e) => setApiKeyInput(e.target.value)}
                    required
                  />
                </div>
                <button type="submit" className="btn-primary" disabled={savingKey || !apiKeyInput.trim()}>
                  {savingKey ? "Activating..." : t.saveApiKeyBtn || "Activate API Key"}
                </button>
                {keySaveStatus && (
                  <p style={{ marginTop: "10px", fontSize: "0.85rem", color: keySaveStatus.startsWith("✅") ? "green" : "red" }}>
                    {keySaveStatus}
                  </p>
                )}
              </form>
            </div>
          </div>
        </div>
      )}

      {/* 4. MODAL: EXTRACT SCHEME FROM TEXT */}
      {showExtractModal && (
        <div className="modal-overlay" onClick={() => setShowExtractModal(false)}>
          <div className="modal-card" style={{ maxWidth: "680px" }} onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>➕ Extract & Ingest Scheme</h3>
              <button className="close-btn" onClick={() => setShowExtractModal(false)}>✕</button>
            </div>
            <form onSubmit={handleExtractScheme} style={{ padding: "20px" }}>
              <p style={{ fontSize: "0.85rem", color: "var(--text-muted)", margin: "0 0 10px 0" }}>
                Paste official government resolution or policy text in Hindi, Marathi, or English to extract structured fields.
              </p>
              <textarea
                rows={7}
                style={{ width: "100%", padding: "10px", borderRadius: "8px", border: "1px solid var(--panel-border)", background: "var(--bg-secondary)", color: "var(--text-main)" }}
                placeholder="Paste scheme description, eligibility, benefits text..."
                value={extractText}
                onChange={(e) => setExtractText(e.target.value)}
                required
              />
              <div style={{ display: "flex", justifyContent: "flex-end", gap: "10px", marginTop: "12px" }}>
                <button type="button" className="btn-secondary" onClick={() => setShowExtractModal(false)}>Cancel</button>
                <button type="submit" className="btn-primary" disabled={extracting || !extractText.trim()}>
                  {extracting ? "Extracting..." : "Extract & Save"}
                </button>
              </div>
              {extractStatus && (
                <p style={{ marginTop: "10px", fontSize: "0.85rem", color: extractStatus.startsWith("✅") ? "green" : "red" }}>
                  {extractStatus}
                </p>
              )}
            </form>
          </div>
        </div>
      )}

      {/* 5. MODAL: DOCUMENT TEXT READER WITH VOICE TTS */}
      {selectedDoc && (
        <div className="modal-overlay" onClick={() => setSelectedDoc(null)}>
          <div className="modal-card" style={{ maxWidth: "800px", maxHeight: "88vh" }} onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <div>
                <h3 style={{ margin: 0 }}>📄 {selectedDoc.title}</h3>
                <span style={{ fontSize: "0.82rem", color: "var(--text-muted)" }}>
                  {selectedDoc.authority} • {selectedDoc.pages_count} Pages
                </span>
              </div>
              <button className="close-btn" onClick={() => setSelectedDoc(null)}>✕</button>
            </div>
            <div style={{ padding: "16px 20px" }}>
              <div className="doc-reader-meta-bar">
                <span>{selectedDoc.source_url ? <a href={selectedDoc.source_url} target="_blank" rel="noreferrer">Official Link ↗</a> : "Verified Local Source"}</span>
                <button
                  type="button"
                  className="btn-primary"
                  style={{ fontSize: "0.82rem", padding: "6px 14px" }}
                  onClick={() => playTts(selectedDoc.text, `doc-${selectedDoc.id}`, selectedLang)}
                >
                  {ttsPlaying && ttsSource === `doc-${selectedDoc.id}` ? "⏹️ Stop Audio" : "🔊 Read Document Aloud"}
                </button>
              </div>
              <div className="doc-content-viewer">
                {selectedDoc.text}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
