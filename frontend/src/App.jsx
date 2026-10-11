import { useState, useEffect, useRef } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

const API = import.meta.env.VITE_API_URL || "";

const DOMAIN_CATEGORIES = [
  {
    id: "farmer",
    label: "🌾 Farmer Questions",
    description: "Kisan Credit Card (KCC), land records (7/12 & RoR), disaster relief (SDRF/NDRF), and tenant farmer credit",
    questions: [
      "What is the procedure for obtaining a Kisan Credit Card (KCC) and what is the concessional interest rate?",
      "What documents and land records (RoR / 7/12 extract) are required to verify farmer eligibility?",
      "What financial assistance is provided under SDRF and NDRF norms for crop loss due to natural calamities?",
      "How can a tenant farmer or sharecropper access agricultural credit without land titles?"
    ]
  },
  {
    id: "crops",
    label: "🌱 Crop Problems",
    description: "Crop yellowing diagnosis, terminal heat stress, lodging management, and seed treatment protocols",
    questions: [
      "How to distinguish between Nitrogen deficiency, waterlogging, and Iron chlorosis when crop leaves turn yellow?",
      "What are the recommended varieties and mitigation sprays to prevent terminal heat stress in wheat?",
      "How can paddy lodging be prevented and managed after unseasonal rains during ripening?",
      "What are the optimum sowing windows and seed treatment protocols for irrigated wheat?"
    ]
  },
  {
    id: "pests",
    label: "🐛 Pest Questions",
    description: "Integrated Pest Management (IPM), Fall Armyworm, Pink Bollworm, Brown Plant Hopper, and bio-pesticides",
    questions: [
      "What is the Integrated Pest Management (IPM) schedule and ETL for Fall Armyworm (FAW) in maize?",
      "How to control Pink Bollworm in Bt Cotton using pheromone traps and approved bio-control agents?",
      "What are the official control measures for Brown Plant Hopper (BPH) in rice, and what chemicals must be avoided?",
      "Which bio-pesticides (like Trichoderma viride) are approved for pulse root rot and wilt management?"
    ]
  },
  {
    id: "fertilizers",
    label: "🧪 Fertilizer Questions",
    description: "Soil Health Card benchmarks, Neem Coated Urea, Nano Urea/DAP, and Zinc deficiency (Khaira)",
    questions: [
      "How to interpret Soil Health Card parameters (pH, EC, Organic Carbon, and NPK benchmarks)?",
      "What is the recommended application schedule and benefits of Neem Coated Urea over normal urea?",
      "How should Nano Urea and Nano DAP liquid be applied as foliar spray and seed treatment?",
      "What are the symptoms and soil correction methods for Zinc deficiency (Khaira disease) in paddy?"
    ]
  },
  {
    id: "schemes",
    label: "🏛️ Central Schemes",
    description: "PM-KISAN (Rs 6,000/yr), PMFBY (Crop Insurance), PM-KUSUM (Solar Pumps), and SMAM (Machinery)",
    questions: [
      "What are the mandatory e-KYC and land-seeding rules to receive Rs 6,000 yearly under PM-KISAN?",
      "Compare farmer premium rates and coverage stages under Pradhan Mantri Fasal Bima Yojana (PMFBY).",
      "What subsidy is provided for standalone solar agriculture pumps under PM-KUSUM Component B?",
      "What financial assistance is available under SMAM for purchasing tractors and farm machinery?"
    ]
  },
  {
    id: "maharashtra_schemes",
    label: "🌾 Maharashtra Schemes (2026–27)",
    description: "Namo Shetakari Mahasanmaan, Krushi Samrudhi, POCRA-II, SMART, Agri AI Policy, & BDS Budget Outlays",
    questions: [
      "What is the 2026-27 proposed budget outlay and allocation for Namo Shetakari Mahasanmaan Nidhi Yojana?",
      "What are the details and fund utilization of the new Krushi Samrudhi Yojana in Maharashtra?",
      "What is the Maharashtra Agriculture Artificial Intelligence Policy 2025-2029 allocation and objectives?",
      "What are the top 5 agricultural schemes by proposed outlay in Maharashtra for 2026-27?"
    ]
  },
  {
    id: "women_child",
    label: "👩 Women & Child Schemes",
    description: "Majhi Ladki Bahin (₹1,500/mo), Lek Ladki (₹1,01,000), PMMVY Maternity, Sakhi One Stop Centre, & Helpline 181",
    questions: [
      "What is the eligibility criteria and ₹1,500 monthly benefit under Mukhyamantri Majhi Ladki Bahin Yojana?",
      "What are the stage-wise milestone grants totaling ₹1,01,000 under Lek Ladki Yojana?",
      "What maternity benefits and DBT installments are provided under Pradhan Mantri Matru Vandana Yojana (PMMVY)?",
      "What emergency rescue, counseling, and shelter services are provided under One Stop Centre (Sakhi) and Helpline 181?"
    ]
  }
];

// Helper to strip markdown and metadata tags for natural speech synthesis
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

// Split text into natural sentence-sized chunks to prevent browser speech timeout bugs
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

