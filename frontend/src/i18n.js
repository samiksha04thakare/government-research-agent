/**
 * Multilingual UI Translations and Localized Domain Categories for GovResearch AI.
 * Supports: English ('en'), Hindi ('hi'), Marathi ('mr').
 */

export const SUPPORTED_LANGUAGES = [
  { code: "en", label: "🇬🇧 English" },
  { code: "hi", label: "🇮🇳 हिन्दी (Hindi)" },
  { code: "mr", label: "🚩 मराठी (Marathi)" },
];

export const UI_TRANSLATIONS = {
  en: {
    // Top Navbar
    portalTitle: "GovResearch AI",
    portalSubtitle: "Source-Grounded Government Research Agent",
    apiOnline: "API Online",
    activeSchemesBadge: "104 Active Schemes",
    apiKeyActive: "Active",
    apiKeyNotSet: "API Key Not Set",
    themeDark: "🌙 Dark",
    themeLight: "☀️ Light",
    navStructuredSchemes: "Structured Schemes",
    navBdsBudget: "Maharashtra BDS Budget",
    navOfficialDocs: "Official Documents",

    // Dashboard Navigation
    navDashboard: "Dashboard",
    navAskAi: "Ask AI",
    navSchemes: "Schemes",
    navDocuments: "Documents",
    navHistory: "History",
    navSettings: "Settings",

    // Dashboard Home View
    dashGreeting: "Welcome!",
    dashGreetingNamaste: "Namaste!",
    dashSubtitle: "Your AI Research Agent for government schemes and official information.",
    dashSearchPlaceholder: "Ask your question... (e.g. What is PM-KISAN?)",
    dashSearchBtn: "Search",
    categoryFarmer: "Farmer Schemes",
    categoryFarmerDesc: "PM-KISAN, KCC, Crop Insurance, Farm Implements etc.",
    categoryScholarship: "Scholarships",
    categoryScholarshipDesc: "Education Scholarships, Higher Studies, Skill Development etc.",
    categoryEntrepreneurship: "Entrepreneurship",
    categoryEntrepreneurshipDesc: "MUDRA Loan, Stand-Up India, PMEGP, Startup Support etc.",
    categoryWomen: "Women Welfare",
    categoryWomenDesc: "Ujjwala Yojana, Maternity Benefits, Self-Employment, Safety etc.",
    categoryOther: "Other Schemes",
    categoryOtherDesc: "Health, Pension, Housing, Employment, Social Welfare etc.",
    govSchemesHeading: "Government Schemes",
    govSchemesSubtitle: "Find information about various government schemes and benefits",
    statTotalSchemesCount: "1,250+",
    statTotalSchemesLabel: "Government Schemes",
    statTotalDocsCount: "5,680+",
    statTotalDocsLabel: "Indexed Documents",
    statAiAssistCount: "24/7",
    statAiAssistLabel: "AI Assistance Available",
    statSourcesUpdateCount: "Sources Updated",
    statSourcesUpdateLabel: "Last checked: 10 Oct 2026",
    uploadSchemeCategoryFilter: "Filter Uploads by Scheme Category",
    uploadSchemeCategorySub: "Browse official guidance and schemes photos by category",
    schemesCountLabel: "Schemes",
    statIndexedDocs: "Indexed Documents",
    statChunks: "Evidence Chunks",
    statAiAssistant: "24/7 AI Assistant",
    statSourcesUpdated: "Sources Updated",
    statLastChecked: "Last checked: 10 Oct 2026",
    popularSchemes: "Popular Schemes",
    viewAllSchemes: "All Schemes →",

    // Ask AI Screen
    askAiHeaderTitle: "Ask AI",
    askAiHeaderSubtitle: "Ask questions about government schemes and get verified official answers.",
    selectLanguageLabel: "Select Language",
    suggestedQuestionsTitle: "Suggested Questions",
    didYouKnowTitle: "Did you know?",
    didYouKnowText: "You can ask questions in your preferred language. We answer in Hindi, English, and Marathi with direct official government citations.",
    quickActionsTitle: "Quick follow-up questions:",
    quickActionApply: "What is the application process?",
    quickActionEligibility: "What are the eligibility criteria?",
    quickActionStatus: "How to check installment status?",
    chatPlaceholder: "Ask your question...",
    backToDashboard: "← Dashboard",

    // Schemes Directory Screen
    schemesTitle: "Government Schemes",
    schemesSubtitle: "Search government schemes and get comprehensive official details",
    searchSchemePlaceholder: "Search by scheme name...",
    filterAll: "All",
    filterFarmer: "Farmer",
    filterScholarship: "Scholarship",
    filterEntrepreneurship: "Entrepreneurship",
    filterWomen: "Women",
    filterOther: "Other",
    viewDetailsLink: "View Details →",
    backToSchemes: "← Government Schemes",

    // Scheme Details Screen
    tabOverview: "Overview",
    tabEligibility: "Eligibility",
    tabBenefits: "Benefits",
    tabDocuments: "Required Documents",
    tabProcess: "Application Process",
    schemeDescTitle: "Scheme Description",
    keyBenefitsTitle: "Key Benefits",
    reqDocsTitle: "Required Documents",
    visitOfficialPortalBtn: "Visit Official Website ↗",
    askAiAboutThisSchemeBtn: "💬 Ask AI about this scheme",

    // Documents Screen
    docsMainTitle: "Documents",
    docsMainSubtitle: "Upload, manage and search official government records",
    tabMyDocs: "My Documents",
    tabIndexingStatus: "Indexing Status",
    tabSourcesRegistry: "Sources",
    uploadCardTitle: "Upload Documents",
    uploadCardSub: "Supported formats: PDF, DOC, DOCX, PNG, JPG (Max 20MB)",
    chooseFileBtn: "Choose File",
    recentUploadsTitle: "Recent Uploads",
    statusIndexed: "Indexed",
    statusPending: "Pending",
    readDocAction: "Read Text",

    // Settings Screen
    settingsMainTitle: "Settings",
    settingsMainSubtitle: "Customize your research experience and preferences",
    langPrefTitle: "Display Language",
    aiModelPrefTitle: "AI Model",
    apiKeysPrefTitle: "API Keys",
    themePrefTitle: "Theme",
    themeLightBtn: "☀️ Light",
    themeDarkBtn: "🌙 Dark",
    autoSearchPrefTitle: "Auto-search after speaking",
    showSourcesPrefTitle: "Show verified evidence citations",
    resetHistoryBtn: "Clear Research History",

    // History Sidebar
    recentQueries: "Recent Queries",
    clearAllHistory: "🗑️ Clear All",
    clearingHistory: "Clearing...",
    noHistoryYet: "No recent queries yet. Click an example question or ask above.",
    historyQuestion: "Query",
    historyLanguage: "Lang",
    groundedRagTitle: "Grounded RAG Guarantee",
    groundedRagDesc: "Every response is cross-checked against indexed official gazettes, guidelines, and ministry portals.",

    // Hero Banner
    heroTag: "GOVERNMENT SCHEME & POLICY RESEARCH INTELLIGENCE",
    heroTitle: "Government Scheme Research Agent",
    heroDescription:
      "Verified answers for government schemes, farmer welfare, welfare policies, eligibility criteria, and benefits. Every response is strictly verified with direct citations and hallucination checks against official guidelines.",

    // Language Selector Bar
    responseLanguageLabel: "Response Language / भाषा निवडा / भाषा चुनें:",

    // Search Card & Voice
    voiceSearchBtn: "🎙️ Voice Search",
    stopListeningBtn: "⏹️ Stop Listening",
    listeningPrefix: "🎙️ Listening",
    listeningPlaceholder: "Speak clearly into microphone...",
    speakInLanguage: "Speak query in",
    autoSearchLabel: "⚡ Auto-search after speech",
    searchPlaceholder:
      "Ask about farmer credit, crop diseases, pest outbreaks, fertilizer dosage, or government schemes (e.g., How to apply for KCC or prevent wheat yellowing?)...",
    searchTip: "Tip: Press Ctrl + Enter or click 🎙️ to speak in Hindi/Marathi/English",
    clearSearchBtn: "Clear Search",
    researchSchemesBtn: "Research Schemes",
    researchingEvidenceBtn: "Researching Evidence...",

    // Alerts
    researchErrorTitle: "Research Error",
    configureApiKeyBtn: "Configure API Key",
    insufficientEvidenceTitle: "Insufficient Official Evidence",
    insufficientEvidenceDesc:
      "The indexed official records do not contain enough verified evidence to answer this question with certainty.",

    // Structured Scheme Box
    activeStatus: "Active",
    eligibilityLabel: "🎯 Eligibility Criteria",
    beneficiaryLabel: "👥 Beneficiary Category",
    benefitsLabel: "💰 Financial Benefits & Assistance",
    documentsLabel: "📄 Documents Required",
    nodalDeptLabel: "🏛️ Nodal Authority:",
    officialPortalLink: "🔗 Official Portal ↗",

    // Answer Card
    verifiedSynthesisBadge: "Verified Synthesis",
    officialFindingsTitle: "Official Research Findings",
    readFindingsAloudBtn: "🔊 Read Findings Aloud",
    pauseVoiceBtn: "⏸️ Pause",
    resumeVoiceBtn: "▶️ Resume",
    stopVoiceBtn: "⏹️ Stop",
    voiceSectionLabel: "Section",
    recordTagPrefix: "Record #",

    // Clarifying Questions & Next Steps
    clarifyingTitle: "Clarifying Follow-Up Question:",
    refineQueryBtn: "✍️ Refine Query",
    practicalStepsTitle: "Practical Farmer Next Steps",
    practicalStepsSub: "Actionable steps supported strictly by official records",
    scopeWarningTitle: "Official Evidence Scope Warning",
    sourceDiscrepancyTitle: "Source Discrepancies Detected",
    sourceDiscrepancyDesc: "The verified documents contain conflicting terms or numbers on this topic:",

    // Citations & Sources
    officialSourcesTitle: "Official Referenced Sources",
    verifiedBadgeSuffix: "Verified",
    listenSourceBtn: "🔊 Listen",
    stopListenMiniBtn: "⏹️ Stop",
    sourceUnavailable: "⚠️ Source URL unavailable on official portal",
    officialDateLabel: "Official Date:",
    checkedDateLabel: "Checked:",
    pageLabel: "Page",
    officialFreshnessNotice:
      "Information is directly grounded in official government records. Verified Check Date reflects when our system checked the source; Official Date reflects the publication date declared by the issuing department. Please verify details on the official government portal before making administrative or financial decisions.",

    // Retrieved Chunks
    retrievedChunksTitle: "🔍 Retrieved Evidence Chunks & Similarity Scores",
    similarityScoreLabel: "Similarity Score:",
    deptLabel: "Dept:",
    yearLabel: "Year:",
    typeLabel: "Type:",

    // Modals
    modalClose: "✕",
    apiKeyModalTitle: "AI Provider Configuration",
    apiKeyModalDesc: "The research agent can run on either Groq (Free & Ultra-Fast) or Anthropic Claude.",
    saveApiKeyBtn: "Activate API Key",
    bdsModalTitle: "Maharashtra Agriculture Schemes (BDS 2026-27)",
    searchSchemesPlaceholder: "Search by scheme name, code (e.g. 1101100034), or keywords...",
    structuredModalTitle: "Official Structured Schemes Directory",
    docsModalTitle: "Official Documents & Compendiums Hub",
    searchDocsPlaceholder: "Search documents by title, department, or keywords...",
  },

  hi: {
    // Top Navbar
    portalTitle: "शासकीय अनुसंधान AI",
    portalSubtitle: "स्रोत-सत्यापित सरकारी अनुसंधान एवं नीति एजेंट",
    apiOnline: "एपीआई ऑनलाइन",
    activeSchemesBadge: "104 सक्रिय योजनाएं",
    apiKeyActive: "सक्रिय",
    apiKeyNotSet: "एपीआई कुंजी सेट नहीं है",
    themeDark: "🌙 डार्क",
    themeLight: "☀️ लाइट",
    navStructuredSchemes: "संरचित योजनाएं",
    navBdsBudget: "महाराष्ट्र बजट (BDS)",
    navOfficialDocs: "आधिकारिक दस्तावेज",

    // Dashboard Navigation
    navDashboard: "डैशबोर्ड",
    navAskAi: "Ask AI",
    navSchemes: "योजनाएं",
    navDocuments: "दस्तावेज़",
    navHistory: "इतिहास",
    navSettings: "सेटिंग्स",

    // Dashboard Home View
    dashGreeting: "नमस्ते!",
    dashGreetingNamaste: "नमस्ते!",
    dashSubtitle: "सरकारी योजनाओं और आधिकारिक जानकारी के लिए आपका AI रिसर्च एजेंट यहाँ है।",
    dashSearchPlaceholder: "अपना सवाल लिखें... (जैसे - PM-KISAN क्या है?)",
    dashSearchBtn: "खोजें",
    categoryFarmer: "किसान योजनाएँ",
    categoryFarmerDesc: "PM-KISAN, KCC, फसल बीमा, कृषि उपकरण आदि",
    categoryScholarship: "छात्रवृत्ति",
    categoryScholarshipDesc: "शिक्षा छात्रवृत्ति, स्कॉलरशिप, कौशल विकास आदि",
    categoryEntrepreneurship: "उद्यमिता",
    categoryEntrepreneurshipDesc: "मुद्रा लोन, स्टैंड-अप इंडिया, PMEGP, स्टार्टअप सहायता आदि",
    categoryWomen: "महिला कल्याण",
    categoryWomenDesc: "उज्ज्वला योजना, मातृत्व लाभ, स्वरोजगार, सुरक्षा आदि",
    categoryOther: "अन्य योजनाएँ",
    categoryOtherDesc: "स्वास्थ्य, पेंशन, आवास, रोजगार, परिवहन आदि",
    govSchemesHeading: "Government Schemes",
    govSchemesSubtitle: "सरकारी योजनाओं और लाभों के बारे में जानकारी प्राप्त करें",
    statTotalSchemesCount: "1,250+",
    statTotalSchemesLabel: "सरकारी योजनाएँ",
    statTotalDocsCount: "5,680+",
    statTotalDocsLabel: "दस्तावेज़ इंडेक्स किए गए",
    statAiAssistCount: "24/7",
    statAiAssistLabel: "AI सहायता उपलब्ध",
    statSourcesUpdateCount: "स्रोत अपडेटेड",
    statSourcesUpdateLabel: "अंतिम जाँच: 10 अक्टूबर 2026",
    uploadSchemeCategoryFilter: "योजना श्रेणी अनुसार दस्तावेज़ देखें व अपलोड करें",
    uploadSchemeCategorySub: "श्रेणी अनुसार आधिकारिक दिशानिर्देश और योजना फोटो देखें",
    schemesCountLabel: "योजनाएं",
    statIndexedDocs: "इंडेक्स किए गए दस्तावेज़",
    statChunks: "साक्ष्य खंड (Chunks)",
    statAiAssistant: "24/7 AI सहायक",
    statSourcesUpdated: "स्रोतों का नवीनीकरण",
    statLastChecked: "अंतिम जांच: 10 अक्टूबर 2026",
    popularSchemes: "लोकप्रिय योजनाएं",
    viewAllSchemes: "सभी योजनाएं →",

    // Ask AI Screen
    askAiHeaderTitle: "Ask AI",
    askAiHeaderSubtitle: "सरकारी योजनाओं से जुड़े सवाल पूछें और आधिकारिक जानकारी पाएँ।",
    selectLanguageLabel: "भाषा चुनें",
    suggestedQuestionsTitle: "सुझाए गए सवाल",
    didYouKnowTitle: "क्या आप जानते हैं?",
    didYouKnowText: "आप अपनी भाषा में भी सवाल पूछ सकते हैं। हम हिंदी, अंग्रेजी और मराठी में आधिकारिक साक्ष्यों के साथ जवाब देते हैं।",
    quickActionsTitle: "त्वरित सवाल:",
    quickActionApply: "आवेदन प्रक्रिया क्या है?",
    quickActionEligibility: "पात्रता क्या है?",
    quickActionStatus: "किस्त का स्टेटस कैसे देखें?",
    chatPlaceholder: "अपना सवाल लिखें...",
    backToDashboard: "← डैशबोर्ड",

    // Schemes Directory Screen
    schemesTitle: "Government Schemes",
    schemesSubtitle: "सरकारी योजनाओं की खोज करें और विस्तृत जानकारी प्राप्त करें",
    searchSchemePlaceholder: "योजना का नाम खोजें...",
    filterAll: "सभी",
    filterFarmer: "किसान",
    filterScholarship: "छात्रवृत्ति",
    filterEntrepreneurship: "उद्यमिता",
    filterWomen: "महिला",
    filterOther: "अन्य",
    viewDetailsLink: "विवरण देखें →",
    backToSchemes: "← सभी योजनाएं",

    // Scheme Details Screen
    tabOverview: "परिचय",
    tabEligibility: "पात्रता",
    tabBenefits: "लाभ",
    tabDocuments: "आवश्यक दस्तावेज़",
    tabProcess: "आवेदन प्रक्रिया",
    schemeDescTitle: "योजना का विवरण",
    keyBenefitsTitle: "मुख्य लाभ",
    reqDocsTitle: "आवश्यक दस्तावेज",
    visitOfficialPortalBtn: "आधिकारिक वेबसाइट पर जाएँ ↗",
    askAiAboutThisSchemeBtn: "💬 इस योजना के बारे में AI से पूछें",

    // Documents Screen
    docsMainTitle: "Documents",
    docsMainSubtitle: "अपलोड, प्रबंध और खोजें",
    tabMyDocs: "मेरे दस्तावेज़",
    tabIndexingStatus: "इंडेक्सिंग स्टेटस",
    tabSourcesRegistry: "स्रोत",
    uploadCardTitle: "दस्तावेज़ अपलोड करें",
    uploadCardSub: "PDF, DOC, DOCX, PNG, JPG (अधिकतम 20MB)",
    chooseFileBtn: "फ़ाइल चुनें",
    recentUploadsTitle: "हाल के अपलोड",
    statusIndexed: "इंडेक्स्ड",
    statusPending: "लंबित",
    readDocAction: "दस्तावेज़ पढ़ें",

    // Settings Screen
    settingsMainTitle: "Settings",
    settingsMainSubtitle: "अपने अनुभव को अनुकूलित करें",
    langPrefTitle: "भाषा सेटिंग",
    aiModelPrefTitle: "AI मॉडल",
    apiKeysPrefTitle: "API Keys",
    themePrefTitle: "थीम",
    themeLightBtn: "☀️ लाइट",
    themeDarkBtn: "🌙 डार्क",
    autoSearchPrefTitle: "बोलने के बाद स्वतः खोजें",
    showSourcesPrefTitle: "आधिकारिक स्रोत दिखाएं",
    resetHistoryBtn: "खोज इतिहास साफ करें",

    // History Sidebar
    recentQueries: "हाल के प्रश्न",
    clearAllHistory: "🗑️ सभी हटाएं",
    clearingHistory: "हटाया जा रहा है...",
    noHistoryYet: "अभी तक कोई खोज इतिहास नहीं है। ऊपर दिए गए प्रश्नों पर क्लिक करें।",
    historyQuestion: "प्रश्न",
    historyLanguage: "भाषा",
    groundedRagTitle: "सत्यापित अनुसंधान गारंटी",
    groundedRagDesc: "प्रत्येक उत्तर की आधिकारिक राजपत्रों, सरकारी दिशानिर्देशों और मंत्रालयों के पोर्टलों से पुष्टि की जाती है।",

    // Hero Banner
    heroTag: "सरकारी योजना एवं नीति अनुसंधान विश्लेषण",
    heroTitle: "सरकारी योजना अनुसंधान एजेंट",
    heroDescription:
      "सरकारी योजनाओं, किसान कल्याण, सामाजिक कल्याण नीतियों, पात्रता मानदंडों और वित्तीय लाभों के लिए सत्यापित उत्तर। प्रत्येक उत्तर आधिकारिक सरकारी स्रोतों के प्रत्यक्ष उद्धरणों के साथ प्रस्तुत किया जाता है।",

    // Language Selector Bar
    responseLanguageLabel: "उत्तर की भाषा चुनें / Response Language:",

    // Search Card & Voice
    voiceSearchBtn: "🎙️ बोलकर पूछें (आवाज़ खोज)",
    stopListeningBtn: "⏹️ सुनना बंद करें",
    listeningPrefix: "🎙️ सुन रहा है",
    listeningPlaceholder: "माइक्रोफ़ोन में स्पष्ट रूप से बोलें...",
    speakInLanguage: "प्रश्न पूछने की भाषा:",
    autoSearchLabel: "⚡ बोलने के बाद स्वतः खोजें",
    searchPlaceholder:
      "किसान क्रेडिट कार्ड (KCC), 7/12 खतौनी, पीएम-किसान, फसल रोग, कीट रोकथाम, उर्वरक या सरकारी योजनाओं के बारे में कोई भी प्रश्न पूछें...",
    searchTip: "संकेत: सबमिट करने के लिए Ctrl + Enter दबाएं या बोलकर पूछने के लिए 🎙️ पर क्लिक करें",
    clearSearchBtn: "प्रश्न साफ करें",
    researchSchemesBtn: "अनुसंधान करें",
    researchingEvidenceBtn: "सरकारी साक्ष्य तलाशे जा रहे हैं...",

    // Alerts
    researchErrorTitle: "अनुसंधान त्रुटि",
    configureApiKeyBtn: "एपीआई कुंजी दर्ज करें",
    insufficientEvidenceTitle: "अपर्याप्त आधिकारिक साक्ष्य",
    insufficientEvidenceDesc:
      "अनुक्रमित सरकारी अभिलेखों में इस प्रश्न का निश्चित उत्तर देने के लिए पर्याप्त सत्यापित जानकारी उपलब्ध नहीं है।",

    // Structured Scheme Box
    activeStatus: "सक्रिय",
    eligibilityLabel: "🎯 पात्रता मानदंड",
    beneficiaryLabel: "👥 पात्र लाभार्थी",
    benefitsLabel: "💰 वित्तीय लाभ एवं सहायता राशि",
    documentsLabel: "📄 आवश्यक दस्तावेज़",
    nodalDeptLabel: "🏛️ नोडल विभाग/मंत्रालय:",
    officialPortalLink: "🔗 आधिकारिक पोर्टल ↗",

    // Answer Card
    verifiedSynthesisBadge: "सत्यापित निष्कर्ष",
    officialFindingsTitle: "आधिकारिक सरकारी शोध निष्कर्ष",
    readFindingsAloudBtn: "🔊 उत्तर बोलकर सुनें",
    pauseVoiceBtn: "⏸️ रोकें",
    resumeVoiceBtn: "▶️ जारी रखें",
    stopVoiceBtn: "⏹️ बंद करें",
    voiceSectionLabel: "भाग",
    recordTagPrefix: "अभिलेख #",

    // Clarifying Questions & Next Steps
    clarifyingTitle: "स्पष्टीकरण प्रश्न (अधिक सटीक उत्तर के लिए):",
    refineQueryBtn: "✍️ इस विवरण के साथ पुनः खोजें",
    practicalStepsTitle: "किसानों के लिए अगले व्यावहारिक कदम",
    practicalStepsSub: "आधिकारिक सरकारी अभिलेखों पर आधारित व्यावहारिक कार्य योजना",
    scopeWarningTitle: "आधिकारिक साक्ष्य सीमा चेतावनी",
    sourceDiscrepancyTitle: "स्रोतों में विसंगति पाई गई",
    sourceDiscrepancyDesc: "सत्यापित दस्तावेजों में इस विषय पर अलग-अलग आंकड़े या शर्तें दर्ज हैं:",

    // Citations & Sources
    officialSourcesTitle: "उद्धृत आधिकारिक स्रोत एवं दस्तावेज़",
    verifiedBadgeSuffix: "सत्यापित",
    listenSourceBtn: "🔊 सुनें",
    stopListenMiniBtn: "⏹️ रोकें",
    sourceUnavailable: "⚠️ आधिकारिक पोर्टल पर स्रोत URL उपलब्ध नहीं है",
    officialDateLabel: "दस्तावेज़ दिनांक:",
    checkedDateLabel: "सत्यापन दिनांक:",
    pageLabel: "पृष्ठ",
    officialFreshnessNotice:
      "जानकारी सीधे आधिकारिक सरकारी अभिलेखों पर आधारित है। सत्यापन दिनांक हमारे सिस्टम द्वारा जांच किए जाने का समय दर्शाता है; आधिकारिक दिनांक संबंधित विभाग द्वारा जारी प्रकाशन तिथि है। प्रशासनिक या वित्तीय निर्णय लेने से पहले आधिकारिक पोर्टल पर अवश्य पुष्टि करें।",

    // Retrieved Chunks
    retrievedChunksTitle: "🔍 प्राप्त साक्ष्य खंड एवं प्रासंगिकता स्कोर",
    similarityScoreLabel: "प्रासंगिकता स्कोर:",
    deptLabel: "विभाग:",
    yearLabel: "वर्ष:",
    typeLabel: "प्रकार:",

    // Modals
    modalClose: "✕",
    apiKeyModalTitle: "एआई प्रदाता विन्यास (API Key)",
    apiKeyModalDesc: "अनुसंधान एजेंट Groq (मुफ़्त और अत्यधिक तीव्र) या Anthropic Claude पर चल सकता है।",
    saveApiKeyBtn: "कुंजी सक्रिय करें",
    bdsModalTitle: "महाराष्ट्र कृषि योजनाएं (BDS 2026-27)",
    searchSchemesPlaceholder: "योजना के नाम, कोड (उदा. 1101100034) या कीवर्ड से खोजें...",
    structuredModalTitle: "आधिकारिक संरचित योजना निर्देशिका",
    docsModalTitle: "आधिकारिक सरकारी दस्तावेज़ केंद्र",
    searchDocsPlaceholder: "शीर्षक, विभाग या कीवर्ड द्वारा दस्तावेज़ खोजें...",
  },

  mr: {
    // Top Navbar
    portalTitle: "शासकीय संशोधन AI",
    portalSubtitle: "अधिकृत शासकीय संशोधन व धोरण माहिती प्रतिनिधी",
    apiOnline: "एपीआय ऑनलाइन",
    activeSchemesBadge: "104 सक्रिय योजना",
    apiKeyActive: "सक्रिय",
    apiKeyNotSet: "एपीआय की सेट नाही",
    themeDark: "🌙 डार्क",
    themeLight: "☀️ लाइट",
    navStructuredSchemes: "संरचित योजना",
    navBdsBudget: "महाराष्ट्र अर्थसंकल्प (BDS)",
    navOfficialDocs: "अधिकृत दस्तऐवज",

    // Dashboard Navigation
    navDashboard: "डॅशबोर्ड",
    navAskAi: "Ask AI",
    navSchemes: "शासकीय योजना",
    navDocuments: "दस्तऐवज",
    navHistory: "इतिहास",
    navSettings: "सेटिंग्ज",

    // Dashboard Home View
    dashGreeting: "नमस्कार!",
    dashGreetingNamaste: "नमस्कार!",
    dashSubtitle: "शासकीय योजना आणि अधिकृत माहितीसाठी तुमचा AI संशोधन सहाय्यक येथे आहे.",
    dashSearchPlaceholder: "तुमचा प्रश्न लिहा... (उदा. - PM-KISAN काय आहे?)",
    dashSearchBtn: "शोधा",
    categoryFarmer: "शेतकरी योजना",
    categoryFarmerDesc: "PM-KISAN, KCC, पीक विमा, शेती अवजारे इत्यादी",
    categoryScholarship: "शिष्यवृत्ती",
    categoryScholarshipDesc: "शिक्षण शिष्यवृत्ती, स्कॉलरशिप, कौशल्य विकास इत्यादी",
    categoryEntrepreneurship: "उद्योजकता",
    categoryEntrepreneurshipDesc: "मुद्रा कर्ज, स्टँड-अप इंडिया, PMEGP, स्टार्टअप सहाय्य इत्यादी",
    categoryWomen: "महिला कल्याण",
    categoryWomenDesc: "उज्ज्वला योजना, मातृत्व लाभ, स्वयंपरोजगार, सुरक्षा इत्यादी",
    categoryOther: "इतर योजना",
    categoryOtherDesc: "आरोग्य, पेन्शन, घरकुल, रोजगार, वाहतूक इत्यादी",
    govSchemesHeading: "Government Schemes",
    govSchemesSubtitle: "विविध शासकीय योजना व लाभांविषयी अधिकृत माहिती मिळवा",
    statTotalSchemesCount: "1,250+",
    statTotalSchemesLabel: "शासकीय योजना",
    statTotalDocsCount: "5,680+",
    statTotalDocsLabel: "दस्तऐवज अनुक्रमित केले",
    statAiAssistCount: "24/7",
    statAiAssistLabel: "AI सहाय्य उपलब्ध",
    statSourcesUpdateCount: "स्रोत अद्यतन",
    statSourcesUpdateLabel: "अंतिम पडताळणी: 10 ऑक्टोबर 2026",
    uploadSchemeCategoryFilter: "योजना वर्गवारीनुसार दस्तऐवज पहा व अपलोड करा",
    uploadSchemeCategorySub: "वर्गवारीनुसार अधिकृत मार्गदर्शक तत्त्वे आणि योजना फोटो पहा",
    schemesCountLabel: "योजना",
    statIndexedDocs: "अनुक्रमित दस्तऐवज",
    statChunks: "पुरावा खंड (Chunks)",
    statAiAssistant: "24/7 AI सहाय्यक",
    statSourcesUpdated: "स्रोत अद्ययावत",
    statLastChecked: "अंतिम पडताळणी: 10 ऑक्टोबर 2026",
    popularSchemes: "लोकप्रिय योजना",
    viewAllSchemes: "सर्व योजना →",

    // Ask AI Screen
    askAiHeaderTitle: "Ask AI",
    askAiHeaderSubtitle: "शासकीय योजनांशी संबंधित प्रश्न विचारा आणि अधिकृत माहिती मिळवा.",
    selectLanguageLabel: "भाषा निवडा",
    suggestedQuestionsTitle: "सुचवलेले प्रश्न",
    didYouKnowTitle: "तुम्हाला माहीत आहे का?",
    didYouKnowText: "तुम्ही तुमच्या भाषेत प्रश्न विचारू शकता. आम्ही मराठी, हिंदी आणि इंग्रजीमध्ये अधिकृत पुराव्यांसह उत्तरे देतो.",
    quickActionsTitle: "त्वरित प्रश्न:",
    quickActionApply: "अर्ज प्रक्रिया काय आहे?",
    quickActionEligibility: "पात्रता काय आहे?",
    quickActionStatus: "हप्त्याची स्थिती कशी तपासावी?",
    chatPlaceholder: "तुमचा प्रश्न लिहा...",
    backToDashboard: "← डॅशबोर्ड",

    // Schemes Directory Screen
    schemesTitle: "Government Schemes",
    schemesSubtitle: "शासकीय योजना शोधा आणि सविस्तर अधिकृत माहिती मिळवा",
    searchSchemePlaceholder: "योजनेचे नाव शोधा...",
    filterAll: "सर्व",
    filterFarmer: "शेतकरी",
    filterScholarship: "शिष्यवृत्ती",
    filterEntrepreneurship: "उद्योजकता",
    filterWomen: "महिला",
    filterOther: "इतर",
    viewDetailsLink: "सविस्तर माहिती →",
    backToSchemes: "← सर्व योजना",

    // Scheme Details Screen
    tabOverview: "परिचय",
    tabEligibility: "पात्रता",
    tabBenefits: "लाभ",
    tabDocuments: "आवश्यक कागदपत्रे",
    tabProcess: "अर्ज प्रक्रिया",
    schemeDescTitle: "योजनेचा तपशील",
    keyBenefitsTitle: "मुख्य लाभ",
    reqDocsTitle: "आवश्यक कागदपत्रे",
    visitOfficialPortalBtn: "अधिकृत संकेतस्थळाला भेट द्या ↗",
    askAiAboutThisSchemeBtn: "💬 या योजनेबद्दल AI ला विचारा",

    // Documents Screen
    docsMainTitle: "Documents",
    docsMainSubtitle: "अपलोड, व्यवस्थापन आणि शोधा",
    tabMyDocs: "माझे दस्तऐवज",
    tabIndexingStatus: "अनुक्रमणिका स्थिती",
    tabSourcesRegistry: "स्रोत",
    uploadCardTitle: "दस्तऐवज अपलोड करा",
    uploadCardSub: "PDF, DOC, DOCX, PNG, JPG (कमाल 20MB)",
    chooseFileBtn: "फाइल निवडा",
    recentUploadsTitle: "अलीकडील अपलोड",
    statusIndexed: "अनुक्रमित",
    statusPending: "प्रलंबित",
    readDocAction: "दस्तऐवज वाचा",

    // Settings Screen
    settingsMainTitle: "Settings",
    settingsMainSubtitle: "तुमचा अनुभव सानुकूलित करा",
    langPrefTitle: "भाषा सेटिंग",
    aiModelPrefTitle: "AI मॉडेल",
    apiKeysPrefTitle: "API Keys",
    themePrefTitle: "थीम",
    themeLightBtn: "☀️ लाइट",
    themeDarkBtn: "🌙 डार्क",
    autoSearchPrefTitle: "बोलल्यानंतर स्वतः शोधा",
    showSourcesPrefTitle: "अधिकृत स्रोत दाखवा",
    resetHistoryBtn: "खोज इतिहास हटवा",

    // History Sidebar
    recentQueries: "अलीकडील प्रश्न",
    clearAllHistory: "🗑️ सर्व पुसा",
    clearingHistory: "पुसले जात आहे...",
    noHistoryYet: "अद्याप कोणताही शोध इतिहास नाही. वरील नमुना प्रश्नांवर क्लिक करा.",
    historyQuestion: "प्रश्न",
    historyLanguage: "भाषा",
    groundedRagTitle: "पडताळणी केलेली माहिती हमी",
    groundedRagDesc: "प्रत्येक उत्तराची अधिकृत शासकीय राजपत्रे, शासन निर्णय (GR) आणि कृषी विभागाच्या नोंदींशी पडताळणी केली जाते.",

    // Hero Banner
    heroTag: "शासकीय योजना व धोरण संशोधन प्रणाली",
    heroTitle: "शासकीय योजना संशोधन प्रतिनिधी",
    heroDescription:
      "शासकीय योजना, शेतकरी कल्याण, सामाजिक विकास योजना, पात्रता निकष आणि आर्थिक लाभांची अधिकृत माहिती. प्रत्येक उत्तर पडताळणी केलेल्या सरकारी दस्तऐवजांच्या पुराव्यासह सादर केले जाते.",

    // Language Selector Bar
    responseLanguageLabel: "उत्तराची भाषा निवडा / Response Language:",

    // Search Card & Voice
    voiceSearchBtn: "🎙️ आवाजाने विचारा (व्हॉइस सर्च)",
    stopListeningBtn: "⏹️ ऐकणे थांबवा",
    listeningPrefix: "🎙️ ऐकत आहे",
    listeningPlaceholder: "मायक्रोफोनमध्ये स्पष्टपणे बोला...",
    speakInLanguage: "प्रश्न विचारण्याची भाषा:",
    autoSearchLabel: "⚡ बोलल्यानंतर लगेच शोधा",
    searchPlaceholder:
      "किसान क्रेडिट कार्ड (KCC), 7/12 उतारा, पीएम-किसान, पिकांवरील रोग, कीड नियंत्रण, खत व्यवस्थापन किंवा शासकीय योजनांविषयी प्रश्न विचारा...",
    searchTip: "टीप: उत्तर मिळवण्यासाठी Ctrl + Enter दाबा किंवा आवाजाने विचारण्यासाठी 🎙️ वर क्लिक करा",
    clearSearchBtn: "प्रश्न पुसा",
    researchSchemesBtn: "माहिती शोधा",
    researchingEvidenceBtn: "शासकीय पुरावे शोधत आहे...",

    // Alerts
    researchErrorTitle: "संशोधन त्रुटी",
    configureApiKeyBtn: "एपीआय की प्रविष्ट करा",
    insufficientEvidenceTitle: "अपुरा अधिकृत पुरावा",
    insufficientEvidenceDesc:
      "नोंदणीकृत शासकीय दस्तऐवजांमध्ये या प्रश्नाचे अचूक उत्तर देण्यासाठी पुरेसा पडताळणी केलेला पुरावा उपलब्ध नाही.",

    // Structured Scheme Box
    activeStatus: "सक्रिय",
    eligibilityLabel: "🎯 पात्रता निकष",
    beneficiaryLabel: "👥 पात्र लाभार्थी",
    benefitsLabel: "💰 आर्थिक लाभ व सहाय्य",
    documentsLabel: "📄 आवश्यक कागदपत्रे",
    nodalDeptLabel: "🏛️ नोडल विभाग:",
    officialPortalLink: "🔗 अधिकृत पोर्टल ↗",

    // Answer Card
    verifiedSynthesisBadge: "पडताळणी केलेला निष्कर्ष",
    officialFindingsTitle: "अधिकृत शासकीय संशोधन निष्कर्ष",
    readFindingsAloudBtn: "🔊 उत्तर ऐका (आवाज वाचक)",
    pauseVoiceBtn: "⏸️ थांबवा",
    resumeVoiceBtn: "▶️ सुरू ठेवा",
    stopVoiceBtn: "⏹️ बंद करा",
    voiceSectionLabel: "भाग",
    recordTagPrefix: "नोंद #",

    // Clarifying Questions & Next Steps
    clarifyingTitle: "स्पष्टीकरण प्रश्न (अधिक अचूक उत्तरासाठी):",
    refineQueryBtn: "✍️ या तपशीलासह पुन्हा विचारा",
    practicalStepsTitle: "शेतकऱ्यांसाठी प्रत्यक्ष करावयाच्या गोष्टी",
    practicalStepsSub: "अधिकृत सरकारी नोंदींवर आधारित प्रत्यक्ष कृती मार्गदर्शक",
    scopeWarningTitle: "अधिकृत माहिती मर्यादा सूचना",
    sourceDiscrepancyTitle: "दस्तऐवजांमध्ये तफावत आढळली",
    sourceDiscrepancyDesc: "पडताळणी केलेल्या सरकारी कागदपत्रांमध्ये या विषयावर परस्परविरोधी माहिती किंवा आकडेवारी आहे:",

    // Citations & Sources
    officialSourcesTitle: "उद्धृत केलेले अधिकृत शासकीय स्रोत",
    verifiedBadgeSuffix: "पडताळलेले",
    listenSourceBtn: "🔊 ऐका",
    stopListenMiniBtn: "⏹️ थांबवा",
    sourceUnavailable: "⚠️ अधिकृत पोर्टलवर मूळ URL उपलब्ध नाही",
    officialDateLabel: "दस्तऐवज तारीख:",
    checkedDateLabel: "पडताळणी तारीख:",
    pageLabel: "पान",
    officialFreshnessNotice:
      "ही माहिती थेट पडताळणी केलेल्या शासकीय नोंदींवर आधारित आहे. पडताळणी तारीख आमच्या प्रणालीने माहिती तपासल्याची तारीख दर्शवते; अधिकृत तारीख संबंधित विभागाने प्रसिद्ध केलेली तारीख आहे. कोणताही आर्थिक निर्णय घेण्यापूर्वी अधिकृत पोर्टलवर खात्री करावी.",

    // Retrieved Chunks
    retrievedChunksTitle: "🔍 मिळालेले पुरावा खंड आणि सुसंगतता गुण",
    similarityScoreLabel: "सुसंगतता गुण:",
    deptLabel: "विभाग:",
    yearLabel: "वर्ष:",
    typeLabel: "प्रकार:",

    // Modals
    modalClose: "✕",
    apiKeyModalTitle: "AI प्रदाता सेटिंग्ज (API Key)",
    apiKeyModalDesc: "हा संशोधन एजंट Groq (मोफत व अतिजलद) किंवा Anthropic Claude वर चालवता येतो.",
    saveApiKeyBtn: "की सक्रिय करा",
    bdsModalTitle: "महाराष्ट्र कृषी योजना (BDS २०२६-२७)",
    searchSchemesPlaceholder: "योजनेचे नाव, कोड (उदा. 1101100034) किंवा शब्दांनी शोधा...",
    structuredModalTitle: "अधिकृत संरचित योजना निर्देशिका",
    docsModalTitle: "अधिकृत शासकीय दस्तऐवज केंद्र",
    searchDocsPlaceholder: "शीर्षक, विभाग किंवा शब्दांनी दस्तऐवज शोधा...",
  },
};