export default function App() {
  const [question, setQuestion] = useState("");
  const [selectedLang, setSelectedLang] = useState("auto");
  const [activeCategory, setActiveCategory] = useState("maharashtra_schemes");
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [history, setHistory] = useState([]);
  const [clearingHistory, setClearingHistory] = useState(false);
  const [health, setHealth] = useState(null);
  const [showApiKeyModal, setShowApiKeyModal] = useState(false);
  const [showSchemesModal, setShowSchemesModal] = useState(false);
  const [schemesList, setSchemesList] = useState([]);
  const [schemeSearch, setSchemeSearch] = useState("");
  const [schemePlanFilter, setSchemePlanFilter] = useState("all");

  // Relational Structured Schemes State (PostgreSQL / Relational DB 9-field schema)
  const [showStructuredModal, setShowStructuredModal] = useState(false);
  const [structuredSchemes, setStructuredSchemes] = useState([]);
  const [structuredSearch, setStructuredSearch] = useState("");
  const [structuredCatFilter, setStructuredCatFilter] = useState("all");
  const [showExtractModal, setShowExtractModal] = useState(false);
  const [extractText, setExtractText] = useState("");
  const [extractStatus, setExtractStatus] = useState("");
  const [extracting, setExtracting] = useState(false);

  // Voice Speech-to-Text (STT) State
  const [isListening, setIsListening] = useState(false);
  const [listeningTarget, setListeningTarget] = useState(null); // "search" | "docSearch" | "extract"
  const [speechError, setSpeechError] = useState("");
  const [liveTranscript, setLiveTranscript] = useState("");
  const [autoSearchOnSpeech, setAutoSearchOnSpeech] = useState(false);
  const recognitionRef = useRef(null);

  // Voice Text-to-Speech (TTS) State
  const [ttsPlaying, setTtsPlaying] = useState(false);
  const [ttsPaused, setTtsPaused] = useState(false);
  const [ttsSource, setTtsSource] = useState(""); // "findings", "doc-X", "chunk-X", "source-X"
  const [ttsCurrentChunk, setTtsCurrentChunk] = useState(0);
  const [ttsTotalChunks, setTtsTotalChunks] = useState(0);
  const [ttsRate, setTtsRate] = useState(1.0);
  const ttsQueueRef = useRef([]);
  const ttsIndexRef = useRef(0);
  const ttsActiveRef = useRef(false);
  const ttsLangRef = useRef("en");
  const ttsRateRef = useRef(1.0);

  // Official Documents Hub & Document Voice Reader State
  const [showDocsModal, setShowDocsModal] = useState(false);
  const [docsList, setDocsList] = useState([]);
  const [docsLoading, setDocsLoading] = useState(false);
  const [docSearch, setDocSearch] = useState("");
  const [docCatFilter, setDocCatFilter] = useState("all");
  const [selectedDoc, setSelectedDoc] = useState(null);
  const [selectedDocText, setSelectedDocText] = useState("");
  const [docTextLoading, setDocTextLoading] = useState(false);

  const [theme, setTheme] = useState(() => {
    return localStorage.getItem("gov_theme") || "light";
  });

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem("gov_theme", theme);
  }, [theme]);

  const [keyProvider, setKeyProvider] = useState("groq");
  const [apiKeyInput, setApiKeyInput] = useState("");
  const [keySaveStatus, setKeySaveStatus] = useState("");
  const [savingKey, setSavingKey] = useState(false);

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
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Failed to update key");
      setKeySaveStatus(`✅ Successfully activated ${data.llm_model}!`);
      setApiKeyInput("");
      fetchHealth();
    } catch (err) {
      setKeySaveStatus(`❌ Error: ${err.message}`);
    } finally {
      setSavingKey(false);
    }
  }

  const toggleTheme = () => {
    setTheme((prev) => (prev === "light" ? "dark" : "light"));
  };

  useEffect(() => {
    fetchHealth();
    fetchHistory();
    fetchSchemes();
    fetchStructuredSchemes();
    fetchDocuments();
    return () => {
      stopTts();
      stopVoiceInput();
    };
  }, []);

  async function fetchStructuredSchemes() {
    try {
      const res = await fetch(`${API}/schemes`);
      if (res.ok) {
        const data = await res.json();
        const list = Array.isArray(data) ? data : (data.items || []);
        // Client-side unique key safeguard
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
    } catch (err) {
      console.error("Failed to fetch structured schemes:", err);
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
          "X-Admin-Token": "admin123"
        },
        body: JSON.stringify({ text: extractText.trim() }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Extraction failed");
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

  async function fetchHealth() {
    try {
      const res = await fetch(`${API}/health`);
      if (res.ok) {
        const data = await res.json();
        setHealth(data);
      }
    } catch {
      // Backend not yet reachable
    }
  }

  async function fetchHistory() {
    try {
      const res = await fetch(`${API}/history`);
      if (res.ok) {
        const data = await res.json();
        setHistory(data);
      }
    } catch {
      // ignore
    }
  }

  async function handleClearAllHistory() {
    if (!window.confirm("Are you sure you want to clear all research search history?")) {
      return;
    }
    setClearingHistory(true);
    try {
      const res = await fetch(`${API}/history`, { method: "DELETE" });
      if (res.ok) {
        setHistory([]);
      }
    } catch (err) {
      console.error("Failed to clear search history:", err);
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



  // Voice Text-to-Speech (TTS) Controller
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
        matchedVoice = voices.find((v) => v.lang.toLowerCase().startsWith("mr") || v.name.toLowerCase().includes("marathi"))
          || voices.find((v) => v.lang.toLowerCase().startsWith("hi"));
      } else if (targetLang === "en") {
        matchedVoice = voices.find((v) => v.lang.toLowerCase().startsWith("en-in") || v.name.toLowerCase().includes("india"))
          || voices.find((v) => v.lang.toLowerCase().startsWith("en"));
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
          console.warn("Speech synthesis error:", e);
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

  function playTts(text, sourceId, language = "en") {
    if (!window.speechSynthesis) {
      alert("Text-to-speech is not supported in this browser.");
      return;
    }
    if (ttsPlaying && ttsSource === sourceId) {
      if (ttsPaused) {
        resumeTts();
      } else {
        pauseTts();
      }
      return;
    }

    stopTts();

    const chunks = splitTextIntoSentences(text);
    if (!chunks.length) return;

    ttsQueueRef.current = chunks;
    ttsIndexRef.current = 0;
    ttsActiveRef.current = true;
    ttsLangRef.current = language || "en";
    ttsRateRef.current = ttsRate;

    setTtsPlaying(true);
    setTtsPaused(false);
    setTtsSource(sourceId);
    setTtsTotalChunks(chunks.length);
    setTtsCurrentChunk(1);

    playNextTtsChunk();
  }

  // Voice Speech-to-Text (STT) Controller
  function startVoiceInput(target = "search") {
    const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRec) {
      setSpeechError("Speech recognition is not supported in this browser. Please use Chrome, Edge, or a Web Speech API supported browser.");
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

      let langCode = "en-IN";
      if (selectedLang === "hi") langCode = "hi-IN";
      else if (selectedLang === "mr") langCode = "mr-IN";
      else if (selectedLang === "en") langCode = "en-IN";
      else langCode = navigator.language || "en-IN";

      recognition.lang = langCode;

      setIsListening(true);
      setListeningTarget(target);
      setSpeechError("");
      setLiveTranscript("");

      recognition.onstart = () => {
        setIsListening(true);
      };

      recognition.onresult = (event) => {
        let finalTrans = "";
        let interimTrans = "";
        for (let i = 0; i < event.results.length; i++) {
          if (event.results[i].isFinal) {
            finalTrans += event.results[i][0].transcript;
          } else {
            interimTrans += event.results[i][0].transcript;
          }
        }
        const text = finalTrans || interimTrans;
        setLiveTranscript(text);

        if (target === "search") {
          setQuestion(text);
        } else if (target === "docSearch") {
          setDocSearch(text);
        } else if (target === "extract") {
          setExtractText((prev) => (prev ? prev + " " + text : text));
        }
      };

      recognition.onerror = (event) => {
        console.warn("Speech recognition error:", event.error);
        if (event.error === "not-allowed") {
          setSpeechError("Microphone permission was denied. Please allow microphone access in your browser address bar.");
        } else if (event.error === "no-speech") {
          setSpeechError("No speech detected. Please try clicking the microphone again.");
        } else {
          setSpeechError(`Speech recognition error: ${event.error}`);
        }
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
      console.error("Speech recognition start failed:", err);
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

  // Official Documents Hub & Reader Handlers
  async function fetchDocuments() {
    setDocsLoading(true);
    try {
      const res = await fetch(`${API}/documents`);
      if (res.ok) {
        const data = await res.json();
        setDocsList(data);
      }
    } catch (err) {
      console.error("Failed to fetch documents:", err);
    } finally {
      setDocsLoading(false);
    }
  }

  async function openDocumentDetails(doc) {
    setSelectedDoc(doc);
    setSelectedDocText("");
    setDocTextLoading(true);
    stopTts();
    try {
      const res = await fetch(`${API}/documents/${doc.id}/text`);
      if (res.ok) {
        const data = await res.json();
        setSelectedDocText(data.text || "Document text is empty or could not be loaded.");
      } else {
        setSelectedDocText("Could not load text for this document.");
      }
    } catch (err) {
      setSelectedDocText(`Error loading document text: ${err.message}`);
    } finally {
      setDocTextLoading(false);
    }
  }

  function closeDocumentReader() {
    stopTts();
    setSelectedDoc(null);
    setSelectedDocText("");
  }

  async function fetchSchemes() {
    try {
      const res = await fetch(`${API}/schemes/raw-budget`);
      if (res.ok) {
        const data = await res.json();
        setSchemesList(data);
      }
    } catch {
      // ignore
    }
  }

  async function ask(e, customQuery) {
    if (e) e.preventDefault();
    const q = (customQuery !== undefined ? customQuery : question).trim();
    if (q.length < 5) return;

    setLoading(true);
    setError("");
    setResult(null);
    stopTts();
    stopVoiceInput();

    try {
      const res = await fetch(`${API}/research`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: q, language: selectedLang }),
      });

      const data = await res.json();

      if (!res.ok) {
        throw new Error(data.detail || `Request failed with status ${res.status}`);
      }

      setResult(data);
      fetchHistory();
      fetchHealth();
    } catch (err) {
      setError(err.message || "An unexpected error occurred.");
    } finally {
      setLoading(false);
    }
  }



  function handleKeyDown(e) {
    if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
      ask(e);
    }
  }

  return (
    <div className="portal-container">
      {/* Top Navbar */}
      <header className="navbar">
        <div className="nav-brand">
          <div className="portal-emblem">🏛️</div>
          <div>
            <div className="nav-title">GovResearch AI</div>
            <div className="nav-subtitle">Source-Grounded Government Research Agent</div>
          </div>
        </div>

        <div className="nav-badges">
          <div className="status-badge live">
            <span className="pulsing-dot" />
            <span>API Online</span>
          </div>

          <div
            className="status-badge live"
            onClick={() => setShowSchemesModal(true)}
            title="Browse all 104 Maharashtra Agriculture Schemes (2026-27)"
            style={{ cursor: "pointer", background: "rgba(16, 185, 129, 0.15)", borderColor: "rgba(16, 185, 129, 0.4)", color: "#059669", fontWeight: 600 }}
          >
            📊 104 Active Schemes
          </div>

          <div
            className={`status-badge ${health?.has_api_key ? "key-active" : "key-inactive"}`}
            onClick={() => setShowApiKeyModal(true)}
            title="Click to view API Key settings"
            style={{ cursor: "pointer" }}
          >
            🔑 {health?.has_api_key ? (health?.llm_model?.includes("Groq") ? "Groq Active" : "LLM Active") : "API Key Not Set"}
          </div>

          <button
            type="button"
            className="theme-toggle-btn"
            onClick={toggleTheme}
            title={theme === "light" ? "Switch to Dark Theme" : "Switch to Light Theme"}
          >
            {theme === "light" ? "🌙 Dark" : "☀️ Light"}
          </button>

          <button
            className="nav-btn"
            style={{ background: "linear-gradient(135deg, #0284c7, #0d9488)", color: "#ffffff", border: "none" }}
            onClick={() => { fetchStructuredSchemes(); setShowStructuredModal(true); }}
          >
            🏛️ Structured Schemes ({health?.structured_schemes || structuredSchemes.length || 12})
          </button>

          <button className="nav-btn" onClick={() => setShowSchemesModal(true)}>
            📊 Maharashtra BDS Budget
          </button>

          <button
            className="nav-btn"
            style={{ background: "linear-gradient(135deg, #4f46e5, #0284c7)", color: "#ffffff", border: "none" }}
            onClick={() => { fetchDocuments(); setShowDocsModal(true); }}
            title="Browse official documents, guidelines, and compendiums with voice reader"
          >
            📑 Official Documents ({health?.total_documents || docsList.length || 13})
          </button>
        </div>
      </header>

      {/* Main Grid Layout */}
      <div className="layout">
        {/* Sidebar History */}
        <aside className="sidebar">
          <div className="sidebar-header">
            <div className="sidebar-title-wrap">
              <h3>Recent Queries</h3>
              <span className="badge-count">{history.length}</span>
            </div>
            {history.length > 0 && (
              <button
                type="button"
                className="btn-clear-history"
                onClick={handleClearAllHistory}
                disabled={clearingHistory}
                title="Clear all recent search history"
              >
                {clearingHistory ? "Clearing..." : "🗑️ Clear All"}
              </button>
            )}
          </div>

          {history.length === 0 ? (
            <div className="empty-history">
              <p className="muted">Your verified research queries and answers will appear here.</p>
            </div>
          ) : (
            <ul className="history-list">
              {history.map((h) => (
                <li
                  key={h.id}
                  className="history-item"
                  onClick={() => {
                    setQuestion(h.question);
                    if (h.answer) {
                      setResult({
                        id: h.id,
                        answer: h.answer,
                        sources: h.sources || [],
                        status: h.status,
                        language: h.language || "en",
                        detected_language: h.detected_language,
                        practical_steps: h.practical_steps || [],
                        clarifying_question: h.clarifying_question,
                        missing_evidence_warning: h.missing_evidence_warning,
                        conflicts: h.conflicts || [],
                        retrieved_chunks: h.retrieved_chunks || [],
                      });
                      setError("");
                    } else {
                      ask(null, h.question);
                    }
                  }}
                >
                  <span className="history-icon">💬</span>
                  <div className="history-text">
                    <span className="history-q" title={h.question}>{h.question}</span>
                    <span className="history-meta">{h.created_at ? new Date(h.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : "Recent"}</span>
                  </div>
                  <button
                    type="button"
                    className="history-delete-btn"
                    onClick={(e) => handleDeleteHistoryItem(e, h.id)}
                    title="Remove this search query"
                    aria-label={`Remove query: ${h.question}`}
                  >
                    ✕
                  </button>
                </li>
              ))}
            </ul>
          )}

          <div className="sidebar-footer">
            <div className="info-box">
              <strong>Grounded RAG Guarantee</strong>
              <p>Every response is cross-checked against indexed official gazettes, guidelines, and ministry portals.</p>
            </div>
          </div>
        </aside>

        {/* Main Content Area */}
        <main className="main-content">
          <div className="hero-banner">
            <div className="hero-tag">GOVERNMENT SCHEME & POLICY RESEARCH INTELLIGENCE</div>
            <h1>Government Scheme Research Agent</h1>
            <p className="hero-description">
              Verified answers for government schemes, farmer welfare, welfare policies, eligibility criteria, and benefits.
              Every response is strictly verified with direct citations and hallucination checks against official guidelines.
            </p>
          </div>

          {/* Domain Category Tabs */}
          <div className="category-tabs">
            {DOMAIN_CATEGORIES.map((cat) => (
              <button
                key={cat.id}
                type="button"
                className={`category-tab-btn ${activeCategory === cat.id ? "active" : ""}`}
                onClick={() => setActiveCategory(cat.id)}
              >
                {cat.label}
              </button>
            ))}
          </div>

          {/* Suggested Queries for Active Category */}
          {(() => {
            const currentCat = DOMAIN_CATEGORIES.find((c) => c.id === activeCategory) || DOMAIN_CATEGORIES[0];
            return (
              <div className="chips-container">
                <div className="chips-header">
                  <span className="chips-label">Research Queries for {currentCat.label}:</span>
                  <span className="chips-sublabel">{currentCat.description}</span>
                </div>
                <div className="chips-list">
                  {currentCat.questions.map((q, idx) => (
                    <button
                      key={idx}
                      type="button"
                      className="chip-btn"
                      onClick={() => {
                        setQuestion(q);
                        ask(null, q);
                      }}
                    >
                      {q}
                    </button>
                  ))}
                </div>
              </div>
            );
          })()}

          {/* Language Preference Selector */}
          <div className="language-selector-bar">
            <div className="lang-label">
              <span>🗣️</span>
              <span>Response Language / भाषा निवडा:</span>
            </div>
            <div className="lang-buttons">
              <button
                type="button"
                className={`lang-btn ${selectedLang === "auto" ? "active" : ""}`}
                onClick={() => setSelectedLang("auto")}
                title="Automatically detect question language"
              >
                🌐 Auto Detect
              </button>
              <button
                type="button"
                className={`lang-btn ${selectedLang === "en" ? "active" : ""}`}
                onClick={() => setSelectedLang("en")}
              >
                🇬🇧 English
              </button>
              <button
                type="button"
                className={`lang-btn ${selectedLang === "hi" ? "active" : ""}`}
                onClick={() => setSelectedLang("hi")}
              >
                🇮🇳 हिन्दी (Hindi)
              </button>
              <button
                type="button"
                className={`lang-btn ${selectedLang === "mr" ? "active" : ""}`}
                onClick={() => setSelectedLang("mr")}
              >
                🚩 मराठी (Marathi)
              </button>
            </div>
          </div>

          {/* Search Form */}
          <form className="search-card" onSubmit={ask}>
            {/* Voice Input Toolbar */}
            <div className="search-voice-bar">
              <div style={{ display: "flex", alignItems: "center", gap: "10px", flexWrap: "wrap", flex: 1 }}>
                <button
                  type="button"
                  className={`voice-mic-btn ${isListening && listeningTarget === "search" ? "listening" : ""}`}
                  onClick={() => (isListening && listeningTarget === "search" ? stopVoiceInput() : startVoiceInput("search"))}
                  title="Click to speak your research query in English, Hindi (हिन्दी) or Marathi (मराठी)"
                >
                  <span>{isListening && listeningTarget === "search" ? "⏹️ Stop Listening" : "🎙️ Voice Search / आवाज विचारा"}</span>
                </button>

                {isListening && listeningTarget === "search" ? (
                  <div className="voice-listening-active-box">
                    <span className="pulse-recording-dot" />
                    <span className="voice-live-text">
                      🎙️ Listening ({selectedLang === "hi" ? "हिन्दी" : selectedLang === "mr" ? "मराठी" : selectedLang === "en" ? "English" : "Auto / Default"})... {liveTranscript || "Speak clearly into microphone..."}
                    </span>
                  </div>
                ) : (
                  <span style={{ fontSize: "0.78rem", color: "var(--text-dim)" }}>
                    Speak query in <strong>{selectedLang === "hi" ? "हिन्दी" : selectedLang === "mr" ? "मराठी" : selectedLang === "en" ? "English" : "selected language"}</strong>
                  </span>
                )}
              </div>

              <label className="auto-search-toggle" title="Automatically research schemes when you finish speaking">
                <input
                  type="checkbox"
                  checked={autoSearchOnSpeech}
                  onChange={(e) => setAutoSearchOnSpeech(e.target.checked)}
                />
                <span>⚡ Auto-search after speech</span>
              </label>
            </div>

            {speechError && (
              <div style={{
                marginBottom: "10px",
                padding: "8px 12px",
                borderRadius: "var(--radius-sm)",
                background: "var(--rose-bg)",
                border: "1px solid var(--rose-border)",
                color: "var(--rose-text)",
                fontSize: "0.82rem",
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center"
              }}>
                <span>⚠️ {speechError}</span>
                <button type="button" onClick={() => setSpeechError("")} style={{ background: "none", border: "none", color: "inherit", cursor: "pointer", fontWeight: "bold" }}>✕</button>
              </div>
            )}

            <div className="textarea-wrapper">
              <textarea
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Ask about farmer credit, crop diseases, pest outbreaks, fertilizer dosage, or government schemes (e.g., How to apply for KCC or prevent wheat yellowing?)"
                rows={3}
              />
            </div>

            <div className="search-footer">
              <span className="hint-text">Tip: Press <strong>Ctrl + Enter</strong> or click <strong>🎙️</strong> to speak in Hindi/Marathi/English</span>
              <div className="btn-group">
                {(question || result || error) && (
                  <button
                    type="button"
                    className="btn-secondary"
                    onClick={() => {
                      setQuestion("");
                      setResult(null);
                      setError("");
                    }}
                    title="Clear search query and displayed findings"
                  >
                    Clear Search
                  </button>
                )}
                <button type="submit" className="btn-primary" disabled={loading || question.trim().length < 5}>
                  {loading ? (
                    <>
                      <span className="spinner" />
                      Researching Evidence...
                    </>
                  ) : (
                    <>
                      <span>🔍</span> Research Schemes
                    </>
                  )}
                </button>
              </div>
            </div>
          </form>

          {/* Alerts */}
          {error && (
            <div className="notice-card error">
              <div className="notice-icon">⚠️</div>
              <div className="notice-body">
                <strong>Research Error</strong>
                <p>{error}</p>
                {error.includes("ANTHROPIC_API_KEY") && (
                  <button
                    type="button"
                    className="notice-action-btn"
                    onClick={() => setShowApiKeyModal(true)}
                  >
                    Configure API Key
                  </button>
                )}
              </div>
            </div>
          )}

          {result?.status === "insufficient_evidence" && (
            <div className="notice-card warn">
              <div className="notice-icon">📋</div>
              <div className="notice-body">
                <strong>Insufficient Official Evidence</strong>
                <p>The indexed official records do not contain enough verified evidence to answer this question with certainty.</p>
              </div>
            </div>
          )}

          {/* Structured Scheme Card (Matched from PostgreSQL / Database) */}
          {result?.matched_scheme && (
            <div
              className="structured-scheme-box"
              style={{
                marginBottom: "20px",
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
                    <h3 style={{ margin: 0, fontSize: "1.25rem", color: "var(--text-main)", fontWeight: 700 }}>
                      {result.matched_scheme.hindi_name}
                    </h3>
                  </div>
                  <div style={{ fontSize: "0.92rem", color: "var(--text-muted)", marginTop: "4px" }}>
                    {result.matched_scheme.scheme_name}
                  </div>
                </div>
                <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
                  <span style={{ background: "var(--emerald-bg)", color: "var(--emerald-text)", border: "1px solid var(--emerald-border)", padding: "4px 10px", borderRadius: "12px", fontSize: "0.78rem", fontWeight: 700 }}>
                    ● {result.matched_scheme.status || "Active"}
                  </span>
                  <span style={{ background: "var(--bg-secondary)", color: "var(--accent)", border: "1px solid var(--panel-border)", padding: "4px 10px", borderRadius: "12px", fontSize: "0.78rem", fontWeight: 700 }}>
                    📍 {result.matched_scheme.state_district}
                  </span>
                  <span style={{ background: "var(--bg-secondary)", color: "var(--text-muted)", border: "1px solid var(--panel-border)", padding: "4px 10px", borderRadius: "12px", fontSize: "0.78rem" }}>
                    🏷️ {result.matched_scheme.category}
                  </span>
                </div>
              </div>

              {/* 9 Structured Fields Grid */}
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: "12px", marginTop: "16px" }}>
                <div style={{ background: "var(--bg-secondary)", padding: "12px 14px", borderRadius: "var(--radius-md)", border: "1px solid var(--panel-border)" }}>
                  <span style={{ fontSize: "0.75rem", fontWeight: 700, color: "var(--text-dim)", textTransform: "uppercase" }}>🎯 पात्रता (Eligibility)</span>
                  <p style={{ margin: "4px 0 0", fontSize: "0.86rem", lineHeight: "1.45", color: "var(--text-main)" }}>{result.matched_scheme.eligibility}</p>
                </div>
                <div style={{ background: "var(--bg-secondary)", padding: "12px 14px", borderRadius: "var(--radius-md)", border: "1px solid var(--panel-border)" }}>
                  <span style={{ fontSize: "0.75rem", fontWeight: 700, color: "var(--text-dim)", textTransform: "uppercase" }}>👥 पात्र लाभार्थी (Beneficiary)</span>
                  <p style={{ margin: "4px 0 0", fontSize: "0.86rem", lineHeight: "1.45", color: "var(--text-main)" }}>{result.matched_scheme.beneficiary}</p>
                </div>
                <div style={{ background: "var(--bg-secondary)", padding: "12px 14px", borderRadius: "var(--radius-md)", border: "1px solid var(--panel-border)" }}>
                  <span style={{ fontSize: "0.75rem", fontWeight: 700, color: "var(--text-dim)", textTransform: "uppercase" }}>💰 वित्तीय लाभ (Benefits)</span>
                  <p style={{ margin: "4px 0 0", fontSize: "0.86rem", lineHeight: "1.45", color: "var(--text-main)" }}>{result.matched_scheme.benefits}</p>
                </div>
                <div style={{ background: "var(--bg-secondary)", padding: "12px 14px", borderRadius: "var(--radius-md)", border: "1px solid var(--panel-border)" }}>
                  <span style={{ fontSize: "0.75rem", fontWeight: 700, color: "var(--text-dim)", textTransform: "uppercase" }}>📄 आवश्यक दस्तावेज़ (Documents Required)</span>
                  <div style={{ margin: "4px 0 0", fontSize: "0.86rem", lineHeight: "1.45", whiteSpace: "pre-line", color: "var(--text-main)" }}>{result.matched_scheme.documents}</div>
                </div>
              </div>

              {result.matched_scheme.official_source_url && (
                <div style={{ marginTop: "14px", paddingTop: "12px", borderTop: "1px solid var(--panel-border)", display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "8px" }}>
                  <span style={{ fontSize: "0.82rem", color: "var(--text-dim)" }}>
                    🏛️ नोडल विभाग: {result.matched_scheme.authority}
                  </span>
                  <a
                    href={result.matched_scheme.official_source_url}
                    target="_blank"
                    rel="noreferrer"
                    style={{ fontSize: "0.85rem", color: "var(--accent)", fontWeight: 700, textDecoration: "none" }}
                  >
                    🔗 आधिकारिक पोर्टल (Official Portal) ↗
                  </a>
                </div>
              )}
            </div>
          )}

          {/* Research Answer */}
          {result?.answer && (
            <section className="answer-card">
              <div className="answer-header">
                <div className="answer-title">
                  <span className="answer-badge">Verified Synthesis</span>
                  {result.language && (
                    <span className="lang-badge">
                      🌐 {result.language === "mr" ? "मराठी (Marathi)" : result.language === "hi" ? "हिन्दी (Hindi)" : "English"}
                      {result.detected_language && result.detected_language !== result.language && ` (Detected: ${result.detected_language})`}
                    </span>
                  )}
                  <h2>
                    {result.language === "mr" ? "अधिकृत शासकीय संशोधन निष्कर्ष" :
                     result.language === "hi" ? "आधिकारिक सरकारी शोध निष्कर्ष" :
                     "Official Research Findings"}
                  </h2>
                </div>

                <div style={{ display: "flex", alignItems: "center", gap: "10px", flexWrap: "wrap" }}>
                  {/* Voice Audio Toolbar for Findings */}
                  <div className="audio-player-toolbar">
                    {ttsPlaying && ttsSource === "findings" ? (
                      <>
                        {ttsPaused ? (
                          <button type="button" className="audio-btn active" onClick={resumeTts} title="Resume voice readout">
                            ▶️ Resume
                          </button>
                        ) : (
                          <button type="button" className="audio-btn active" onClick={pauseTts} title="Pause voice readout">
                            ⏸️ Pause
                          </button>
                        )}
                        <button type="button" className="audio-btn danger" onClick={stopTts} title="Stop voice readout">
                          ⏹️ Stop
                        </button>

                        <div className="audio-waveform-bars" title="Voice audio active">
                          <span className="audio-wave-bar" />
                          <span className="audio-wave-bar" />
                          <span className="audio-wave-bar" />
                          <span className="audio-wave-bar" />
                          <span className="audio-wave-bar" />
                        </div>

                        <span style={{ fontSize: "0.74rem", color: "var(--accent)", fontWeight: 700 }}>
                          Section {ttsCurrentChunk}/{ttsTotalChunks}
                        </span>
                      </>
                    ) : (
                      <button
                        type="button"
                        className="audio-btn"
                        onClick={() => playTts(result.answer, "findings", result.language || selectedLang)}
                        title="Listen to official research findings read aloud"
                      >
                        🔊 Read Findings Aloud (ऐका / सुनें)
                      </button>
                    )}

                    <div className="speed-selector-group" title="Adjust speech playback speed">
                      {[0.8, 1.0, 1.25, 1.5].map((rate) => (
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

                  {result.id && <span className="citation-tag">Record #{result.id}</span>}
                </div>
              </div>

              <div className="markdown-body">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{result.answer}</ReactMarkdown>
              </div>

              {/* Follow-up Clarifying Question */}
              {result?.clarifying_question && (
                <div className="farmer-clarifying-card">
                  <div className="farmer-clarifying-content">
                    <span className="clarify-icon">💡</span>
                    <div className="clarify-text">
                      <strong>
                        {result.language === "mr" ? "स्पष्टीकरण प्रश्न (अधिक अचूक उत्तरासाठी):" :
                         result.language === "hi" ? "स्पष्टीकरण प्रश्न (अधिक सटीक उत्तर के लिए):" :
                         "Clarifying Follow-Up Question:"}
                      </strong>
                      <p>{result.clarifying_question}</p>
                    </div>
                  </div>
                  <button
                    type="button"
                    className="btn-clarify-ask"
                    onClick={() => {
                      const refined = `${question} - ${result.clarifying_question}`;
                      setQuestion(refined);
                      ask(null, refined);
                    }}
                    title="Click to refine query with this clarification"
                  >
                    ✍️ {result.language === "mr" ? "या तपशीलासह विचारा" :
                        result.language === "hi" ? "इस विवरण के साथ पूछें" :
                        "Refine Query"}
                  </button>
                </div>
              )}

              {/* Practical Farmer Next Steps */}
              {result?.practical_steps?.length > 0 && (
                <section className="practical-steps-card">
                  <div className="practical-steps-header">
                    <span className="steps-icon">🚜</span>
                    <div>
                      <h3>
                        {result.language === "mr" ? "शेतकऱ्यांसाठी पुढील व्यावहारिक पावले" :
                         result.language === "hi" ? "किसानों के लिए अगले व्यावहारिक कदम" :
                         "Practical Farmer Next Steps"}
                      </h3>
                      <span className="steps-sub">
                        {result.language === "mr" ? "अधिकृत शासकीय पुराव्यांवर आधारित कृती मार्गदर्शक" :
                         result.language === "hi" ? "आधिकारिक सरकारी साक्ष्यों पर आधारित कार्य योजना" :
                         "Actionable steps supported strictly by official records"}
                      </span>
                    </div>
                  </div>
                  <ol className="practical-steps-list">
                    {result.practical_steps.map((step, idx) => (
                      <li key={idx} className="practical-step-item">
                        <span className="step-number">{idx + 1}</span>
                        <span className="step-text">{step}</span>
                      </li>
                    ))}
                  </ol>
                </section>
              )}

              {/* Missing Evidence / Scope Warning */}
              {result?.missing_evidence_warning && (
                <div className="notice-card warn" style={{ marginTop: "16px" }}>
                  <div className="notice-icon">⚠️</div>
                  <div className="notice-body">
                    <strong>
                      {result.language === "mr" ? "अधिकृत माहिती मर्यादा सूचना" :
                       result.language === "hi" ? "आधिकारिक साक्ष्य सीमा चेतावनी" :
                       "Official Evidence Scope Warning"}
                    </strong>
                    <p>{result.missing_evidence_warning}</p>
                  </div>
                </div>
              )}
            </section>
          )}

          {/* Conflicts Warning */}
          {result?.conflicts?.length > 0 && (
            <div className="notice-card conflict">
              <div className="notice-icon">⚡</div>
              <div className="notice-body">
                <strong>Source Discrepancies Detected</strong>
                <p>The verified documents contain conflicting terms or numbers on this topic:</p>
                <ul>
                  {result.conflicts.map((c, i) => (
                    <li key={i}>
                      <strong>{c.topic}</strong>: {c.explanation}
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          )}

          {/* Citations & Sources */}
          {result?.sources?.length > 0 && (
            <section className="sources-card">
              <div className="sources-header">
                <h3>Official Referenced Sources</h3>
                <span className="badge-count">{result.sources.length} Verified</span>
              </div>

              <div className="sources-grid">
                {result.sources.map((s) => (
                  <div key={s.id} className="source-item">
                    <div className="source-num">[{s.id}]</div>
                    <div className="source-details">
                      <div className="source-name" style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: "8px" }}>
                        {s.url ? (
                          <a href={s.url} target="_blank" rel="noreferrer" className="source-link">
                            {s.title} ↗
                          </a>
                        ) : (
                          <span className="source-title-plain">{s.title}</span>
                        )}
                        <button
                          type="button"
                          className={`btn-listen-mini ${ttsPlaying && ttsSource === `source-${s.id}` ? "playing" : ""}`}
                          onClick={() => {
                            if (ttsPlaying && ttsSource === `source-${s.id}`) {
                              stopTts();
                            } else {
                              const srcText = `${s.title}. Authority: ${s.authority || s.department || "Official department"}.`;
                              playTts(srcText, `source-${s.id}`, result?.language || selectedLang);
                            }
                          }}
                          title="Listen to official document citation"
                        >
                          {ttsPlaying && ttsSource === `source-${s.id}` ? "⏹️ Stop" : "🔊 Listen"}
                        </button>
                      </div>

                      {s.url ? (
                        <div style={{ fontSize: "0.75rem", color: "var(--accent)", wordBreak: "break-all" }}>
                          {s.url}
                        </div>
                      ) : (
                        <div style={{ fontSize: "0.75rem", color: "#e11d48", fontWeight: 500 }}>
                          ⚠️ Source URL unavailable on official portal
                        </div>
                      )}

                      <div className="source-meta">
                        <span className="meta-badge authority">🏛️ {s.department || s.authority || "Official Authority"}</span>
                        <span className="meta-badge date" title="Official publication or revision date provided by source">
                          📅 Official Date: {s.last_updated || (s.has_official_date ? (s.updated_date || s.publication_date) : "Official update date not available.")}
                        </span>
                        <span className="meta-badge checked" title="Date verified by our system" style={{ color: "#059669", background: "rgba(16, 185, 129, 0.1)", borderColor: "rgba(16, 185, 129, 0.3)" }}>
                          🛡️ Checked: {s.last_checked || "Verified during retrieval"}
                        </span>
                        {s.page_number && (
                          <span className="meta-badge page">📄 Page {s.page_number}</span>
                        )}
                        {s.category && (
                          <span className="meta-badge category">📁 {s.category.replace(/_/g, " ")}</span>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>

              <div className="source-advisory" style={{
                marginTop: "16px",
                padding: "10px 14px",
                background: "rgba(245, 158, 11, 0.08)",
                border: "1px solid rgba(245, 158, 11, 0.25)",
                borderRadius: "var(--radius-sm)",
                fontSize: "0.82rem",
                color: "var(--text-dim)",
                lineHeight: "1.5"
              }}>
                ℹ️ <strong>Official Freshness Notice:</strong> Information is directly grounded in official government records. Verified Check Date reflects when our system checked the source; Official Date reflects the publication date declared by the issuing department. Please verify details on the official government portal before making administrative or financial decisions.
              </div>
            </section>
          )}

          {/* Retrieved Evidence Chunks with Similarity Scores */}
          {result?.retrieved_chunks?.length > 0 && (
            <section className="sources-card" style={{ marginTop: "20px" }}>
              <div className="sources-header">
                <h3>🔍 Retrieved Evidence Chunks &amp; Similarity Scores</h3>
                <span className="badge-count" style={{ background: "rgba(59, 130, 246, 0.15)", color: "#2563eb" }}>
                  {result.retrieved_chunks.length} Chunks (k=5)
                </span>
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: "12px", marginTop: "12px" }}>
                {result.retrieved_chunks.map((chk) => (
                  <div key={chk.chunk_index} style={{
                    background: "var(--bg-secondary)",
                    border: "1px solid var(--panel-border)",
                    borderRadius: "var(--radius-md)",
                    padding: "14px",
                    display: "flex",
                    flexDirection: "column",
                    gap: "8px"
                  }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "6px" }}>
                      <span style={{ fontWeight: 700, color: "var(--text-main)", fontSize: "0.88rem" }}>
                        Chunk {chk.chunk_index}: {chk.source}
                      </span>
                      <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                        <span style={{
                          padding: "2px 8px",
                          borderRadius: "12px",
                          fontSize: "0.78rem",
                          fontWeight: 700,
                          background: "rgba(16, 185, 129, 0.15)",
                          color: "#059669",
                          fontFamily: "var(--font-mono)"
                        }}>
                          Similarity Score: {chk.similarity_score}
                        </span>
                        <button
                          type="button"
                          className={`btn-listen-mini ${ttsPlaying && ttsSource === `chunk-${chk.chunk_index}` ? "playing" : ""}`}
                          onClick={() => {
                            if (ttsPlaying && ttsSource === `chunk-${chk.chunk_index}`) {
                              stopTts();
                            } else {
                              playTts(chk.text, `chunk-${chk.chunk_index}`, result?.language || selectedLang);
                            }
                          }}
                          title="Listen to this official evidence chunk read aloud"
                        >
                          {ttsPlaying && ttsSource === `chunk-${chk.chunk_index}` ? "⏹️ Stop" : "🔊 Listen"}
                        </button>
                      </div>
                    </div>
                    <div style={{ display: "flex", gap: "10px", flexWrap: "wrap", fontSize: "0.78rem", color: "var(--text-muted)" }}>
                      <span>📄 Page: <strong>{chk.page}</strong></span>
                      <span>🏛️ Dept: <strong>{chk.department}</strong></span>
                      <span>📅 Year: <strong>{chk.year}</strong></span>
                      <span>📑 Type: <strong>{chk.document_type}</strong></span>
                    </div>
                    <div style={{
                      background: "var(--input-bg)",
                      border: "1px solid var(--panel-border)",
                      borderRadius: "4px",
                      padding: "8px 10px",
                      fontSize: "0.82rem",
                      color: "var(--text-main)",
                      fontFamily: "var(--font-mono)",
                      maxHeight: "120px",
                      overflowY: "auto",
                      whiteSpace: "pre-wrap"
                    }}>
                      {chk.text}
                    </div>
                  </div>
                ))}
              </div>
            </section>
          )}
        </main>
      </div>



      {/* API Key Modal */}
      {showApiKeyModal && (
        <div className="modal-overlay" onClick={() => setShowApiKeyModal(false)}>
          <div className="modal-card" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>AI Provider Configuration</h3>
              <button className="close-btn" onClick={() => setShowApiKeyModal(false)}>✕</button>
            </div>

            <div className="api-modal-content">
              <p>
                The research agent can run on either <strong>Groq (Free &amp; Ultra-Fast)</strong> or <strong>Anthropic Claude</strong>.
              </p>

              {/* Instant Key Activation Form */}
              <form onSubmit={handleSaveKey} className="key-activate-form" style={{marginTop: "16px", marginBottom: "20px"}}>
                <div style={{display: "flex", gap: "10px", marginBottom: "10px"}}>
                  <button
                    type="button"
                    className={`btn-secondary ${keyProvider === "groq" ? "active" : ""}`}
                    style={{
                      flex: 1,
                      borderColor: keyProvider === "groq" ? "var(--accent)" : "var(--panel-border)",
                      color: keyProvider === "groq" ? "var(--accent)" : "var(--text-muted)",
                      fontWeight: 600,
                    }}
                    onClick={() => setKeyProvider("groq")}
                  >
                    ⚡ Groq (Free & Fast)
                  </button>
                  <button
                    type="button"
                    className={`btn-secondary ${keyProvider === "anthropic" ? "active" : ""}`}
                    style={{
                      flex: 1,
                      borderColor: keyProvider === "anthropic" ? "var(--accent)" : "var(--panel-border)",
                      color: keyProvider === "anthropic" ? "var(--accent)" : "var(--text-muted)",
                      fontWeight: 600,
                    }}
                    onClick={() => setKeyProvider("anthropic")}
                  >
                    🧠 Anthropic Claude
                  </button>
                </div>

                <div className="form-group" style={{marginBottom: "12px"}}>
                  <label>
                    {keyProvider === "groq" ? "Groq API Key (starts with gsk_)" : "Anthropic API Key (starts with sk-ant-)"}
                  </label>
                  <input
                    type="password"
                    placeholder={keyProvider === "groq" ? "gsk_..." : "sk-ant-..."}
                    value={apiKeyInput}
                    onChange={(e) => setApiKeyInput(e.target.value)}
                    required
                  />
                </div>

                <div style={{display: "flex", gap: "10px", alignItems: "center"}}>
                  <button type="submit" className="btn-primary" disabled={savingKey || !apiKeyInput.trim()}>
                    {savingKey ? "Saving & Activating..." : "Save & Activate Key"}
                  </button>
                  {keyProvider === "groq" && (
                    <a
                      href="https://console.groq.com/keys"
                      target="_blank"
                      rel="noreferrer"
                      style={{fontSize: "0.82rem", color: "var(--accent)", textDecoration: "none", fontWeight: 600}}
                    >
                      Get Free Groq Key ↗
                    </a>
                  )}
                </div>

                {keySaveStatus && (
                  <div style={{
                    marginTop: "12px",
                    padding: "10px 14px",
                    borderRadius: "var(--radius-md)",
                    fontSize: "0.85rem",
                    background: keySaveStatus.startsWith("✅") ? "var(--emerald-bg)" : "var(--rose-bg)",
                    color: keySaveStatus.startsWith("✅") ? "var(--emerald-text)" : "var(--rose-text)",
                    border: `1px solid ${keySaveStatus.startsWith("✅") ? "var(--emerald-border)" : "var(--rose-border)"}`,
                  }}>
                    {keySaveStatus}
                  </div>
                )}
              </form>

              <div className="config-box">
                <span className="config-title">Option 1: Free Groq API Key (Recommended)</span>
                <ol>
                  <li>Get a free key instantly at <a href="https://console.groq.com/keys" target="_blank" rel="noreferrer" style={{color: "#38bdf8"}}>console.groq.com/keys</a> (no credit card needed).</li>
                  <li>Open the <code>.env</code> file in the project root:</li>
                  <pre className="code-block">GROQ_API_KEY=gsk_your_groq_key_here</pre>
                  <li>Save the file. It will immediately enable live research!</li>
                </ol>
              </div>

              <div className="config-box">
                <span className="config-title">Option 2: Anthropic Claude Key</span>
                <ol>
                  <li>Get an Anthropic key at <a href="https://console.anthropic.com/settings/keys" target="_blank" rel="noreferrer" style={{color: "#38bdf8"}}>console.anthropic.com</a>.</li>
                  <li>In <code>.env</code> set:</li>
                  <pre className="code-block">ANTHROPIC_API_KEY=sk-ant-api03-your-key-here</pre>
                </ol>
              </div>

              <div className="status-summary">
                <div><strong>Current Engine:</strong> {health?.llm_model || "None configured"}</div>
                <div><strong>Status:</strong> {health?.has_api_key ? "✅ Live & Ready" : "⚠️ Key required for live research"}</div>
              </div>

              <button className="btn-primary" onClick={() => setShowApiKeyModal(false)}>
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Schemes Explorer Modal */}
      {showSchemesModal && (
        <div className="modal-overlay" onClick={() => setShowSchemesModal(false)}>
          <div
            className="modal-card"
            style={{ maxWidth: "1100px", width: "95vw", maxHeight: "90vh", display: "flex", flexDirection: "column" }}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="modal-header">
              <div>
                <h3 style={{ margin: 0 }}>📊 Maharashtra Active Agriculture Schemes (2026–2027)</h3>
                <p style={{ margin: "4px 0 0 0", fontSize: "0.82rem", color: "var(--text-muted)" }}>
                  Department of Agriculture, Govt of Maharashtra • 104 Active Schemes • BDS Outlays &amp; Expenditures (Rs. in Lakhs)
                </p>
              </div>
              <button className="close-btn" onClick={() => setShowSchemesModal(false)}>✕</button>
            </div>

            <div style={{ padding: "16px 24px", overflowY: "auto", flex: 1 }}>
              {/* Quick Metrics Bar */}
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: "12px", marginBottom: "16px" }}>
                <div style={{ background: "var(--bg-secondary)", padding: "12px 14px", borderRadius: "var(--radius-md)", border: "1px solid var(--panel-border)" }}>
                  <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", textTransform: "uppercase", fontWeight: 700 }}>Total Schemes</div>
                  <div style={{ fontSize: "1.3rem", fontWeight: 700, color: "var(--text-main)", marginTop: "2px" }}>104 Schemes</div>
                  <div style={{ fontSize: "0.72rem", color: "var(--text-dim)" }}>63 General • 19 SCCS • 22 TCS</div>
                </div>

                <div style={{ background: "var(--bg-secondary)", padding: "12px 14px", borderRadius: "var(--radius-md)", border: "1px solid var(--panel-border)" }}>
                  <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", textTransform: "uppercase", fontWeight: 700 }}>2026-27 Proposed Outlay</div>
                  <div style={{ fontSize: "1.3rem", fontWeight: 700, color: "var(--accent)", marginTop: "2px" }}>₹12,438.14 Cr</div>
                  <div style={{ fontSize: "0.72rem", color: "var(--text-dim)" }}>Rs. 12,43,813.52 Lakh</div>
                </div>

                <div style={{ background: "var(--bg-secondary)", padding: "12px 14px", borderRadius: "var(--radius-md)", border: "1px solid var(--panel-border)" }}>
                  <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", textTransform: "uppercase", fontWeight: 700 }}>BDS Released by FD</div>
                  <div style={{ fontSize: "1.3rem", fontWeight: 700, color: "var(--text-main)", marginTop: "2px" }}>₹3,508.79 Cr</div>
                  <div style={{ fontSize: "0.72rem", color: "var(--text-dim)" }}>Rs. 35,08,78.90 Lakh</div>
                </div>

                <div style={{ background: "var(--bg-secondary)", padding: "12px 14px", borderRadius: "var(--radius-md)", border: "1px solid var(--panel-border)" }}>
                  <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", textTransform: "uppercase", fontWeight: 700 }}>BDS Expenditure</div>
                  <div style={{ fontSize: "1.3rem", fontWeight: 700, color: "#10b981", marginTop: "2px" }}>₹2,218.61 Cr</div>
                  <div style={{ fontSize: "0.72rem", color: "#10b981" }}>63.2% of release spent</div>
                </div>
              </div>

              {/* Filter and Search Bar */}
              <div style={{ display: "flex", gap: "12px", alignItems: "center", flexWrap: "wrap", marginBottom: "16px" }}>
                <input
                  type="text"
                  placeholder="🔍 Search scheme name, code (e.g., Namo, Krushi, POCRA, 1101010312)..."
                  value={schemeSearch}
                  onChange={(e) => setSchemeSearch(e.target.value)}
                  style={{
                    flex: "1 1 300px",
                    padding: "9px 14px",
                    background: "var(--input-bg)",
                    border: "1px solid var(--input-border)",
                    borderRadius: "var(--radius-md)",
                    color: "var(--text-main)",
                    fontSize: "0.88rem"
                  }}
                />

                <div style={{ display: "flex", gap: "6px" }}>
                  {["all", "General", "SCCS", "TCS"].map((plan) => (
                    <button
                      key={plan}
                      type="button"
                      onClick={() => setSchemePlanFilter(plan)}
                      style={{
                        padding: "6px 14px",
                        borderRadius: "20px",
                        fontSize: "0.82rem",
                        fontWeight: 600,
                        border: "1px solid",
                        cursor: "pointer",
                        background: schemePlanFilter === plan ? "var(--accent)" : "var(--bg-secondary)",
                        color: schemePlanFilter === plan ? "#ffffff" : "var(--text-muted)",
                        borderColor: schemePlanFilter === plan ? "var(--accent)" : "var(--panel-border)"
                      }}
                    >
                      {plan === "all" ? "All Plans (104)" : plan}
                    </button>
                  ))}
                </div>
              </div>

              {/* Table */}
              <div style={{ border: "1px solid var(--panel-border)", borderRadius: "var(--radius-md)", overflowX: "auto" }}>
                <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.84rem", textAlign: "left" }}>
                  <thead>
                    <tr style={{ background: "var(--bg-secondary)", borderBottom: "1px solid var(--panel-border)" }}>
                      <th style={{ padding: "10px 12px", color: "var(--text-muted)", fontWeight: 600 }}>Sr</th>
                      <th style={{ padding: "10px 12px", color: "var(--text-muted)", fontWeight: 600 }}>Plan</th>
                      <th style={{ padding: "10px 12px", color: "var(--text-muted)", fontWeight: 600 }}>Code</th>
                      <th style={{ padding: "10px 12px", color: "var(--text-muted)", fontWeight: 600 }}>Scheme Title</th>
                      <th style={{ padding: "10px 12px", color: "var(--text-muted)", fontWeight: 600, textAlign: "right" }}>2026-27 Proposed (Lakh)</th>
                      <th style={{ padding: "10px 12px", color: "var(--text-muted)", fontWeight: 600, textAlign: "right" }}>BDS Released (Lakh)</th>
                      <th style={{ padding: "10px 12px", color: "var(--text-muted)", fontWeight: 600, textAlign: "right" }}>BDS Exp (Lakh)</th>
                      <th style={{ padding: "10px 12px", color: "var(--text-muted)", fontWeight: 600, textAlign: "center" }}>SDG</th>
                      <th style={{ padding: "10px 12px", color: "var(--text-muted)", fontWeight: 600, textAlign: "center" }}>Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {schemesList
                      .filter((s) => {
                        const matchesPlan = schemePlanFilter === "all" || s.plan_type === schemePlanFilter;
                        const query = schemeSearch.toLowerCase().trim();
                        const matchesQuery = !query ||
                          s.scheme_title.toLowerCase().includes(query) ||
                          s.scheme_code.toLowerCase().includes(query);
                        return matchesPlan && matchesQuery;
                      })
                      .map((s) => (
                        <tr
                          key={`${s.sr_no}-${s.scheme_code}`}
                          style={{
                            borderBottom: "1px solid var(--panel-border)",
                            transition: "background 0.15s ease"
                          }}
                        >
                          <td style={{ padding: "10px 12px", color: "var(--text-dim)", fontFamily: "var(--font-mono)" }}>{s.sr_no}</td>
                          <td style={{ padding: "10px 12px" }}>
                            <span style={{
                              padding: "2px 8px",
                              borderRadius: "12px",
                              fontSize: "0.75rem",
                              fontWeight: 600,
                              background: s.plan_type === "General" ? "rgba(59, 130, 246, 0.12)" : s.plan_type === "SCCS" ? "rgba(168, 85, 247, 0.12)" : "rgba(234, 88, 12, 0.12)",
                              color: s.plan_type === "General" ? "#2563eb" : s.plan_type === "SCCS" ? "#9333ea" : "#c2410c"
                            }}>
                              {s.plan_type}
                            </span>
                          </td>
                          <td style={{ padding: "10px 12px", fontFamily: "var(--font-mono)", fontSize: "0.8rem", color: "var(--text-muted)" }}>
                            {s.scheme_code}
                          </td>
                          <td style={{ padding: "10px 12px", fontWeight: 600, color: "var(--text-main)", maxWidth: "340px" }}>
                            {s.scheme_title}
                          </td>
                          <td style={{ padding: "10px 12px", textAlign: "right", fontFamily: "var(--font-mono)", fontWeight: 600, color: "var(--accent)" }}>
                            Rs. {s.proposed_outlay_2026_27_lakh.toLocaleString("en-IN", { minimumFractionDigits: 2 })}
                          </td>
                          <td style={{ padding: "10px 12px", textAlign: "right", fontFamily: "var(--font-mono)", color: "var(--text-muted)" }}>
                            Rs. {s.bds_release_by_fd_till_07_oct_26_lakh.toLocaleString("en-IN", { minimumFractionDigits: 2 })}
                          </td>
                          <td style={{ padding: "10px 12px", textAlign: "right", fontFamily: "var(--font-mono)", color: s.bds_expenditure_till_07_oct_26_lakh > 0 ? "#10b981" : "var(--text-dim)", fontWeight: 600 }}>
                            Rs. {s.bds_expenditure_till_07_oct_26_lakh.toLocaleString("en-IN", { minimumFractionDigits: 2 })}
                          </td>
                          <td style={{ padding: "10px 12px", textAlign: "center" }}>
                            <span style={{
                              padding: "2px 6px",
                              borderRadius: "4px",
                              fontSize: "0.72rem",
                              fontWeight: 700,
                              background: s.sdg_status === "A" ? "rgba(16, 185, 129, 0.15)" : "rgba(156, 163, 175, 0.15)",
                              color: s.sdg_status === "A" ? "#059669" : "#6b7280"
                            }}>
                              {s.sdg_status || "—"}
                            </span>
                          </td>
                          <td style={{ padding: "10px 12px", textAlign: "center" }}>
                            <button
                              type="button"
                              onClick={() => {
                                const q = `What are the financial outlays, allocations, and status for ${s.scheme_title} (Code: ${s.scheme_code}) under ${s.plan_type} plan?`;
                                setQuestion(q);
                                setShowSchemesModal(false);
                                ask(null, q);
                              }}
                              style={{
                                padding: "4px 10px",
                                background: "var(--accent)",
                                color: "#ffffff",
                                border: "none",
                                borderRadius: "4px",
                                fontSize: "0.76rem",
                                fontWeight: 600,
                                cursor: "pointer"
                              }}
                            >
                              Research ↗
                            </button>
                          </td>
                        </tr>
                      ))}
                  </tbody>
                </table>
              </div>
            </div>

            <div style={{ padding: "12px 24px", borderTop: "1px solid var(--panel-border)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <span style={{ fontSize: "0.82rem", color: "var(--text-muted)" }}>
                Showing active records parsed from Maharashtra Department of Agriculture BDS.
              </span>
              <button className="btn-primary" onClick={() => setShowSchemesModal(false)}>
                Close Explorer
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Structured Schemes Catalog Modal (PostgreSQL / Relational DB 9 Fields) */}
      {showStructuredModal && (
        <div className="modal-overlay" onClick={() => setShowStructuredModal(false)}>
          <div
            className="modal-card"
            style={{ maxWidth: "1200px", width: "96vw", maxHeight: "92vh", display: "flex", flexDirection: "column" }}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="modal-header">
              <div>
                <h3 style={{ margin: 0, display: "flex", alignItems: "center", gap: "8px" }}>
                  <span>🏛️</span> Structured Government Schemes (आधिकारिक सरकारी योजनाएं)
                </h3>
                <p style={{ margin: "4px 0 0 0", fontSize: "0.82rem", color: "var(--text-muted)" }}>
                  PostgreSQL / Relational Storage • 9 Standard Fields: Scheme name, Hindi name, Category, Beneficiary, Eligibility, Benefits, Documents, State/District, Status
                </p>
              </div>
              <div style={{ display: "flex", gap: "10px", alignItems: "center" }}>
                <button
                  type="button"
                  className="btn-primary"
                  style={{ fontSize: "0.82rem", padding: "6px 14px", background: "var(--emerald)", border: "none" }}
                  onClick={() => setShowExtractModal(true)}
                >
                  ➕ Extract from Document
                </button>
                <button className="close-btn" onClick={() => setShowStructuredModal(false)}>✕</button>
              </div>
            </div>

            <div style={{ padding: "16px 24px", overflowY: "auto", flex: 1 }}>
              {/* Controls */}
              <div style={{ display: "flex", gap: "12px", marginBottom: "16px", flexWrap: "wrap", alignItems: "center" }}>
                <input
                  type="text"
                  placeholder="🔍 Search scheme name, Hindi name (उदा. किसान, KCC, कुसुम, scholarship), eligibility, benefits..."
                  value={structuredSearch}
                  onChange={(e) => setStructuredSearch(e.target.value)}
                  style={{
                    flex: "1 1 300px",
                    padding: "10px 14px",
                    borderRadius: "var(--radius-md)",
                    border: "1px solid var(--panel-border)",
                    background: "var(--bg-secondary)",
                    color: "var(--text-main)",
                    fontSize: "0.9rem",
                  }}
                />
                <select
                  value={structuredCatFilter}
                  onChange={(e) => setStructuredCatFilter(e.target.value)}
                  style={{
                    padding: "10px 14px",
                    borderRadius: "var(--radius-md)",
                    border: "1px solid var(--panel-border)",
                    background: "var(--bg-secondary)",
                    color: "var(--text-main)",
                    fontSize: "0.88rem",
                  }}
                >
                  <option value="all">All Categories</option>
                  <option value="Agriculture">🌾 Agriculture & Farmers</option>
                  <option value="Women">👩 Women & Child Development</option>
                  <option value="Credit">💳 Credit & Finance</option>
                  <option value="Insurance">🛡️ Crop Insurance</option>
                  <option value="Irrigation">💧 Irrigation & Energy</option>
                  <option value="Education">🎓 Education & Scholarships</option>
                  <option value="Health">🏥 Health & Medical</option>
                  <option value="Nutrition">🥗 Nutrition & Poshan</option>
                  <option value="Housing">🏠 Housing</option>
                </select>
                <span style={{ fontSize: "0.85rem", color: "var(--text-dim)", fontWeight: 600 }}>
                  {structuredSchemes.length} Total Schemes Seeded
                </span>
              </div>

              {/* Grid of 9-field Scheme Cards */}
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(360px, 1fr))", gap: "16px" }}>
                {structuredSchemes
                  .filter((s) => {
                    const matchesSearch =
                      !structuredSearch ||
                      s.scheme_name.toLowerCase().includes(structuredSearch.toLowerCase()) ||
                      s.hindi_name.toLowerCase().includes(structuredSearch.toLowerCase()) ||
                      s.eligibility.toLowerCase().includes(structuredSearch.toLowerCase()) ||
                      s.benefits.toLowerCase().includes(structuredSearch.toLowerCase()) ||
                      s.state_district.toLowerCase().includes(structuredSearch.toLowerCase());
                    const matchesCat =
                      structuredCatFilter === "all" ||
                      (structuredCatFilter === "Women"
                        ? (s.category.toLowerCase().includes("women") ||
                           s.category.toLowerCase().includes("child") ||
                           s.category.toLowerCase().includes("girl") ||
                           s.category.toLowerCase().includes("maternity") ||
                           s.category.toLowerCase().includes("shg") ||
                           s.category.toLowerCase().includes("shelter"))
                        : s.category.toLowerCase().includes(structuredCatFilter.toLowerCase()));
                    return matchesSearch && matchesCat;
                  })
                  .map((s) => (
                    <div
                      key={s.scheme_id || s.id}
                      style={{
                        background: "var(--bg-card)",
                        border: "1px solid var(--panel-border)",
                        borderRadius: "var(--radius-lg)",
                        padding: "16px",
                        display: "flex",
                        flexDirection: "column",
                        gap: "10px",
                        boxShadow: "var(--shadow-sm)",
                      }}
                    >
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: "8px" }}>
                        <div>
                          <h4 style={{ margin: 0, fontSize: "1.05rem", color: "var(--text-main)" }}>
                            {s.hindi_name}
                          </h4>
                          <span style={{ fontSize: "0.82rem", color: "var(--text-muted)" }}>
                            {s.scheme_name}
                          </span>
                        </div>
                        <span style={{
                          background: "var(--emerald-bg)",
                          color: "var(--emerald-text)",
                          border: "1px solid var(--emerald-border)",
                          padding: "2px 8px",
                          borderRadius: "10px",
                          fontSize: "0.72rem",
                          fontWeight: 700,
                          whiteSpace: "nowrap"
                        }}>
                          ● {s.status}
                        </span>
                      </div>

                      <div style={{ display: "flex", gap: "6px", flexWrap: "wrap" }}>
                        <span style={{ background: "var(--bg-secondary)", color: "var(--text-dim)", padding: "2px 8px", borderRadius: "6px", fontSize: "0.72rem" }}>
                          🏷️ {s.category}
                        </span>
                        <span style={{ background: "var(--bg-secondary)", color: "var(--accent)", padding: "2px 8px", borderRadius: "6px", fontSize: "0.72rem", fontWeight: 600 }}>
                          📍 {s.state_district}
                        </span>
                      </div>

                      <div style={{ fontSize: "0.82rem", lineHeight: "1.4", color: "var(--text-main)", background: "var(--bg-secondary)", padding: "8px 10px", borderRadius: "var(--radius-sm)" }}>
                        <strong>👥 लाभार्थी:</strong> {s.beneficiary}
                      </div>

                      <div style={{ fontSize: "0.82rem", lineHeight: "1.4", color: "var(--text-main)" }}>
                        <strong>🎯 पात्रता (Eligibility):</strong>
                        <p style={{ margin: "2px 0 0", color: "var(--text-muted)" }}>{s.eligibility}</p>
                      </div>

                      <div style={{ fontSize: "0.82rem", lineHeight: "1.4", color: "var(--text-main)" }}>
                        <strong>💰 लाभ (Benefits):</strong>
                        <p style={{ margin: "2px 0 0", color: "var(--text-muted)" }}>{s.benefits}</p>
                      </div>

                      <div style={{ fontSize: "0.82rem", lineHeight: "1.4", color: "var(--text-main)" }}>
                        <strong>📄 दस्तावेज़ (Documents):</strong>
                        <div style={{ margin: "2px 0 0", color: "var(--text-muted)", whiteSpace: "pre-line" }}>{s.documents}</div>
                      </div>

                      <div style={{ marginTop: "auto", paddingTop: "10px", borderTop: "1px solid var(--panel-border)", display: "flex", justifyContent: "space-between", alignItems: "center", gap: "8px" }}>
                        {s.official_source_url ? (
                          <a href={s.official_source_url} target="_blank" rel="noreferrer" style={{ fontSize: "0.76rem", color: "var(--accent)", textDecoration: "none", fontWeight: 600 }}>
                            🌐 Official Portal ↗
                          </a>
                        ) : <span />}

                        <button
                          type="button"
                          onClick={() => {
                            const q = `${s.hindi_name} (${s.scheme_name}) के लिए क्या पात्रता, लाभ और दस्तावेज़ हैं?`;
                            setQuestion(q);
                            setSelectedLang("hi");
                            setShowStructuredModal(false);
                            ask(null, q);
                          }}
                          style={{
                            padding: "6px 12px",
                            background: "var(--accent)",
                            color: "#ffffff",
                            border: "none",
                            borderRadius: "var(--radius-sm)",
                            fontSize: "0.78rem",
                            fontWeight: 600,
                            cursor: "pointer",
                          }}
                        >
                          Research in Hindi 🔍
                        </button>
                      </div>
                    </div>
                  ))}
              </div>
            </div>

            <div style={{ padding: "12px 24px", borderTop: "1px solid var(--panel-border)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <span style={{ fontSize: "0.82rem", color: "var(--text-muted)" }}>
                Database synced with Official Central & State Government Ministries.
              </span>
              <button className="btn-primary" onClick={() => setShowStructuredModal(false)}>
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Extract & Ingest Scheme Modal */}
      {showExtractModal && (
        <div className="modal-overlay" onClick={() => setShowExtractModal(false)}>
          <div
            className="modal-card"
            style={{ maxWidth: "680px", width: "90vw" }}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="modal-header">
              <div>
                <h3 style={{ margin: 0 }}>➕ Extract & Ingest Structured Scheme</h3>
                <p style={{ margin: "4px 0 0 0", fontSize: "0.82rem", color: "var(--text-muted)" }}>
                  Paste official PDF text, GR, or notification in Hindi or English to automatically clean, normalize, and store into PostgreSQL/database.
                </p>
              </div>
              <button className="close-btn" onClick={() => setShowExtractModal(false)}>✕</button>
            </div>

            <form onSubmit={handleExtractScheme} style={{ padding: "20px 24px" }}>
              <div style={{ marginBottom: "14px" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "6px" }}>
                  <label style={{ fontSize: "0.85rem", fontWeight: 600 }}>
                    Document / Notification Text (Hindi / English):
                  </label>
                  <button
                    type="button"
                    className={`voice-mic-btn ${isListening && listeningTarget === "extract" ? "listening" : ""}`}
                    style={{ padding: "4px 12px", fontSize: "0.78rem" }}
                    onClick={() => (isListening && listeningTarget === "extract" ? stopVoiceInput() : startVoiceInput("extract"))}
                    title="Dictate document notification text using microphone"
                  >
                    <span>{isListening && listeningTarget === "extract" ? "⏹️ Stop Dictation" : "🎙️ Dictate Text (बोलून लिहा)"}</span>
                  </button>
                </div>
                <textarea
                  rows={8}
                  style={{
                    width: "100%",
                    padding: "10px 12px",
                    borderRadius: "var(--radius-md)",
                    border: "1px solid var(--panel-border)",
                    background: "var(--bg-secondary)",
                    color: "var(--text-main)",
                    fontSize: "0.88rem",
                    fontFamily: "var(--font-mono)",
                  }}
                  placeholder="Paste official notification text here (e.g. Scheme Name, Eligibility, Benefits, Documents Required, State)..."
                  value={extractText}
                  onChange={(e) => setExtractText(e.target.value)}
                  required
                />
              </div>

              <div style={{ display: "flex", justifyContent: "flex-end", gap: "10px" }}>
                <button type="button" className="btn-secondary" onClick={() => setShowExtractModal(false)}>
                  Cancel
                </button>
                <button type="submit" className="btn-primary" disabled={extracting || !extractText.trim()}>
                  {extracting ? "Extracting & Normalizing..." : "Extract & Save Scheme"}
                </button>
              </div>

              {extractStatus && (
                <div style={{
                  marginTop: "14px",
                  padding: "10px 14px",
                  borderRadius: "var(--radius-md)",
                  fontSize: "0.85rem",
                  background: extractStatus.startsWith("✅") ? "var(--emerald-bg)" : "var(--rose-bg)",
                  color: extractStatus.startsWith("✅") ? "var(--emerald-text)" : "var(--rose-text)",
                  border: `1px solid ${extractStatus.startsWith("✅") ? "var(--emerald-border)" : "var(--rose-border)"}`,
                }}>
                  {extractStatus}
                </div>
              )}
            </form>
          </div>
        </div>
      )}

      {/* Official Documents Hub & Document Voice Reader Modal */}
      {showDocsModal && (
        <div className="modal-overlay" onClick={() => { closeDocumentReader(); setShowDocsModal(false); }}>
          <div
            className="modal-card"
            style={{ maxWidth: "1150px", width: "95vw", maxHeight: "92vh", display: "flex", flexDirection: "column" }}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="modal-header">
              <div>
                <h3 style={{ margin: 0, display: "flex", alignItems: "center", gap: "8px" }}>
                  <span>📑</span> Official Government Documents &amp; Guidelines (अधिकृत दस्तऐवज)
                </h3>
                <p style={{ margin: "4px 0 0 0", fontSize: "0.82rem", color: "var(--text-muted)" }}>
                  Verified Gazettes, Policy Circulars, Compendiums &amp; Guidelines • Indexed for Grounded RAG with Voice Read Aloud
                </p>
              </div>
              <button className="close-btn" onClick={() => { closeDocumentReader(); setShowDocsModal(false); }}>✕</button>
            </div>

            <div style={{ padding: "16px 24px", overflowY: "auto", flex: 1 }}>
              {selectedDoc ? (
                /* Document Full Reader View with Audio Toolbar */
                <div className="doc-reader-container">
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "14px", flexWrap: "wrap", gap: "10px" }}>
                    <button
                      type="button"
                      className="btn-secondary"
                      onClick={closeDocumentReader}
                      style={{ fontSize: "0.82rem", padding: "6px 14px", display: "inline-flex", alignItems: "center", gap: "6px" }}
                    >
                      ← Back to All Documents
                    </button>

                    {/* Audio Player Toolbar for this Document */}
                    <div className="audio-player-toolbar">
                      {ttsPlaying && ttsSource === `doc-${selectedDoc.id}` ? (
                        <>
                          {ttsPaused ? (
                            <button type="button" className="audio-btn active" onClick={resumeTts} title="Resume voice readout">
                              ▶️ Resume
                            </button>
                          ) : (
                            <button type="button" className="audio-btn active" onClick={pauseTts} title="Pause voice readout">
                              ⏸️ Pause
                            </button>
                          )}
                          <button type="button" className="audio-btn danger" onClick={stopTts} title="Stop voice readout">
                            ⏹️ Stop
                          </button>
                          <div className="audio-waveform-bars" title="Voice audio playing">
                            <span className="audio-wave-bar" />
                            <span className="audio-wave-bar" />
                            <span className="audio-wave-bar" />
                            <span className="audio-wave-bar" />
                            <span className="audio-wave-bar" />
                          </div>
                          <span style={{ fontSize: "0.75rem", color: "var(--accent)", fontWeight: 700 }}>
                            Paragraph {ttsCurrentChunk}/{ttsTotalChunks}
                          </span>
                        </>
                      ) : (
                        <button
                          type="button"
                          className="audio-btn"
                          onClick={() => playTts(selectedDocText, `doc-${selectedDoc.id}`, selectedLang === "mr" ? "mr" : selectedLang === "hi" ? "hi" : "en")}
                          disabled={docTextLoading || !selectedDocText}
                          title="Listen to this entire official document read aloud"
                        >
                          🔊 Read Full Document Aloud (संपूर्ण दस्तऐवज ऐका)
                        </button>
                      )}

                      <div className="speed-selector-group" title="Adjust speech playback speed">
                        {[0.8, 1.0, 1.25, 1.5].map((rate) => (
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

                  <div className="doc-reader-meta-bar">
                    <div>
                      <h4 style={{ margin: "0 0 4px", fontSize: "1.1rem", color: "var(--text-main)" }}>
                        {selectedDoc.title}
                      </h4>
                      <div style={{ display: "flex", gap: "8px", flexWrap: "wrap", fontSize: "0.8rem", color: "var(--text-muted)" }}>
                        <span>🏛️ <strong>Authority:</strong> {selectedDoc.authority}</span>
                        <span>📑 <strong>Type:</strong> {selectedDoc.document_type || "Official Guidelines"}</span>
                        {selectedDoc.publication_date && <span>📅 <strong>Date:</strong> {selectedDoc.publication_date}</span>}
                        {selectedDoc.updated_date && <span>🛡️ <strong>Updated:</strong> {selectedDoc.updated_date}</span>}
                      </div>
                    </div>
                    {selectedDoc.source_url && (
                      <a
                        href={selectedDoc.source_url}
                        target="_blank"
                        rel="noreferrer"
                        style={{ fontSize: "0.82rem", color: "var(--accent)", fontWeight: 700, textDecoration: "none" }}
                      >
                        🌐 Official Portal ↗
                      </a>
                    )}
                  </div>

                  {docTextLoading ? (
                    <div style={{ padding: "40px", textAlign: "center", color: "var(--text-muted)" }}>
                      <span className="spinner" style={{ borderColor: "rgba(2, 132, 199, 0.3)", borderTopColor: "var(--accent)", width: "24px", height: "24px", margin: "0 auto 12px", display: "block" }} />
                      Loading official document contents...
                    </div>
                  ) : (
                    <div className="doc-content-viewer">
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "14px", borderBottom: "1px solid var(--panel-border)", paddingBottom: "8px" }}>
                        <span style={{ fontSize: "0.8rem", color: "var(--text-dim)", fontWeight: 600 }}>
                          💡 Tip: Click any paragraph to listen to it read aloud.
                        </span>
                        <button
                          type="button"
                          className="btn-secondary"
                          style={{ padding: "3px 10px", fontSize: "0.75rem" }}
                          onClick={() => {
                            navigator.clipboard.writeText(selectedDocText);
                            alert("Document text copied to clipboard!");
                          }}
                        >
                          📋 Copy Text
                        </button>
                      </div>

                      {selectedDocText.split("\n\n").map((para, pIdx) => {
                        const trimmed = para.trim();
                        if (!trimmed) return null;
                        const isSpeakingThis = ttsPlaying && ttsSource === `doc-${selectedDoc.id}` && ttsCurrentChunk === pIdx + 1;
                        return (
                          <div
                            key={pIdx}
                            className={`doc-paragraph-item ${isSpeakingThis ? "currently-speaking" : ""}`}
                            onClick={() => playTts(trimmed, `doc-${selectedDoc.id}`, selectedLang === "mr" ? "mr" : selectedLang === "hi" ? "hi" : "en")}
                            title="Click to listen to this paragraph"
                          >
                            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: "8px" }}>
                              <p style={{ margin: 0, flex: 1, whiteSpace: "pre-wrap" }}>{trimmed}</p>
                              <button
                                type="button"
                                className={`btn-listen-mini ${isSpeakingThis ? "playing" : ""}`}
                                onClick={(e) => {
                                  e.stopPropagation();
                                  playTts(trimmed, `doc-${selectedDoc.id}`, selectedLang === "mr" ? "mr" : selectedLang === "hi" ? "hi" : "en");
                                }}
                                style={{ flexShrink: 0 }}
                              >
                                {isSpeakingThis ? "⏹️" : "🔊"}
                              </button>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              ) : (
                /* Documents List View */
                <div>
                  {/* Search & Filter Bar */}
                  <div style={{ display: "flex", gap: "10px", marginBottom: "16px", flexWrap: "wrap", alignItems: "center" }}>
                    <div style={{ display: "flex", flex: "1 1 320px", gap: "6px" }}>
                      <input
                        type="text"
                        placeholder="🔍 Search official documents (e.g. scholarship, KCC, pest, fertilizer, PM-KISAN)..."
                        value={docSearch}
                        onChange={(e) => setDocSearch(e.target.value)}
                        style={{
                          flex: 1,
                          padding: "9px 14px",
                          borderRadius: "var(--radius-md)",
                          border: "1px solid var(--panel-border)",
                          background: "var(--input-bg)",
                          color: "var(--text-main)",
                          fontSize: "0.88rem",
                        }}
                      />
                      <button
                        type="button"
                        className={`voice-mic-btn ${isListening && listeningTarget === "docSearch" ? "listening" : ""}`}
                        onClick={() => (isListening && listeningTarget === "docSearch" ? stopVoiceInput() : startVoiceInput("docSearch"))}
                        title="Speak to search documents"
                        style={{ padding: "8px 12px" }}
                      >
                        <span>{isListening && listeningTarget === "docSearch" ? "⏹️ Stop" : "🎙️ Speak"}</span>
                      </button>
                    </div>

                    <select
                      value={docCatFilter}
                      onChange={(e) => setDocCatFilter(e.target.value)}
                      style={{
                        padding: "9px 12px",
                        borderRadius: "var(--radius-md)",
                        border: "1px solid var(--panel-border)",
                        background: "var(--bg-secondary)",
                        color: "var(--text-main)",
                        fontSize: "0.84rem",
                      }}
                    >
                      <option value="all">All Documents ({docsList.length})</option>
                      <option value="agriculture">🌾 Agriculture & Farming</option>
                      <option value="pest">🐛 Pest & Plant Protection</option>
                      <option value="fertilizer">🧪 Fertilizer & Soil Health</option>
                      <option value="education">🎓 Education & Scholarships</option>
                      <option value="women">👩 Women & Child Schemes</option>
                    </select>

                    <button
                      type="button"
                      className="btn-secondary"
                      onClick={fetchDocuments}
                      title="Reload document list"
                      style={{ padding: "8px 12px", fontSize: "0.82rem" }}
                    >
                      🔄 Refresh
                    </button>
                  </div>

                  {docsLoading ? (
                    <div style={{ padding: "30px", textAlign: "center", color: "var(--text-muted)" }}>
                      Loading documents repository...
                    </div>
                  ) : (
                    <div style={{ border: "1px solid var(--panel-border)", borderRadius: "var(--radius-md)", overflowX: "auto" }}>
                      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.84rem", textAlign: "left" }}>
                        <thead>
                          <tr style={{ background: "var(--bg-secondary)", borderBottom: "1px solid var(--panel-border)" }}>
                            <th style={{ padding: "10px 12px", color: "var(--text-muted)", fontWeight: 600 }}>ID</th>
                            <th style={{ padding: "10px 12px", color: "var(--text-muted)", fontWeight: 600 }}>Document Title</th>
                            <th style={{ padding: "10px 12px", color: "var(--text-muted)", fontWeight: 600 }}>Authority / Ministry</th>
                            <th style={{ padding: "10px 12px", color: "var(--text-muted)", fontWeight: 600 }}>Type / Date</th>
                            <th style={{ padding: "10px 12px", color: "var(--text-muted)", fontWeight: 600, textAlign: "center" }}>Indexed</th>
                            <th style={{ padding: "10px 12px", color: "var(--text-muted)", fontWeight: 600, textAlign: "center" }}>Action</th>
                          </tr>
                        </thead>
                        <tbody>
                          {docsList
                            .filter((doc) => {
                              const q = docSearch.toLowerCase().trim();
                              const matchesSearch = !q ||
                                doc.title.toLowerCase().includes(q) ||
                                (doc.authority && doc.authority.toLowerCase().includes(q)) ||
                                (doc.document_type && doc.document_type.toLowerCase().includes(q));
                              const cat = docCatFilter.toLowerCase();
                              const matchesCat = cat === "all" ||
                                (cat === "pest" && (doc.title.toLowerCase().includes("pest") || doc.title.toLowerCase().includes("cibrc"))) ||
                                (cat === "fertilizer" && (doc.title.toLowerCase().includes("fertilizer") || doc.title.toLowerCase().includes("soil"))) ||
                                (cat === "education" && (doc.title.toLowerCase().includes("scholarship") || doc.title.toLowerCase().includes("matric"))) ||
                                (cat === "women" && (doc.title.toLowerCase().includes("women") || doc.title.toLowerCase().includes("child"))) ||
                                (cat === "agriculture" && (doc.title.toLowerCase().includes("agriculture") || doc.title.toLowerCase().includes("crop") || doc.title.toLowerCase().includes("farmer") || doc.title.toLowerCase().includes("kisan")));
                              return matchesSearch && matchesCat;
                            })
                            .map((doc) => (
                              <tr
                                key={doc.id}
                                style={{
                                  borderBottom: "1px solid var(--panel-border)",
                                  transition: "background 0.15s ease",
                                }}
                              >
                                <td style={{ padding: "10px 12px", color: "var(--text-dim)", fontFamily: "var(--font-mono)" }}>
                                  #{doc.id}
                                </td>
                                <td style={{ padding: "10px 12px", fontWeight: 600, color: "var(--text-main)", maxWidth: "340px" }}>
                                  {doc.title}
                                </td>
                                <td style={{ padding: "10px 12px", color: "var(--text-muted)", fontSize: "0.82rem" }}>
                                  {doc.authority || "Government Authority"}
                                </td>
                                <td style={{ padding: "10px 12px", fontSize: "0.78rem", color: "var(--text-dim)" }}>
                                  <span style={{ background: "var(--bg-secondary)", padding: "2px 6px", borderRadius: "4px", border: "1px solid var(--panel-border)", marginRight: "6px" }}>
                                    {doc.document_type || "TXT"}
                                  </span>
                                  {doc.publication_date || doc.updated_date || "Official"}
                                </td>
                                <td style={{ padding: "10px 12px", textAlign: "center" }}>
                                  <span style={{
                                    padding: "2px 8px",
                                    borderRadius: "10px",
                                    fontSize: "0.74rem",
                                    fontWeight: 700,
                                    background: doc.indexed ? "var(--emerald-bg)" : "var(--amber-bg)",
                                    color: doc.indexed ? "var(--emerald-text)" : "var(--amber-text)",
                                    border: `1px solid ${doc.indexed ? "var(--emerald-border)" : "var(--amber-border)"}`
                                  }}>
                                    {doc.indexed ? "● Indexed" : "Pending"}
                                  </span>
                                </td>
                                <td style={{ padding: "10px 12px", textAlign: "center" }}>
                                  <button
                                    type="button"
                                    onClick={() => openDocumentDetails(doc)}
                                    style={{
                                      padding: "5px 12px",
                                      background: "linear-gradient(135deg, #0284c7, #0d9488)",
                                      color: "#ffffff",
                                      border: "none",
                                      borderRadius: "6px",
                                      fontSize: "0.78rem",
                                      fontWeight: 600,
                                      cursor: "pointer",
                                      display: "inline-flex",
                                      alignItems: "center",
                                      gap: "5px",
                                    }}
                                  >
                                    <span>📖 Read &amp; Listen 🔊</span>
                                  </button>
                                </td>
                              </tr>
                            ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              )}
            </div>

            <div style={{ padding: "12px 24px", borderTop: "1px solid var(--panel-border)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <span style={{ fontSize: "0.82rem", color: "var(--text-muted)" }}>
                {docsList.length} Official Grounded Documents Indexed in ChromaDB &amp; SQLite.
              </span>
              <button className="btn-primary" onClick={() => { closeDocumentReader(); setShowDocsModal(false); }}>
                Close Hub
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