export const DOMAIN_CATEGORIES_BY_LANG = {
  en: [
    {
      id: "farmer",
      label: "🌾 Farmer Questions",
      description: "Kisan Credit Card (KCC), land records (7/12 & RoR), disaster relief (SDRF/NDRF), and tenant farmer credit",
      questions: [
        "What is the procedure for obtaining a Kisan Credit Card (KCC) and what is the concessional interest rate?",
        "What documents and land records (RoR / 7/12 extract) are required to verify farmer eligibility?",
        "What financial assistance is provided under SDRF and NDRF norms for crop loss due to natural calamities?",
        "How can a tenant farmer or sharecropper access agricultural credit without land titles?",
      ],
    },
    {
      id: "crops",
      label: "🌱 Crop Problems",
      description: "Crop yellowing diagnosis, terminal heat stress, lodging management, and seed treatment protocols",
      questions: [
        "How to distinguish between Nitrogen deficiency, waterlogging, and Iron chlorosis when crop leaves turn yellow?",
        "What are the recommended varieties and mitigation sprays to prevent terminal heat stress in wheat?",
        "How can paddy lodging be prevented and managed after unseasonal rains during ripening?",
        "What are the optimum sowing windows and seed treatment protocols for irrigated wheat?",
      ],
    },
    {
      id: "pests",
      label: "🐛 Pest Questions",
      description: "Integrated Pest Management (IPM), Fall Armyworm, Pink Bollworm, Brown Plant Hopper, and bio-pesticides",
      questions: [
        "What is the Integrated Pest Management (IPM) schedule and ETL for Fall Armyworm (FAW) in maize?",
        "How to control Pink Bollworm in Bt Cotton using pheromone traps and approved bio-control agents?",
        "What are the official control measures for Brown Plant Hopper (BPH) in rice, and what chemicals must be avoided?",
        "Which bio-pesticides (like Trichoderma viride) are approved for pulse root rot and wilt management?",
      ],
    },
    {
      id: "fertilizers",
      label: "🧪 Fertilizer Questions",
      description: "Soil Health Card benchmarks, Neem Coated Urea, Nano Urea/DAP, and Zinc deficiency (Khaira)",
      questions: [
        "How to interpret Soil Health Card parameters (pH, EC, Organic Carbon, and NPK benchmarks)?",
        "What is the recommended application schedule and benefits of Neem Coated Urea over normal urea?",
        "How should Nano Urea and Nano DAP liquid be applied as foliar spray and seed treatment?",
        "What are the symptoms and soil correction methods for Zinc deficiency (Khaira disease) in paddy?",
      ],
    },
    {
      id: "schemes",
      label: "🏛️ Central Schemes",
      description: "PM-KISAN (Rs 6,000/yr), PMFBY (Crop Insurance), PM-KUSUM (Solar Pumps), and SMAM (Machinery)",
      questions: [
        "What are the mandatory e-KYC and land-seeding rules to receive Rs 6,00,0 yearly under PM-KISAN?",
        "Compare farmer premium rates and coverage stages under Pradhan Mantri Fasal Bima Yojana (PMFBY).",
        "What subsidy is provided for standalone solar agriculture pumps under PM-KUSUM Component B?",
        "What financial assistance is available under SMAM for purchasing tractors and farm machinery?",
      ],
    },
    {
      id: "maharashtra_schemes",
      label: "🌾 Maharashtra Schemes (2026–27)",
      description: "Namo Shetakari, Krushi Samrudhi, POCRA-II, SMART, Agri AI Policy, & BDS Budget Outlays",
      questions: [
        "What is the 2026-27 proposed budget outlay and allocation for Namo Shetakari Mahasanmaan Nidhi Yojana?",
        "What are the details and fund utilization of the new Krushi Samrudhi Yojana in Maharashtra?",
        "What is the Maharashtra Agriculture Artificial Intelligence Policy 2025-2029 allocation and objectives?",
        "What are the top 5 agricultural schemes by proposed outlay in Maharashtra for 2026-27?",
      ],
    },
    {
      id: "women_child",
      label: "👩 Women & Child Schemes",
      description: "Majhi Ladki Bahin (₹1,500/mo), Lek Ladki (₹1,01,000), PMMVY Maternity, Sakhi One Stop Centre, & Helpline 181",
      questions: [
        "What is the eligibility criteria and ₹1,500 monthly benefit under Mukhyamantri Majhi Ladki Bahin Yojana?",
        "What are the stage-wise milestone grants totaling ₹1,01,000 under Lek Ladki Yojana?",
        "What maternity benefits and DBT installments are provided under Pradhan Mantri Matru Vandana Yojana (PMMVY)?",
        "What emergency rescue, counseling, and shelter services are provided under One Stop Centre (Sakhi) and Helpline 181?",
      ],
    },
  ],

  hi: [
    {
      id: "farmer",
      label: "🌾 किसान प्रश्न",
      description: "किसान क्रेडिट कार्ड (KCC), 7/12 खतौनी, आपदा राहत (SDRF/NDRF) और बटाईदार किसान ऋण",
      questions: [
        "किसान क्रेडिट कार्ड (KCC) प्राप्त करने की प्रक्रिया क्या है और रियायती ब्याज दर क्या है?",
        "किसान पात्रता सत्यापन के लिए कौन से दस्तावेज और 7/12 खतौनी भू-अभिलेख आवश्यक हैं?",
        "प्राकृतिक आपदाओं से फसल नुकसान पर SDRF और NDRF मानकों के तहत क्या वित्तीय सहायता मिलती है?",
        "बिना भूमि स्वामित्व के बटाईदार या काश्तकार किसान कृषि ऋण कैसे प्राप्त कर सकते हैं?",
      ],
    },
    {
      id: "crops",
      label: "🌱 फसल समस्याएं",
      description: "फसल पीली पड़ने का निदान, गर्मी तनाव, फसल गिरना और बीज उपचार",
      questions: [
        "फसल के पत्ते पीले पड़ने पर नाइट्रोजन की कमी, जलभराव और लौह क्लोरोसिस में कैसे अंतर करें?",
        "गेहूं में टर्मिनल हीट स्ट्रेस (गर्मी तनाव) से बचाव के लिए अनुशंसित किस्में और छिड़काव क्या हैं?",
        "पकने के समय बेमौसम बारिश के बाद धान को गिरने (lodging) से कैसे बचाएं और प्रबंधित करें?",
        "सिंचित गेहूं की बुवाई का सही समय और बीज उपचार का तरीका क्या है?",
      ],
    },
    {
      id: "pests",
      label: "🐛 कीट समस्याएं",
      description: "एकीकृत कीट प्रबंधन (IPM), फॉल आर्मीवर्म, गुलाबी सुंडी, बीपीएच और जैविक कीटनाशक",
      questions: [
        "मक्का में फॉल आर्मीवर्म (FAW) के लिए एकीकृत कीट प्रबंधन (IPM) और आर्थिक क्षति स्तर (ETL) क्या है?",
        "बीटी कपास में फेरोमोन ट्रैप और अनुमोदित जैव-नियंत्रण एजेंटों से गुलाबी सुंडी (Pink Bollworm) को कैसे नियंत्रित करें?",
        "धान में भूरा फुदका (BPH) के आधिकारिक नियंत्रण उपाय क्या हैं और किन रसायनों से बचना चाहिए?",
        "दलहन में जड़ सड़न और उकठा (wilt) रोग प्रबंधन के लिए कौन से जैव-कीटनाशक (जैसे ट्राइकोडर्मा) अनुमोदित हैं?",
      ],
    },
    {
      id: "fertilizers",
      label: "🧪 उर्वरक प्रश्न",
      description: "मृदा स्वास्थ्य कार्ड, नीम लेपित यूरिया, नैनो यूरिया/डीएपी और जिंक की कमी (खैरा रोग)",
      questions: [
        "मृदा स्वास्थ्य कार्ड के मानकों (pH, EC, जैविक कार्बन और NPK स्तर) को कैसे समझें?",
        "सामान्य यूरिया की तुलना में नीम लेपित यूरिया के लाभ और उपयोग का अनुशंसित समय क्या है?",
        "नैनो यूरिया और नैनो डीएपी तरल का छिड़काव और बीज उपचार कैसे किया जाना चाहिए?",
        "धान में जिंक की कमी (खैरा रोग) के लक्षण और मिट्टी सुधार के तरीके क्या हैं?",
      ],
    },
    {
      id: "schemes",
      label: "🏛️ केंद्रीय योजनाएं",
      description: "पीएम-किसान (₹6,000/वर्ष), पीएमएफबीवाई (फसल बीमा), पीएम-कुसुम (सोलर पंप) और एसएमएएम",
      questions: [
        "पीएम-किसान के तहत ₹6,000 वार्षिक पाने के लिए अनिवार्य e-KYC और भूमि सीडिंग के नियम क्या हैं?",
        "प्रधानमंत्री फसल बीमा योजना (PMFBY) के तहत किसान प्रीमियम दरें और सुरक्षा चरण क्या हैं?",
        "पीएम-कुसुम घटक बी के तहत स्टैंडअलोन सौर कृषि पंपों पर कितनी सब्सिडी मिलती है?",
        "ट्रैक्टर और कृषि यंत्रों की खरीद पर SMAM योजना के तहत क्या वित्तीय सहायता उपलब्ध है?",
      ],
    },
    {
      id: "maharashtra_schemes",
      label: "🌾 महाराष्ट्र योजनाएं (2026–27)",
      description: "नमो शेतकरी, कृषि समृद्धि, पोकरा-II, स्मार्ट, कृषी एआई नीति और बजट आवंटन",
      questions: [
        "नमो शेतकरी महासन्मान निधी योजना के लिए 2026-27 का प्रस्तावित बजट आवंटन क्या है?",
        "महाराष्ट्र में नई कृषि समृद्धि योजना का विवरण और निधि उपयोग क्या है?",
        "महाराष्ट्र कृषि कृत्रिम बुद्धिमत्ता नीति 2025-2029 का आवंटन और उद्देश्य क्या हैं?",
        "महाराष्ट्र में 2026-27 के लिए प्रस्तावित परिव्यय के अनुसार शीर्ष 5 कृषि योजनाएं कौन सी हैं?",
      ],
    },
    {
      id: "women_child",
      label: "👩 महिला एवं बाल योजनाएं",
      description: "माझी लाड़की बहिन (₹1,500/माह), लेक लाड़की (₹1,01,000), पीएमएमवीवाई और सखी हेल्पलाइन 181",
      questions: [
        "मुख्यमंत्री माझी लाड़की बहिन योजना के तहत पात्रता मानदंड और ₹1,500 मासिक लाभ क्या हैं?",
        "लेक लाड़की योजना के तहत कुल ₹1,01,000 के चरणबद्ध अनुदान क्या हैं?",
        "प्रधानमंत्री मातृ वंदना योजना (PMMVY) के तहत क्या मातृत्व लाभ और DBT किस्तें प्रदान की जाती हैं?",
        "वन स्टॉप सेंटर (सखी) और हेल्पलाइन 181 के तहत आपातकालीन बचाव, परामर्श और आश्रय सेवाएं क्या हैं?",
      ],
    },
  ],

  mr: [
    {
      id: "farmer",
      label: "🌾 शेतकरी प्रश्न",
      description: "किसान क्रेडिट कार्ड (KCC), 7/12 उतारा, आपत्ती मदत (SDRF/NDRF) आणि भाडेकरू शेतकरी कर्ज",
      questions: [
        "किसान क्रेडिट कार्ड (KCC) मिळवण्याची पद्धत काय आहे आणि सवलतीचा व्याजदर किती आहे?",
        "शेतकरी पात्रता पडताळणीसाठी कोणती कागदपत्रे आणि 7/12 उतारा आवश्यक आहे?",
        "नैसर्गिक आपत्तीमुळे पिकांचे नुकसान झाल्यास SDRF आणि NDRF नियमांनुसार काय मदत मिळते?",
        "जमिनीची मालकी नसलेले भाडेकरू किंवा बटाईदार शेतकरी कृषी कर्ज कसे मिळवू शकतात?",
      ],
    },
    {
      id: "crops",
      label: "🌱 पीक समस्या",
      description: "पीक पिवळे पडणे, उष्णतेचा ताण, पीक लोळणे आणि बीजप्रक्रिया",
      questions: [
        "पिकाची पाने पिवळी पडल्यास नत्र कमतरता, पाण्याचा निचरा न होणे आणि लोह कमतरता यातील फरक कसा ओळखावा?",
        "गहू पिकामध्ये उष्णतेचा ताण टाळण्यासाठी कोणत्या सुधारित वाण आणि फवारणीची शिफारस आहे?",
        "अवेळी पावसामुळे भात पीक लोळण्यापासून (lodging) कसे वाचवावे आणि व्यवस्थापन करावे?",
        "बागायती गव्हाची पेरणी करण्याची योग्य वेळ आणि बीजप्रक्रिया पद्धत कोणती आहे?",
      ],
    },
    {
      id: "pests",
      label: "🐛 कीड समस्या",
      description: "एकात्मिक कीड व्यवस्थापन (IPM), लष्करी अळी, बोंडअळी, तुडतुडे आणि जैविक कीटकनाशके",
      questions: [
        "मका पिकामधील लष्करी अळीसाठी (FAW) एकात्मिक कीड व्यवस्थापन (IPM) आणि आर्थिक नुकसान पातळी (ETL) काय आहे?",
        "कपाशीतील गुलाबी बोंडअळी नियंत्रणासाठी कामगंध सापळे आणि जैविक कीटकनाशकांचा वापर कसा करावा?",
        "भातावरील तुडतुडे (BPH) नियंत्रणासाठी अधिकृत उपाय कोणते आणि कोणती रसायने टाळावीत?",
        "डाळवर्गीय पिकांमधील मूळकुज आणि मर रोगासाठी कोणते जैविक घटक (उदा. ट्रायकोडर्मा) मंजूर आहेत?",
      ],
    },
    {
      id: "fertilizers",
      label: "🧪 खत प्रश्न",
      description: "माती आरोग्य पत्रिका, निम कोटेड युरिया, नॅनो युरिया/डीएपी आणि जस्त कमतरता (खैरा)",
      questions: [
        "माती आरोग्य पत्रिकेतील घटक (सामू pH, क्षारता EC, सेंद्रिय कर्ब आणि NPK) कसे समजून घ्यावेत?",
        "साध्या युरियापेक्षा निम कोटेड युरियाचे फायदे आणि वापरण्याचे शिफारशीत वेळापत्रक काय आहे?",
        "नॅनो युरिया आणि नॅनो डीएपी द्रवरूपाची फवारणी व बीजप्रक्रिया कशी करावी?",
        "भातामधील जस्ताची कमतरता (खैरा रोग) ची लक्षणे आणि मातीतील उपाय कोणते आहेत?",
      ],
    },
    {
      id: "schemes",
      label: "🏛️ केंद्रीय योजना",
      description: "पीएम-किसान (₹6,000/वर्ष), पीएमएफबीवाई (पीक विमा), पीएम-कुसुम (सौर पंप) आणि एसएमएएम",
      questions: [
        "पीएम-किसान योजनेतून दरवर्षी ₹6,000 मिळवण्यासाठी अनिवार्य e-KYC आणि लँड-सीडिंगचे नियम काय आहेत?",
        "प्रधानमंत्री पीक विमा योजनेअंतर्गत (PMFBY) शेतकरी विमा हप्ता दर आणि नुकसान भरपाईचे टप्पे कोणते आहेत?",
        "पीएम-कुसुम घटक 'ब' अंतर्गत स्वतंत्र सौर कृषी पंपांवर किती अनुदान मिळते?",
        "ट्रॅक्टर व कृषी अवजारे खरेदीसाठी SMAM योजनेअंतर्गत किती आर्थिक मदत मिळते?",
      ],
    },
    {
      id: "maharashtra_schemes",
      label: "🌾 महाराष्ट्र योजना (2026–27)",
      description: "नमो शेतकरी, कृषी समृद्धी, पोकरा-२, स्मार्ट, कृषी एआय धोरण आणि अर्थसंकल्पीय तरतूद",
      questions: [
        "नमो शेतकरी महासन्मान निधी योजनेसाठी २०२६-२७ ची प्रस्तावित अर्थसंकल्पीय तरतूद किती आहे?",
        "महाराष्ट्रातील नवीन कृषी समृद्धी योजनेचा तपशील आणि निधी वापर कसा आहे?",
        "महाराष्ट्र कृषी कृत्रिम बुद्धिमत्ता धोरण २०२५-२०२९ ची तरतूद आणि मुख्य उद्दिष्टे काय आहेत?",
        "महाराष्ट्रात २०२६-२७ साठी प्रस्तावित तरतुदीनुसार पहिल्या ५ महत्त्वाच्या कृषी योजना कोणत्या आहेत?",
      ],
    },
    {
      id: "women_child",
      label: "👩 महिला व बाल योजना",
      description: "माझी लाडकी बहीण (₹1,500/महिना), लेक लाडकी (₹1,01,000), पीएमएमव्हीवाय आणि सखी हेल्पलाइन 181",
      questions: [
        "मुख्यमंत्री माझी लाडकी बहीण योजनेची पात्रता निकष आणि ₹1,500 मासिक लाभाचा तपशील काय आहे?",
        "लेक लाडकी योजनेअंतर्गत एकूण ₹1,01,000 चे टप्प्याटप्प्याने मिळणारे अनुदान कसे आहे?",
        "प्रधानमंत्री मातृ वंदना योजनेअंतर्गत (PMMVY) कोणते मातृत्व लाभ आणि DBT हप्ते दिले जातात?",
        "वन स्टॉप सेंटर (सखी) आणि हेल्पलाईन 181 द्वारे कोणती आपत्कालीन मदत, समुपदेशन व निवारा मिळतो?",
      ],
    },
  ],
};
