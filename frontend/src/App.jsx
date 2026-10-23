import { useState, useEffect, useRef, useMemo } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { SUPPORTED_LANGUAGES, UI_TRANSLATIONS, DOMAIN_CATEGORIES_BY_LANG } from "./i18n";

const API_URL = (import.meta.env.VITE_API_URL || "").replace(/\/+$/, "");
const API = API_URL;

// Auto-bypass ngrok free tier browser warning interstitial for API calls
if (typeof window !== "undefined" && window.fetch) {
  const _origFetch = window.fetch;
  window.fetch = async function (resource, config) {
    try {
      const url = typeof resource === "string" ? resource : resource?.url || "";
      const isNgrok = (API && API.includes("ngrok")) || url.includes("ngrok");
      if (isNgrok) {
        config = config ? { ...config } : {};
        if (config.headers instanceof Headers) {
          if (!config.headers.has("ngrok-skip-browser-warning")) {
            config.headers.set("ngrok-skip-browser-warning", "true");
          }
        } else if (Array.isArray(config.headers)) {
          config.headers = [...config.headers, ["ngrok-skip-browser-warning", "true"]];
        } else {
          config.headers = {
            ...config.headers,
            "ngrok-skip-browser-warning": "true",
          };
        }
      }
    } catch {
      // Fallback gracefully without interrupting request
    }
    return _origFetch.call(this, resource, config);
  };
}

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

// Helper for scheme category photo mappings matching design mockup with high resolution imagery
function getSchemeCategoryPhoto(category) {
  const cat = (category || "").toLowerCase();
  if (cat.includes("agri") || cat.includes("farmer") || cat.includes("kisan") || cat.includes("crop") || cat.includes("soil") || cat.includes("pest") || cat.includes("fertilizer") || cat.includes("wheat") || cat.includes("rice")) {
    return {
      photo: "/assets/scheme_cat_farmer.jpg",
      fallback: "/assets/scheme_cat_farmer.jpg",
      icon: "🌾",
      themeClass: "card-theme-farmer",
      color: "#166534",
      label: "कृषि एवं किसान कल्याण (Agriculture & Farmer Welfare)",
    };
  }
  if (cat.includes("edu") || cat.includes("scholar") || cat.includes("छात्रवृत्ति") || cat.includes("matric") || cat.includes("student") || cat.includes("university")) {
    return {
      photo: "/assets/scheme_cat_scholarship.jpg",
      fallback: "/assets/scheme_cat_scholarship.jpg",
      icon: "🎓",
      themeClass: "card-theme-scholarship",
      color: "#1d4ed8",
      label: "शिक्षा एवं छात्रवृत्ति (Education & Scholarships)",
    };
  }
  if (cat.includes("credit") || cat.includes("msme") || cat.includes("mudra") || cat.includes("loan") || cat.includes("entrepreneur") || cat.includes("उद्योग") || cat.includes("stand-up") || cat.includes("pmegp") || cat.includes("startup")) {
    return {
      photo: "/assets/scheme_cat_entrepreneur.jpg",
      fallback: "/assets/scheme_cat_entrepreneur.jpg",
      icon: "💼",
      themeClass: "card-theme-entrepreneurship",
      color: "#c2410c",
      label: "सूक्ष्म, लघु व मध्यम उद्यम एवं उद्यमिता (MSME & Entrepreneurship)",
    };
  }
  if (cat.includes("women") || cat.includes("child") || cat.includes("mahila") || cat.includes("girl") || cat.includes("महिला") || cat.includes("wcd") || cat.includes("ujjwala") || cat.includes("matritva") || cat.includes("ladki")) {
    return {
      photo: "/assets/scheme_cat_women.jpg",
      fallback: "/assets/scheme_cat_women.jpg",
      icon: "👩",
      themeClass: "card-theme-women",
      color: "#be185d",
      label: "महिला एवं बाल विकास (Women & Child Welfare)",
    };
  }
  return {
    photo: "/assets/scheme_cat_other.jpg",
    fallback: "/assets/scheme_cat_other.jpg",
    icon: "🏛️",
    themeClass: "card-theme-other",
    color: "#6d28d9",
    label: "सामाजिक सुरक्षा व लोक कल्याण (Social Security & Welfare)",
  };
}

// 26 Official Maharashtra & Central Scheme Cards from the Visual Compendium Poster
export const MAHARASHTRA_SCHEME_CARDS = [
  // Row 1 - Agriculture & Farmer Welfare
  {
    id: "pocra",
    nameEn: "POCRA (Climate Resilient Agriculture)",
    nameMr: "नानाजी देशमुख कृषी संजीवनी (पोकरा)",
    benefit: "Climate-resilient agriculture, water management & farm development",
    category: "Agriculture",
    icon: "🌱",
    badge: "PoCRA DBT",
    cardImg: "/assets/card_pocra.jpg",
    photoImg: "/assets/scheme_mahapocra_farmers_dbt.jpg",
    query: "पोकरा (PoCRA) योजनेअंतर्गत ठिबक सिंचन, शेततळे आणि अनुदानाचे नियम काय आहेत?",
    schemeId: "MAHAPOCRA-FARMERS-DBT",
  },
  {
    id: "namo_shetkari",
    nameEn: "Namo Shetkari Mahasanman Nidhi",
    nameMr: "नमो शेतकरी महासन्मान निधी योजना",
    benefit: "Financial assistance to eligible farmers of Maharashtra (₹6,000/yr)",
    category: "Agriculture",
    icon: "🌾",
    badge: "₹6,000/वर्ष",
    cardImg: "/assets/card_namo_shetkari.jpg",
    photoImg: "/assets/scheme_namo_shetkari.jpg",
    query: "महाराष्ट्र नमो शेतकरी महासन्मान निधी योजनेचे निकष आणि हप्ते कसे मिळतात?",
    schemeId: "NAMO-SHETAKARI",
  },
  {
    id: "pm_kisan",
    nameEn: "PM-KISAN Samman Nidhi",
    nameMr: "पीएम-किसान सन्मान निधी",
    benefit: "Direct income support of ₹6,000 annually to small & marginal farmers",
    category: "Agriculture",
    icon: "🚜",
    badge: "PM-KISAN",
    cardImg: "/assets/card_pm_kisan.jpg",
    photoImg: "/assets/scheme_farmer_banner.jpg",
    query: "पीएम-किसान योजनेचे ई-केवायसी आणि पात्रता निकष काय आहेत?",
    schemeId: "PM-KISAN",
  },
  {
    id: "pmfby",
    nameEn: "Pradhan Mantri Fasal Bima Yojana",
    nameMr: "पंतप्रधान पीक विमा योजना (१ रुपयात)",
    benefit: "Crop insurance protection for farmers' financial security",
    category: "Agriculture",
    icon: "🛡️",
    badge: "₹1 पीक विमा",
    cardImg: "/assets/card_pmfby.jpg",
    photoImg: "/assets/scheme_cat_farmer.jpg",
    query: "महाराष्ट्रात १ रुपयात पीक विमा योजना कशी लागू आहे?",
    schemeId: "PMFBY",
  },
  {
    id: "soil_health_card",
    nameEn: "Soil Health Card Scheme",
    nameMr: "मृदा आरोग्य पत्रिका योजना",
    benefit: "Healthy soil analysis, optimized fertilizers, better crop yield",
    category: "Agriculture",
    icon: "🧪",
    badge: "Soil Card",
    cardImg: "/assets/card_soil_health_card.jpg",
    photoImg: "/assets/scheme_cat_farmer.jpg",
    query: "मृदा आरोग्य पत्रिका कशी मिळवावी आणि माती परीक्षण कसे करावे?",
    schemeId: "SOIL-HEALTH-CARD",
  },

  // Row 2 - Education, Women & Entrepreneurship
  {
    id: "scholarship",
    nameEn: "MahaDBT Scholarship Schemes",
    nameMr: "महाडीबीटी शिष्यवृत्ती योजना",
    benefit: "Financial support for higher education, post-matric & professional courses",
    category: "Education",
    icon: "🎓",
    badge: "शिष्यवृत्ती",
    cardImg: "/assets/card_scholarship.jpg",
    photoImg: "/assets/scheme_cat_scholarship.jpg",
    query: "महाराष्ट्र महाडीबीटी पोस्ट-मॅट्रिक शिष्यवृत्तीचे नियम व कागदपत्रे काय आहेत?",
    schemeId: "MAHA-POST-MATRIC-SCHOLARSHIP",
  },
  {
    id: "mahila_kalyan",
    nameEn: "Majhi Ladki Bahin / Mahila Kalyan",
    nameMr: "मुख्यमंत्री माझी लाडकी बहीण योजना",
    benefit: "Direct cash transfer of ₹1,500/month for women's financial independence",
    category: "Women",
    icon: "👩",
    badge: "₹1,500/महिना",
    cardImg: "/assets/card_mahila_kalyan.jpg",
    photoImg: "/assets/scheme_cat_women.jpg",
    query: "मुख्यमंत्री माझी लाडकी बहीण योजनेची पात्रता आणि कागदपत्रे काय आहेत?",
    schemeId: "MH-WOM-01",
  },
  {
    id: "msrtc_bus",
    nameEn: "MSRTC 50% Concession (Mahila Sanman)",
    nameMr: "एसटी बस महिला सन्मान योजना (५०% सवलत)",
    benefit: "50% discount on bus fares across all Maharashtra State Transport buses",
    category: "Women",
    icon: "🚌",
    badge: "MSRTC 50%",
    cardImg: "/assets/scheme_msrtc_bus_women.jpg",
    photoImg: "/assets/scheme_msrtc_bus_women.jpg",
    query: "एसटी बस महिला सन्मान योजनेत ५० टक्के तिकीट सवलतीसाठी काय नियम आहेत?",
    schemeId: "MSRTC-50%-CONCESSION-ON-BUS-FARE",
  },
  {
    id: "lakhpati_didi",
    nameEn: "Lakhpati Didi Yojana",
    nameMr: "लखपती दीदी योजना",
    benefit: "Empowering rural SHG women to earn annual sustainable income of ₹1 Lakh+",
    category: "Women",
    icon: "💰",
    badge: "₹1 लाख उत्पन्न",
    cardImg: "/assets/card_lakhpati_didi.jpg",
    photoImg: "/assets/scheme_cat_women.jpg",
    query: "लखपती दीदी योजनेअंतर्गत बचत गटांना कर्ज व कौशल्य प्रशिक्षण कसे मिळते?",
    schemeId: "MH-WOM-10",
  },
  {
    id: "udyogini",
    nameEn: "Mukhyamantri Udyogini Yojana",
    nameMr: "महाराष्ट्र मुख्यमंत्री उद्योगिनी योजना",
    benefit: "Financial assistance & subsidized loans for women micro-entrepreneurs",
    category: "Credit",
    icon: "🧵",
    badge: "महिला उद्योग",
    cardImg: "/assets/card_udyogini.jpg",
    photoImg: "/assets/scheme_cat_entrepreneur.jpg",
    query: "महिलांसाठी उद्योगिनी योजना आणि व्यवसाय अनुदानाचे नियम काय आहेत?",
    schemeId: "MH-WOM-09",
  },
  {
    id: "startup_india",
    nameEn: "Startup & Stand-Up India",
    nameMr: "स्टार्टअप इंडिया / स्टँड-अप इंडिया",
    benefit: "Support for startups, bank loans for SC/ST and women entrepreneurs",
    category: "Credit",
    icon: "🚀",
    badge: "उद्यमिता कर्ज",
    cardImg: "/assets/card_startup_india.jpg",
    photoImg: "/assets/scheme_cat_entrepreneur.jpg",
    query: "स्टँड-अप इंडिया योजनेत १० लाख ते १ कोटी रुपयांचे कर्ज कसे मिळते?",
    schemeId: "STAND-UP-INDIA",
  },

  // Row 3 - Health, Housing & Rural Welfare
  {
    id: "ayushman_bharat",
    nameEn: "Ayushman Bharat / Mahatma Phule Jan Arogya",
    nameMr: "आयुष्मान भारत व महात्मा फुले जन आरोग्य",
    benefit: "Cashless health insurance coverage up to ₹5 Lakh per family per year",
    category: "Other",
    icon: "🏥",
    badge: "₹5 लाख मोफत",
    cardImg: "/assets/card_ayushman_bharat.jpg",
    photoImg: "/assets/scheme_ayushman_bharat.jpg",
    query: "आयुष्मान भारत आणि महात्मा ज्योतिराव फुले जन आरोग्य योजनेचे मोफत उपचार नियम काय आहेत?",
    schemeId: "PM-JAY",
  },
  {
    id: "pm_awas",
    nameEn: "Pradhan Mantri Awas Yojana (PMAY)",
    nameMr: "प्रधानमंत्री आवास योजना (घरकुल)",
    benefit: "Financial subsidy for pukka house construction for rural & urban homeless",
    category: "Other",
    icon: "🏡",
    badge: "PMAY घरकुल",
    cardImg: "/assets/card_pm_awas.jpg",
    photoImg: "/assets/scheme_pm_awas_yojana.jpg",
    query: "प्रधानमंत्री आवास योजना ग्रामीण (PMAY-G) अंतर्गत घरकुल अनुदान किती मिळते?",
    schemeId: "PMAY-G",
  },
  {
    id: "mgnrega",
    nameEn: "MGNREGA Rural Employment",
    nameMr: "महात्मा गांधी ग्रामीण रोजगार हमी (मनरेगा)",
    benefit: "Guaranteed 100 days of wage employment per year to rural households",
    category: "Other",
    icon: "👷",
    badge: "१०० दिवस काम",
    cardImg: "/assets/card_mgnrega.jpg",
    photoImg: "/assets/scheme_cat_other.jpg",
    query: "मनरेगा (MGNREGA) जॉब कार्ड कसे काढावे आणि मजुरी दर किती आहे?",
    schemeId: "MGNREGA",
  },
  {
    id: "pm_ujjwala",
    nameEn: "Pradhan Mantri Ujjwala Yojana",
    nameMr: "प्रधानमंत्री उज्ज्वला योजना (LPG गॅस)",
    benefit: "Free clean domestic LPG connection for women of BPL households",
    category: "Women",
    icon: "🔥",
    badge: "मोफत गॅस",
    cardImg: "/assets/card_pm_ujjwala.jpg",
    photoImg: "/assets/scheme_pm_ujjwala.jpg",
    query: "प्रधानमंत्री उज्ज्वला योजनेअंतर्गत मोफत गॅस कनेक्शनची पात्रता काय आहे?",
    schemeId: "MH-WOM-07",
  },
  {
    id: "digital_india",
    nameEn: "Digital India Services (Aaple Sarkar)",
    nameMr: "आपले सरकार / डिजिटल इंडिया सेवा",
    benefit: "Online certificates, 7/12 extract, caste & income certificates from home",
    category: "Other",
    icon: "📱",
    badge: "Digital India",
    cardImg: "/assets/card_digital_india.jpg",
    photoImg: "/assets/scheme_cat_other.jpg",
    query: "आपले सरकार पोर्टलवर उत्पन्न दाखला आणि रहिवासी प्रमाणपत्र कसे काढावे?",
    schemeId: "DIGITAL-INDIA",
  },

  // Row 4 - Maternal Health, Skills & Social Security
  {
    id: "pm_matru_vandana",
    nameEn: "PM Matru Vandana Yojana (PMMVY)",
    nameMr: "प्रधानमंत्री मातृ वंदना योजना",
    benefit: "Financial assistance of ₹5,000 directly for pregnant & lactating mothers",
    category: "Women",
    icon: "🤱",
    badge: "₹5,000 मातृत्व",
    cardImg: "/assets/card_pm_matru_vandana.jpg",
    photoImg: "/assets/scheme_cat_women.jpg",
    query: "प्रधानमंत्री मातृ वंदना योजनेचे पैसे कधी आणि कसे मिळतात?",
    schemeId: "MH-WOM-03",
  },
  {
    id: "janani_suraksha",
    nameEn: "Janani Suraksha Yojana",
    nameMr: "जननी सुरक्षा योजना",
    benefit: "Institutional delivery incentive and neonatal care in government health centres",
    category: "Women",
    icon: "👶",
    badge: "सुरक्षित प्रसूती",
    cardImg: "/assets/card_janani_suraksha.jpg",
    photoImg: "/assets/scheme_cat_women.jpg",
    query: "जननी सुरक्षा योजनेत शासकीय रुग्णालयातील प्रसूती अनुदान किती आहे?",
    schemeId: "JANANI-SURAKSHA",
  },
  {
    id: "pmkvy",
    nameEn: "PM Kaushal Vikas Yojana (PMKVY)",
    nameMr: "प्रधानमंत्री कौशल्य विकास योजना",
    benefit: "Free industry-relevant skill training, assessment and certification with placement",
    category: "Education",
    icon: "⚙️",
    badge: "कौशल्य प्रशिक्षण",
    cardImg: "/assets/card_pmkvy.jpg",
    photoImg: "/assets/scheme_cat_scholarship.jpg",
    query: "पीएमकेव्हीवाय (PMKVY) मोफत कौशल्य प्रशिक्षण केंद्र कसे शोधावे?",
    schemeId: "PMKVY",
  },
  {
    id: "nrlm",
    nameEn: "NRLM Umeed Abhiyan",
    nameMr: "दीनदयाळ अंत्योदय योजना (महाराष्ट्र उमेद)",
    benefit: "Community livelihood enhancement and revolving fund for women SHGs",
    category: "Other",
    icon: "🤝",
    badge: "उमेद SHG",
    cardImg: "/assets/card_nrlm.jpg",
    photoImg: "/assets/scheme_cat_other.jpg",
    query: "महाराष्ट्र उमेद अभियानांतर्गत महिला बचत गटांना मिळणारे अनुदान काय आहे?",
    schemeId: "NRLM-UMEED",
  },
  {
    id: "atal_pension",
    nameEn: "Atal Pension Yojana (APY)",
    nameMr: "अटल पेन्शन योजना",
    benefit: "Guaranteed monthly lifelong pension of ₹1,000 to ₹5,000 post 60 years",
    category: "Other",
    icon: "👵",
    badge: "मासिक पेन्शन",
    cardImg: "/assets/card_atal_pension.jpg",
    photoImg: "/assets/scheme_cat_other.jpg",
    query: "अटल पेन्शन योजनेमध्ये मासिक हप्ता आणि ६० वर्षानंतर पेन्शन किती मिळेल?",
    schemeId: "ATAL-PENSION",
  },

  // Row 5 - Allied Agriculture, Livestock & Fisheries
  {
    id: "kcc",
    nameEn: "Kisan Credit Card (KCC)",
    nameMr: "किसान क्रेडिट कार्ड योजना",
    benefit: "Short-term subsidized credit at 4% effective interest for farm crops",
    category: "Agriculture",
    icon: "💳",
    badge: "KCC Credit",
    cardImg: "/assets/card_kcc.jpg",
    photoImg: "/assets/scheme_cat_farmer.jpg",
    query: "किसान क्रेडिट कार्ड (KCC) कसे काढावे आणि कर्ज मर्यादा काय असते?",
    schemeId: "KCC",
  },
  {
    id: "fisheries",
    nameEn: "Fisheries & Aquaculture Scheme",
    nameMr: "मत्स्य व्यवसाय व जलकृषी विकास योजना",
    benefit: "Subsidies for fish ponds, biofloc, cage culture, and motorized boats",
    category: "Agriculture",
    icon: "🐟",
    badge: "मत्स्य व्यवसाय",
    cardImg: "/assets/card_fisheries.jpg",
    photoImg: "/assets/scheme_cat_farmer.jpg",
    query: "शेततळ्यात मत्स्यपालन आणि मत्स्य व्यवसाय अनुदानाचे नियम काय आहेत?",
    schemeId: "FISHERIES-AQUA",
  },
  {
    id: "sericulture",
    nameEn: "Sericulture Scheme (Silk Production)",
    nameMr: "रेशीम उद्योग व तुती लागवड योजना",
    benefit: "Government grants for mulberry plantation, rearing houses & silkworm farming",
    category: "Agriculture",
    icon: "🐛",
    badge: "रेशीम उद्योग",
    cardImg: "/assets/card_sericulture.jpg",
    photoImg: "/assets/scheme_cat_farmer.jpg",
    query: "महाराष्ट्रात तुती लागवड आणि सिल्क/रेशीम उद्योगासाठी मिळणारे शासकीय अनुदान काय आहे?",
    schemeId: "SERICULTURE-MH",
  },
  {
    id: "horticulture",
    nameEn: "National Horticulture Mission",
    nameMr: "एकात्मिक फलोत्पादन विकास अभियान",
    benefit: "Subsidies for fruit orchards, polyhouses, shade nets & cold storages",
    category: "Agriculture",
    icon: "🍎",
    badge: "फलोत्पादन",
    cardImg: "/assets/card_horticulture.jpg",
    photoImg: "/assets/scheme_cat_farmer.jpg",
    query: "भाजीपाला व फळबाग लागवडीसाठी राष्ट्रीय फलोत्पादन अभियान अनुदान कसे मिळते?",
    schemeId: "HORTICULTURE-MISSION",
  },
  {
    id: "animal_husbandry",
    nameEn: "Animal Husbandry & Dairy Scheme",
    nameMr: "पशुसंवर्धन व दुग्धव्यवसाय योजना",
    benefit: "Subsidies for milch cows/buffaloes, goat farming, and fodder development",
    category: "Agriculture",
    icon: "🐄",
    badge: "पशुसंवर्धन",
    cardImg: "/assets/card_animal_husbandry.jpg",
    photoImg: "/assets/scheme_cat_farmer.jpg",
    query: "गाई-म्हशी खरेदी आणि शेळीपालनासाठी पशुसंवर्धन विभागाचे अनुदान कसे मिळते?",
    schemeId: "ANIMAL-HUSBANDRY",
  },
  {
    id: "matsya_sampada",
    nameEn: "PM Matsya Sampada Yojana (PMMSY)",
    nameMr: "प्रधानमंत्री मत्स्य संपदा योजना",
    benefit: "Comprehensive development of marine and inland fisheries value chain",
    category: "Agriculture",
    icon: "🐠",
    badge: "मत्स्य संपदा",
    cardImg: "/assets/card_matsya_sampada.jpg",
    photoImg: "/assets/scheme_cat_farmer.jpg",
    query: "प्रधानमंत्री मत्स्य संपदा योजना (PMMSY) अंतर्गत मिळणारे अर्थसहाय्य काय आहे?",
    schemeId: "PMMSY",
  },
];

// Comprehensive scheme visual resolver supporting all individual schemes & categories
export function getSchemeVisual(scheme) {
  if (!scheme) {
    return {
      photo: "/assets/scheme_cat_other.jpg",
      card: "/assets/card_other.jpg",
      fallback: "/assets/card_other.jpg",
      icon: "🏛️",
      badge: "शासकीय योजना",
      label: "सामाजिक सुरक्षा व लोक कल्याण (Social Security & Welfare)",
      themeClass: "card-theme-other",
      color: "#6d28d9",
    };
  }

  const sId = (scheme.scheme_id || scheme.id || "").toLowerCase();
  const nameEn = (scheme.scheme_name || "").toLowerCase();
  const nameHi = (scheme.hindi_name || "").toLowerCase();
  const cat = (scheme.category || "").toLowerCase();
  const desc = ((scheme.eligibility || "") + " " + (scheme.benefits || "") + " " + (scheme.dataset_section || "")).toLowerCase();
  const fullText = `${sId} ${nameEn} ${nameHi} ${cat} ${desc}`;

  // 1. PoCRA / Nana Ji Deshmukh Krishi Sanjeevani (MahaPoCRA)
  if (fullText.includes("pocra") || fullText.includes("पोकरा") || fullText.includes("संजीवनी") || fullText.includes("climate resilient") || fullText.includes("mahapocra")) {
    return {
      photo: "/assets/scheme_mahapocra_farmers_dbt.jpg",
      card: "/assets/card_pocra.jpg",
      fallback: "/assets/scheme_mahapocra_farmers_dbt.jpg",
      icon: "🌱",
      badge: "PoCRA DBT",
      label: "नानाजी देशमुख कृषी संजीवनी (PoCRA)",
      themeClass: "card-theme-farmer",
      color: "#166534",
    };
  }

  // 2. MSRTC 50% Concession on Bus Fare (Mahila Sanman Yojana)
  if (fullText.includes("msrtc") || fullText.includes("st bus") || fullText.includes("एसटी") || fullText.includes("हाफ तिकीट") || fullText.includes("50% concession") || fullText.includes("mahila sanman")) {
    return {
      photo: "/assets/scheme_msrtc_bus_women.jpg",
      card: "/assets/card_mahila_kalyan.jpg",
      fallback: "/assets/scheme_msrtc_bus_women.jpg",
      icon: "🚌",
      badge: "MSRTC 50%",
      label: "MSRTC महिला सन्मान योजना (५०% सवलत)",
      themeClass: "card-theme-women",
      color: "#be185d",
    };
  }

  // 3. Namo Shetkari Mahasanman Nidhi Yojana
  if (fullText.includes("namo shetkari") || fullText.includes("shetkari mahasanman") || fullText.includes("नमो शेतकरी") || fullText.includes("shetakari")) {
    return {
      photo: "/assets/scheme_namo_shetkari.jpg",
      card: "/assets/card_namo_shetkari.jpg",
      fallback: "/assets/scheme_namo_shetkari.jpg",
      icon: "🌾",
      badge: "₹6,000/वर्ष",
      label: "नमो शेतकरी महासन्मान निधी योजना",
      themeClass: "card-theme-farmer",
      color: "#166534",
    };
  }

  // 4. PM-KISAN Samman Nidhi
  if (fullText.includes("pm-kisan") || fullText.includes("pm kisan") || fullText.includes("किसान सम्मान") || fullText.includes("kisan samman")) {
    return {
      photo: "/assets/scheme_farmer_banner.jpg",
      card: "/assets/card_pm_kisan.jpg",
      fallback: "/assets/scheme_farmer_banner.jpg",
      icon: "🚜",
      badge: "PM-KISAN",
      label: "PM-KISAN सन्मान निधी",
      themeClass: "card-theme-farmer",
      color: "#166534",
    };
  }

  // 5. Pradhan Mantri Fasal Bima Yojana (PMFBY)
  if (fullText.includes("pmfby") || fullText.includes("fasal bima") || fullText.includes("फसल बीमा") || fullText.includes("पीक विमा")) {
    return {
      photo: "/assets/scheme_cat_farmer.jpg",
      card: "/assets/card_pmfby.jpg",
      fallback: "/assets/scheme_cat_farmer.jpg",
      icon: "🛡️",
      badge: "₹1 पीक विमा",
      label: "प्रधानमंत्री पीक विमा योजना (PMFBY)",
      themeClass: "card-theme-farmer",
      color: "#166534",
    };
  }

  // 6. Soil Health Card Scheme
  if (fullText.includes("soil health") || fullText.includes("soil-health") || fullText.includes("मृदा आरोग्य") || fullText.includes("माती परीक्षण")) {
    return {
      photo: "/assets/scheme_cat_farmer.jpg",
      card: "/assets/card_soil_health_card.jpg",
      fallback: "/assets/scheme_cat_farmer.jpg",
      icon: "🧪",
      badge: "Soil Card",
      label: "मृदा आरोग्य पत्रिका योजना",
      themeClass: "card-theme-farmer",
      color: "#166534",
    };
  }

  // 7. PM-KUSUM (Solar Pumps)
  if (fullText.includes("kusum") || fullText.includes("कुसूम") || fullText.includes("solar pump") || fullText.includes("सौर कृषी पंप")) {
    return {
      photo: "/assets/scheme_cat_farmer.jpg",
      card: "/assets/card_pm_kusum.jpg",
      fallback: "/assets/scheme_cat_farmer.jpg",
      icon: "☀️",
      badge: "Solar Pump",
      label: "PM-KUSUM सौर कृषी पंप योजना",
      themeClass: "card-theme-farmer",
      color: "#d97706",
    };
  }

  // 8. Kisan Credit Card (KCC)
  if (fullText.includes("kcc") || fullText.includes("kisan credit card") || fullText.includes("किसान क्रेडिट कार्ड")) {
    return {
      photo: "/assets/scheme_cat_farmer.jpg",
      card: "/assets/card_kcc.jpg",
      fallback: "/assets/scheme_cat_farmer.jpg",
      icon: "💳",
      badge: "KCC Credit",
      label: "किसान क्रेडिट कार्ड (KCC)",
      themeClass: "card-theme-farmer",
      color: "#166534",
    };
  }

  // 9. Ayushman Bharat (PM-JAY / Jan Arogya)
  if (fullText.includes("ayushman") || fullText.includes("pm-jay") || fullText.includes("pmjay") || fullText.includes("jan arogya") || fullText.includes("आयुष्मान") || fullText.includes("जन आरोग्य") || fullText.includes("jyotirao phule")) {
    return {
      photo: "/assets/scheme_ayushman_bharat.jpg",
      card: "/assets/card_ayushman_bharat.jpg",
      fallback: "/assets/scheme_ayushman_bharat.jpg",
      icon: "🏥",
      badge: "₹5 लाख मोफत",
      label: "आयुष्मान भारत / महात्मा फुले जन आरोग्य योजना",
      themeClass: "card-theme-other",
      color: "#0284c7",
    };
  }

  // 10. Pradhan Mantri Awas Yojana (PMAY)
  if (fullText.includes("awas") || fullText.includes("pmay") || fullText.includes("आवास") || fullText.includes("घरकुल") || fullText.includes("housing")) {
    return {
      photo: "/assets/scheme_pm_awas_yojana.jpg",
      card: "/assets/card_pm_awas.jpg",
      fallback: "/assets/scheme_pm_awas_yojana.jpg",
      icon: "🏡",
      badge: "PMAY घरकुल",
      label: "प्रधानमंत्री आवास योजना (PMAY)",
      themeClass: "card-theme-other",
      color: "#0d9488",
    };
  }

  // 11. Pradhan Mantri Ujjwala Yojana
  if (fullText.includes("ujjwala") || fullText.includes("उज्ज्वला") || fullText.includes("lpg") || fullText.includes("गॅस कनेक्शन")) {
    return {
      photo: "/assets/scheme_pm_ujjwala.jpg",
      card: "/assets/card_pm_ujjwala.jpg",
      fallback: "/assets/scheme_pm_ujjwala.jpg",
      icon: "🔥",
      badge: "मोफत गॅस",
      label: "प्रधानमंत्री उज्ज्वला योजना (LPG)",
      themeClass: "card-theme-women",
      color: "#e11d48",
    };
  }

  // 12. Ladki Bahin / Lek Ladki / Mahila Kalyan
  if (fullText.includes("ladki bahin") || fullText.includes("लाडकी बहीण") || fullText.includes("lek ladki") || fullText.includes("mh-wom-01") || fullText.includes("mh-wom-02")) {
    return {
      photo: "/assets/scheme_cat_women.jpg",
      card: "/assets/card_mahila_kalyan.jpg",
      fallback: "/assets/scheme_cat_women.jpg",
      icon: "👩",
      badge: "₹1,500/महिना",
      label: "मुख्यमंत्री माझी लाडकी बहीण योजना",
      themeClass: "card-theme-women",
      color: "#be185d",
    };
  }

  // 13. Lakhpati Didi Yojana
  if (fullText.includes("lakhpati didi") || fullText.includes("लखपती दीदी")) {
    return {
      photo: "/assets/scheme_cat_women.jpg",
      card: "/assets/card_lakhpati_didi.jpg",
      fallback: "/assets/scheme_cat_women.jpg",
      icon: "💰",
      badge: "लखपती दीदी",
      label: "लखपती दीदी योजना",
      themeClass: "card-theme-women",
      color: "#be185d",
    };
  }

  // 14. Maharashtra Mukhyamantri Udyogini Yojana
  if (fullText.includes("udyogini") || fullText.includes("उद्योगिनी")) {
    return {
      photo: "/assets/scheme_cat_entrepreneur.jpg",
      card: "/assets/card_udyogini.jpg",
      fallback: "/assets/scheme_cat_entrepreneur.jpg",
      icon: "🧵",
      badge: "महिला उद्योग",
      label: "महाराष्ट्र मुख्यमंत्री उद्योगिनी योजना",
      themeClass: "card-theme-entrepreneurship",
      color: "#c2410c",
    };
  }

  // 15. Startup India / Stand-Up India / PMEGP / CGTMSE
  if (fullText.includes("startup") || fullText.includes("stand-up") || fullText.includes("standup") || fullText.includes("स्टार्टअप") || fullText.includes("pmegp") || fullText.includes("cgtmse") || fullText.includes("mudra")) {
    return {
      photo: "/assets/scheme_cat_entrepreneur.jpg",
      card: fullText.includes("pmegp") ? "/assets/card_pmegp.jpg" : fullText.includes("cgtmse") ? "/assets/card_cgtmse.jpg" : "/assets/card_startup_india.jpg",
      fallback: "/assets/scheme_cat_entrepreneur.jpg",
      icon: "🚀",
      badge: "उद्यमिता कर्ज",
      label: "स्टार्टअप इंडिया / स्टँड-अप इंडिया / PMEGP",
      themeClass: "card-theme-entrepreneurship",
      color: "#c2410c",
    };
  }

  // 16. Scholarships & Higher Education (MahaDBT)
  if (fullText.includes("scholarship") || fullText.includes("matric") || fullText.includes("छात्रवृत्ति") || fullText.includes("शिष्यवृत्ती") || fullText.includes("mahadbt") || fullText.includes("fellowship")) {
    return {
      photo: "/assets/scheme_cat_scholarship.jpg",
      card: "/assets/card_scholarship.jpg",
      fallback: "/assets/scheme_cat_scholarship.jpg",
      icon: "🎓",
      badge: "शिष्यवृत्ती",
      label: "महाडीबीटी शिष्यवृत्ती योजना",
      themeClass: "card-theme-scholarship",
      color: "#1d4ed8",
    };
  }

  // 17. MGNREGA / रोजगार हमी
  if (fullText.includes("mgnrega") || fullText.includes("nrega") || fullText.includes("रोजगार हमी") || fullText.includes("मनरेगा")) {
    return {
      photo: "/assets/scheme_cat_other.jpg",
      card: "/assets/card_mgnrega.jpg",
      fallback: "/assets/scheme_cat_other.jpg",
      icon: "👷",
      badge: "१०० दिवस काम",
      label: "महात्मा गांधी राष्ट्रीय ग्रामीण रोजगार हमी (मनरेगा)",
      themeClass: "card-theme-other",
      color: "#059669",
    };
  }

  // 18. Digital India / Services
  if (fullText.includes("digital india") || fullText.includes("डिजिटल इंडिया") || fullText.includes("mahaonline") || fullText.includes("aaple sarkar")) {
    return {
      photo: "/assets/scheme_cat_other.jpg",
      card: "/assets/card_digital_india.jpg",
      fallback: "/assets/scheme_cat_other.jpg",
      icon: "📱",
      badge: "Digital India",
      label: "डिजिटल इंडिया नागरिक सेवा",
      themeClass: "card-theme-other",
      color: "#0284c7",
    };
  }

  // 19. PM Matru Vandana Yojana (PMMVY)
  if (fullText.includes("matru vandana") || fullText.includes("pmmvy") || fullText.includes("मातृ वंदना") || fullText.includes("mh-wom-03")) {
    return {
      photo: "/assets/scheme_cat_women.jpg",
      card: "/assets/card_pm_matru_vandana.jpg",
      fallback: "/assets/scheme_cat_women.jpg",
      icon: "🤱",
      badge: "₹5,000 मातृत्व",
      label: "प्रधानमंत्री मातृ वंदना योजना (PMMVY)",
      themeClass: "card-theme-women",
      color: "#be185d",
    };
  }

  // 20. Janani Suraksha Yojana
  if (fullText.includes("janani suraksha") || fullText.includes("जननी सुरक्षा")) {
    return {
      photo: "/assets/scheme_cat_women.jpg",
      card: "/assets/card_janani_suraksha.jpg",
      fallback: "/assets/scheme_cat_women.jpg",
      icon: "👶",
      badge: "सुरक्षित प्रसूती",
      label: "जननी सुरक्षा योजना",
      themeClass: "card-theme-women",
      color: "#be185d",
    };
  }

  // 21. PMKVY / Kaushal Vikas
  if (fullText.includes("kaushal vikas") || fullText.includes("pmkvy") || fullText.includes("skill") || fullText.includes("कौशल")) {
    return {
      photo: "/assets/scheme_cat_scholarship.jpg",
      card: "/assets/card_pmkvy.jpg",
      fallback: "/assets/scheme_cat_scholarship.jpg",
      icon: "⚙️",
      badge: "कौशल्य प्रशिक्षण",
      label: "प्रधानमंत्री कौशल्य विकास योजना (PMKVY)",
      themeClass: "card-theme-scholarship",
      color: "#1d4ed8",
    };
  }

  // 22. Deen Dayal Antyodaya / NRLM / Umeed
  if (fullText.includes("nrlm") || fullText.includes("umeed") || fullText.includes("उमेद") || fullText.includes("antyodaya") || fullText.includes("self-help") || fullText.includes("बचत गट")) {
    return {
      photo: "/assets/scheme_cat_other.jpg",
      card: "/assets/card_nrlm.jpg",
      fallback: "/assets/scheme_cat_other.jpg",
      icon: "🤝",
      badge: "उमेद SHG",
      label: "महाराष्ट्र उमेद अभियान (NRLM)",
      themeClass: "card-theme-other",
      color: "#059669",
    };
  }

  // 23. Atal Pension Yojana (APY)
  if (fullText.includes("atal pension") || fullText.includes("apy") || fullText.includes("अटल पेन्शन") || fullText.includes("pension") || fullText.includes("पेन्शन")) {
    return {
      photo: "/assets/scheme_cat_other.jpg",
      card: "/assets/card_atal_pension.jpg",
      fallback: "/assets/scheme_cat_other.jpg",
      icon: "👵",
      badge: "मासिक पेन्शन",
      label: "अटल पेन्शन योजना (APY)",
      themeClass: "card-theme-other",
      color: "#6d28d9",
    };
  }

  // 24. Fisheries & Aquaculture / Matsya Sampada
  if (fullText.includes("fisheries") || fullText.includes("aquaculture") || fullText.includes("matsya") || fullText.includes("मत्स्य")) {
    return {
      photo: "/assets/scheme_cat_farmer.jpg",
      card: "/assets/card_fisheries.jpg",
      fallback: "/assets/scheme_cat_farmer.jpg",
      icon: "🐟",
      badge: "मत्स्य व्यवसाय",
      label: "मत्स्य व्यवसाय व जलकृषी विकास",
      themeClass: "card-theme-farmer",
      color: "#0284c7",
    };
  }

  // 25. Sericulture / Silk
  if (fullText.includes("sericulture") || fullText.includes("रेशीम") || fullText.includes("तुती")) {
    return {
      photo: "/assets/scheme_cat_farmer.jpg",
      card: "/assets/card_sericulture.jpg",
      fallback: "/assets/scheme_cat_farmer.jpg",
      icon: "🐛",
      badge: "रेशीम उद्योग",
      label: "रेशीम उद्योग व तुती लागवड योजना",
      themeClass: "card-theme-farmer",
      color: "#166534",
    };
  }

  // 26. Horticulture / फलोत्पादन
  if (fullText.includes("horticulture") || fullText.includes("फल") || fullText.includes("फलोत्पादन")) {
    return {
      photo: "/assets/scheme_cat_farmer.jpg",
      card: "/assets/card_horticulture.jpg",
      fallback: "/assets/scheme_cat_farmer.jpg",
      icon: "🍎",
      badge: "फलोत्पादन",
      label: "एकात्मिक फलोत्पादन विकास अभियान",
      themeClass: "card-theme-farmer",
      color: "#166534",
    };
  }

  // 27. Animal Husbandry & Dairy / पशुसंवर्धन
  if (fullText.includes("animal husbandry") || fullText.includes("dairy") || fullText.includes("पशुसंवर्धन") || fullText.includes("दुग्ध") || fullText.includes("gokul")) {
    return {
      photo: "/assets/scheme_cat_farmer.jpg",
      card: "/assets/card_animal_husbandry.jpg",
      fallback: "/assets/scheme_cat_farmer.jpg",
      icon: "🐄",
      badge: "पशुसंवर्धन",
      label: "पशुसंवर्धन व दुग्ध व्यवसाय विकास",
      themeClass: "card-theme-farmer",
      color: "#166534",
    };
  }

  // 28. Jal Jeevan Mission
  if (fullText.includes("jal jeevan") || fullText.includes("जल जीवन") || fullText.includes("हर घर जल")) {
    return {
      photo: "/assets/scheme_cat_other.jpg",
      card: "/assets/card_jal_jeevan.jpg",
      fallback: "/assets/scheme_cat_other.jpg",
      icon: "💧",
      badge: "हर घर जल",
      label: "जल जीवन मिशन",
      themeClass: "card-theme-other",
      color: "#0284c7",
    };
  }

  // 29. Beti Bachao Beti Padhao
  if (fullText.includes("beti bachao") || fullText.includes("बेटी बचाओ")) {
    return {
      photo: "/assets/scheme_cat_women.jpg",
      card: "/assets/card_beti_bachao.jpg",
      fallback: "/assets/scheme_cat_women.jpg",
      icon: "👧",
      badge: "बेटी बचाओ",
      label: "बेटी बचाओ बेटी पढ़ाओ",
      themeClass: "card-theme-women",
      color: "#be185d",
    };
  }

  // Fallback to broad category
  return getSchemeCategoryPhoto(scheme.category);
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
  const [datasetSections, setDatasetSections] = useState([]);
  const [selectedSectionGroup, setSelectedSectionGroup] = useState("all");
  const [selectedScheme, setSelectedScheme] = useState(null);
  const [schemeLoading, setSchemeLoading] = useState(false);
  const [schemeError, setSchemeError] = useState(null);
  const [schemeSubTab, setSchemeSubTab] = useState("overview");
  const schemeFetchSeqRef = useRef(0);

  // Automatic Scheme Update Pipeline State
  const [syncStatus, setSyncStatus] = useState(null);
  const [isSyncing, setIsSyncing] = useState(false);
  const [showSyncModal, setShowSyncModal] = useState(false);
  const [syncLogs, setSyncLogs] = useState([]);
  const [syncLogsLoading, setSyncLogsLoading] = useState(false);
  const [retryingSync, setRetryingSync] = useState(false);
  const [showHistoryModal, setShowHistoryModal] = useState(false);
  const [schemeHistoryList, setSchemeHistoryList] = useState([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyTargetScheme, setHistoryTargetScheme] = useState(null);

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
    fetchDatasetSections();
    fetchDocuments();
    fetchSourcesRegistry();
    fetchSyncStatus();
    return () => {
      stopTts();
      stopVoiceInput();
    };
  }, []);

  async function fetchSyncStatus() {
    try {
      const res = await fetch(`${API}/api/sync/status`);
      if (res.ok) {
        const data = await safeParseJson(res);
        if (data) setSyncStatus(data);
      }
    } catch (err) {
      console.error("Failed to fetch sync status:", err);
    }
  }

  async function handleTriggerSync() {
    setIsSyncing(true);
    try {
      const res = await fetch(`${API}/api/sync/run`, { method: "POST" });
      if (res.ok) {
        await fetchStructuredSchemes();
        await fetchSyncStatus();
      }
    } catch (err) {
      console.error("Failed to run sync pipeline:", err);
    } finally {
      setIsSyncing(false);
    }
  }

  async function fetchSyncLogs() {
    setSyncLogsLoading(true);
    try {
      const res = await fetch(`${API}/api/sync/logs?limit=50`);
      if (res.ok) {
        const data = await safeParseJson(res);
        if (data && data.items) setSyncLogs(data.items);
      }
    } catch (err) {
      console.error("Failed to fetch sync logs:", err);
    } finally {
      setSyncLogsLoading(false);
    }
  }

  async function handleRetrySync() {
    setRetryingSync(true);
    try {
      const res = await fetch(`${API}/api/sync/retry`, { method: "POST" });
      if (res.ok) {
        await fetchStructuredSchemes();
        await fetchSyncStatus();
        await fetchSyncLogs();
      }
    } catch (err) {
      console.error("Failed to retry sync:", err);
    } finally {
      setRetryingSync(false);
    }
  }

  async function openSchemeHistory(scheme) {
    if (!scheme) return;
    const targetId = scheme.scheme_id || scheme.id;
    setHistoryTargetScheme(scheme);
    setShowHistoryModal(true);
    setHistoryLoading(true);
    setSchemeHistoryList([]);
    try {
      const res = await fetch(`${API}/api/schemes/${encodeURIComponent(targetId)}/history`);
      if (res.ok) {
        const data = await safeParseJson(res);
        if (data && Array.isArray(data)) setSchemeHistoryList(data);
      }
    } catch (err) {
      console.error("Failed to fetch scheme history:", err);
    } finally {
      setHistoryLoading(false);
    }
  }

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

  async function fetchDatasetSections() {
    try {
      const res = await fetch(`${API}/schemes/sections`);
      if (res.ok) {
        const data = await safeParseJson(res);
        if (data && Array.isArray(data)) setDatasetSections(data);
      }
    } catch (err) {
      console.error("Failed to fetch dataset sections:", err);
    }
  }

  async function fetchStructuredSchemes() {
    try {
      const res = await fetch(`${API}/schemes?limit=2500`);
      if (res.ok) {
        const data = await safeParseJson(res);
        if (data) {
          const list = Array.isArray(data) ? data : (data.items || data.schemes || []);
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

  async function openSchemeDetails(schemeOrId) {
    const rawId = typeof schemeOrId === "object" ? (schemeOrId.scheme_id || schemeOrId.id) : schemeOrId;
    if (!rawId) return;

    const currentSeq = ++schemeFetchSeqRef.current;

    // Immediately clear stale state and show loading
    setSelectedScheme(null);
    setSchemeError(null);
    setSchemeLoading(true);
    setActiveTab("scheme-details");
    setSchemeSubTab("overview");

    try {
      const res = await fetch(`${API}/schemes/${encodeURIComponent(rawId)}`);
      if (currentSeq !== schemeFetchSeqRef.current) return;

      if (!res.ok) {
        if (res.status === 404) {
          throw new Error(
            selectedLang === "mr"
              ? "शासकीय योजना प्रणालीत सापडली नाही (४०४)."
              : selectedLang === "hi"
              ? "सरकारी योजना डेटाबेस में नहीं मिली (404)।"
              : "Government scheme not found in the database (404)."
          );
        }
        throw new Error(`Failed to load scheme details (${res.status})`);
      }

      const data = await safeParseJson(res);
      if (currentSeq !== schemeFetchSeqRef.current) return;
      if (!data) throw new Error("Invalid scheme data received from server.");

      setSelectedScheme(data);
    } catch (err) {
      if (currentSeq === schemeFetchSeqRef.current) {
        setSchemeError(err.message || "Failed to load scheme details");
      }
    } finally {
      if (currentSeq === schemeFetchSeqRef.current) {
        setSchemeLoading(false);
      }
    }
  }

  const featuredDbSchemes = useMemo(() => {
    const flagshipIds = [
      "MAHAPOCRA-FARMERS-DBT",
      "NAMO-SHETAKARI",
      "PM-KISAN",
      "PMFBY",
      "MH-WOM-01",
      "MUDRA-SHISHU",
    ];
    if (!structuredSchemes || structuredSchemes.length === 0) {
      return [
        {
          id: 1,
          scheme_id: "MAHAPOCRA-FARMERS-DBT",
          scheme_name: "MahaPoCRA - Farmers DBT",
          hindi_name: "नानाजी देशमुख कृषी संजीवनी प्रकल्प - शेतकरी डीबीटी (PoCRA Farmers DBT)",
          category: "Agriculture",
          dataset_section: "State Agriculture Scheme (BDS Active)",
          status: "Active",
          state_district: "Maharashtra (15 Districts)",
          benefits: "Direct benefit transfer (DBT) financial assistance and subsidies for climate-resilient farming, drip & sprinkler irrigation, farm ponds, shade net houses, and horticulture plantations.",
        },
        {
          id: 2,
          scheme_id: "NAMO-SHETAKARI",
          scheme_name: "Namo Shetakari Mahasanmaan Nidhi Yojana",
          hindi_name: "नमो शेतकरी महासन्मान निधी योजना",
          category: "Agriculture",
          dataset_section: "BDS Flagship: Namo Shetakari Mahasanmaan Nidhi",
          status: "Active",
          state_district: "Maharashtra",
          benefits: "Direct financial assistance of ₹6,000 per year from the Maharashtra State Government, disbursed in three equal installments directly into farmers' Aadhaar-linked bank accounts.",
        },
        {
          id: 3,
          scheme_id: "PM-KISAN",
          scheme_name: "Pradhan Mantri Kisan Samman Nidhi",
          hindi_name: "Pradhan Mantri Kisan Samman Nidhi",
          category: "Agriculture",
          dataset_section: "Central Flagship: Direct Income Support",
          status: "Active",
          state_district: "All India / Maharashtra",
          benefits: "Financial benefit of ₹6000 per annum per family payable in three equal installments of ₹2000 each, transferred directly into bank accounts of land-holding farmer families.",
        },
      ];
    }
    const map = new Map(structuredSchemes.map((s) => [s.scheme_id, s]));
    const matched = [];
    for (const fid of flagshipIds) {
      if (map.has(fid)) matched.push(map.get(fid));
    }
    if (matched.length < 3) {
      for (const s of structuredSchemes) {
        if (!matched.some((m) => (m.scheme_id || m.id) === (s.scheme_id || s.id))) {
          const t = ((s.scheme_id || "") + " " + (s.scheme_name || "") + " " + (s.hindi_name || "")).toLowerCase();
          if (t.includes("pocra") || t.includes("namo shet") || t.includes("kisan samman")) {
            matched.push(s);
          }
        }
        if (matched.length >= 6) break;
      }
    }
    for (const s of structuredSchemes) {
      if (!matched.some((m) => (m.scheme_id || m.id) === (s.scheme_id || s.id))) {
        matched.push(s);
      }
      if (matched.length >= 6) break;
    }
    return matched;
  }, [structuredSchemes]);

  const renderSchemeCard = (s) => {
    const visual = getSchemeVisual(s);
    return (
      <div
        key={s.id || s.scheme_id}
        className="scheme-card-item"
        style={{ cursor: "pointer" }}
        onClick={() => openSchemeDetails(s.scheme_id || s.id)}
      >
        <div>
          <div className="scheme-card-thumbnail-wrap">
            <img
              src={visual.photo}
              alt={s.hindi_name || s.scheme_name}
              className="scheme-card-thumbnail-img"
              loading="lazy"
              decoding="async"
              onError={(e) => {
                if (e.target.dataset.fallbackTried === "primary") {
                  e.target.dataset.fallbackTried = "secondary";
                  e.target.src = "/assets/scheme_fallback.svg";
                } else if (!e.target.dataset.fallbackTried) {
                  e.target.dataset.fallbackTried = "primary";
                  e.target.src = visual.fallback || "/assets/scheme_fallback.svg";
                }
              }}
            />
          </div>

          <div className="scheme-card-top-icon-bar">
            <div className="scheme-card-badge-icon">
              {visual.icon}
            </div>
            <div style={{ display: "flex", gap: "5px", alignItems: "center", flexWrap: "wrap" }}>
              {s.is_discontinued ? (
                <span
                  style={{
                    background: "rgba(239, 68, 68, 0.15)",
                    color: "#ef4444",
                    border: "1px solid rgba(239, 68, 68, 0.3)",
                    padding: "2px 7px",
                    borderRadius: "10px",
                    fontSize: "0.68rem",
                    fontWeight: 700,
                  }}
                >
                  ⚠️ Discontinued
                </span>
              ) : (
                <span
                  style={{
                    background: s.verification_status === "Pending Review" ? "rgba(245, 158, 11, 0.15)" : "var(--emerald-bg)",
                    color: s.verification_status === "Pending Review" ? "#d97706" : "var(--emerald-text)",
                    padding: "2px 7px",
                    borderRadius: "10px",
                    fontSize: "0.68rem",
                    fontWeight: 700,
                    display: "flex",
                    alignItems: "center",
                    gap: "4px",
                  }}
                >
                  {s.verification_status === "Pending Review" ? "⏳ Review Pending" : `● ${visual.badge || s.status || "Active"}`}
                </span>
              )}
              {s.verification_status === "Verified" && !s.is_discontinued && (
                <span
                  title="Verified with official government sources"
                  style={{
                    background: "rgba(59, 130, 246, 0.12)",
                    color: "#2563eb",
                    border: "1px solid rgba(59, 130, 246, 0.25)",
                    padding: "2px 6px",
                    borderRadius: "10px",
                    fontSize: "0.66rem",
                    fontWeight: 700,
                  }}
                >
                  🛡️ Verified
                </span>
              )}
            </div>
          </div>

          {s.dataset_section && (
            <div className="scheme-card-dataset-section-tag" title={s.dataset_section}>
              📑 {s.dataset_section}
            </div>
          )}

          <h3 className="scheme-card-title-hi">{s.hindi_name}</h3>
          <p className="scheme-card-title-en">{s.scheme_name}</p>
          {s.department && (
            <p style={{ margin: "2px 0 6px 0", fontSize: "0.74rem", color: "var(--text-dim)", fontWeight: 600 }}>
              🏛️ {s.department}
            </p>
          )}
          <p className="scheme-card-benefits-snippet">
            <strong>💰 लाभ:</strong> {s.benefits ? s.benefits.slice(0, 110) + "..." : "सरकारी सहायता उपलब्ध"}
          </p>
        </div>

        <div className="scheme-card-footer-action">
          <div style={{ display: "flex", flexDirection: "column", gap: "2px" }}>
            <span style={{ fontSize: "0.74rem", color: "var(--text-dim)", fontWeight: 600 }}>
              📍 {s.state_district}
            </span>
            {s.last_verified && (
              <span style={{ fontSize: "0.68rem", color: "var(--text-muted)" }}>
                🛡️ Verified: {s.last_verified.slice(0, 10)}
              </span>
            )}
          </div>
          <button
            type="button"
            className="scheme-card-details-link"
            onClick={(e) => {
              e.stopPropagation();
              openSchemeDetails(s.scheme_id || s.id);
            }}
          >
            <span>{t.viewDetailsLink || "विवरण देखें →"}</span>
          </button>
        </div>
      </div>
    );
  };

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
  async function ask(e, customQuery, langOverride, schemeIdOverride) {
    if (e) e.preventDefault();
    const q = (customQuery !== undefined ? customQuery : question).trim();
    if (q.length < 3) return;

    const targetLang = langOverride || selectedLang || "hi";
    const targetSchemeId =
      schemeIdOverride !== undefined
        ? schemeIdOverride
        : (activeTab === "scheme-details" && selectedScheme ? (selectedScheme.scheme_id || selectedScheme.id) : null);

    setLoading(true);
    setError("");
    setResult(null);
    stopTts();
    stopVoiceInput();
    setActiveTab("ask-ai");

    try {
      const payload = { question: q, language: targetLang };
      if (targetSchemeId) {
        payload.scheme_id = String(targetSchemeId);
      }

      const res = await fetch(`${API}/research`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      const data = await safeParseJson(res);
      if (!res.ok) throw new Error(data?.detail || `Request failed with status ${res.status}`);
      if (!data) throw new Error("Server returned an invalid non-JSON response.");

      setResult({ ...data, question: q, language: data.language || targetLang, scoped_scheme_id: targetSchemeId });
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
            <div className="dash-brand-emblem-wrap" title="State Emblem of India">
              <img
                src="/assets/national_emblem_light.png"
                alt="State Emblem of India"
                className="dash-brand-emblem-img"
              />
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

        {/* Bottom Satyameva Jayate Official State Emblem */}
        <div className="dash-sidebar-footer" title="State Emblem of India | सत्यमेव जयते">
          <div className="satyameva-emblem-wrap">
            <img
              src="/assets/national_emblem_light.png"
              alt="State Emblem of India - सत्यमेव जयते"
              className="satyameva-emblem-img"
              width="54"
              height="80"
              loading="lazy"
            />
          </div>
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
                    loading="eager"
                    decoding="async"
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

                {/* Active Scheme Scope Indicator */}
                {result?.scoped_scheme_id && (
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                      gap: "10px",
                      background: "var(--bg-card)",
                      border: "1.5px solid var(--accent)",
                      borderRadius: "var(--radius-md)",
                      padding: "8px 14px",
                      fontSize: "0.84rem",
                      color: "var(--text-main)",
                    }}
                  >
                    <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                      <span>🎯</span>
                      <span>
                        {selectedLang === "mr" ? "योजना-विशिष्ट संशोधन:" : selectedLang === "hi" ? "योजना-विशिष्ट अनुसंधान:" : "Scheme-Specific Research:"}{" "}
                        <strong>{result.matched_scheme?.hindi_name || result.matched_scheme?.scheme_name || result.scoped_scheme_id}</strong>
                      </span>
                    </div>
                    <button
                      type="button"
                      className="btn-secondary"
                      style={{ fontSize: "0.76rem", padding: "3px 10px", border: "1px solid var(--panel-border)" }}
                      onClick={() => ask(null, result.question, selectedLang, null)}
                      title="Search across all government schemes"
                    >
                      {selectedLang === "mr" ? "सर्व योजनांमध्ये शोधा ✕" : selectedLang === "hi" ? "सभी योजनाओं में खोजें ✕" : "Search all schemes ✕"}
                    </button>
                  </div>
                )}

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
                {result?.matched_scheme && (() => {
                  const visual = getSchemeVisual(result.matched_scheme);
                  return (
                    <div
                      style={{
                        background: "var(--bg-card)",
                        border: "1.5px solid var(--accent)",
                        borderRadius: "var(--radius-lg)",
                        overflow: "hidden",
                        boxShadow: "var(--shadow-md)",
                      }}
                    >
                      <div style={{ position: "relative", height: "145px", overflow: "hidden", background: "radial-gradient(circle at center, #f8fafc 0%, #e2e8f0 100%)", display: "flex", alignItems: "center", justifyContent: "center" }}>
                        <img
                          src={visual.photo}
                          alt={result.matched_scheme.scheme_name}
                          style={{ width: "100%", height: "100%", objectFit: "contain", objectPosition: "center center", imageRendering: "-webkit-optimize-contrast" }}
                          loading="lazy"
                          decoding="async"
                          onError={(e) => {
                            if (e.target.dataset.fallbackTried === "primary") {
                              e.target.dataset.fallbackTried = "secondary";
                              e.target.src = "/assets/scheme_fallback.svg";
                            } else if (!e.target.dataset.fallbackTried) {
                              e.target.dataset.fallbackTried = "primary";
                              e.target.src = visual.fallback || "/assets/scheme_fallback.svg";
                            }
                          }}
                        />
                        <div
                          style={{
                            position: "absolute",
                            bottom: "10px",
                            left: "14px",
                            background: "rgba(15, 23, 42, 0.85)",
                            backdropFilter: "blur(6px)",
                            color: "#ffffff",
                            padding: "4px 12px",
                            borderRadius: "20px",
                            fontSize: "0.78rem",
                            fontWeight: 700,
                            display: "flex",
                            alignItems: "center",
                            gap: "6px",
                          }}
                        >
                          <span>{visual.icon}</span>
                          <span>{visual.label}</span>
                        </div>
                      </div>

                      <div style={{ padding: "18px 20px" }}>
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: "10px" }}>
                          <div>
                            <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                              <span style={{ fontSize: "1.3rem" }}>{visual.icon}</span>
                              <h3 style={{ margin: 0, fontSize: "1.2rem", color: "var(--text-main)", fontWeight: 700 }}>
                                {result.matched_scheme.hindi_name}
                              </h3>
                            </div>
                            <div style={{ fontSize: "0.86rem", color: "var(--text-muted)", marginTop: "3px" }}>
                              {result.matched_scheme.scheme_name}
                            </div>
                          </div>
                          <div style={{ display: "flex", gap: "6px", alignItems: "center" }}>
                            <span style={{ background: "var(--accent-glow)", color: "var(--accent)", padding: "4px 10px", borderRadius: "12px", fontSize: "0.76rem", fontWeight: 700 }}>
                              {visual.badge}
                            </span>
                            <span style={{ background: "var(--emerald-bg)", color: "var(--emerald-text)", padding: "4px 10px", borderRadius: "12px", fontSize: "0.76rem", fontWeight: 700 }}>
                              ● {result.matched_scheme.status || "Active"}
                            </span>
                          </div>
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
                    </div>
                  );
                })()}

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

                <div style={{ display: "flex", gap: "10px", alignItems: "center", flexWrap: "wrap" }}>
                  <button
                    type="button"
                    className="sync-btn-sync-now"
                    onClick={handleTriggerSync}
                    disabled={isSyncing}
                    title="Automatically check authorized sources for updates and new schemes"
                  >
                    <span>{isSyncing ? "⏳ Syncing..." : "🔄 Sync Now"}</span>
                  </button>
                  <button
                    type="button"
                    className="sync-btn-logs"
                    onClick={() => {
                      fetchSyncLogs();
                      setShowSyncModal(true);
                    }}
                    title="View sync logs, status, and failure history"
                  >
                    <span>📊 Pipeline Logs</span>
                  </button>
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

              {/* Automatic Scheme Update Pipeline Status Banner */}
              <div className="sync-status-banner">
                <div className="sync-status-banner-left">
                  <div className={`sync-status-badge ${isSyncing ? "running" : (syncStatus?.last_sync_status === "FAILED" ? "failed" : "active")}`}>
                    <span>{isSyncing ? "🔄 Live Syncing Official Sources..." : "🟢 Auto-Update Pipeline Active"}</span>
                  </div>
                  <div className="sync-metrics-chips">
                    <span className="sync-metric-chip" title="Last time official sources were checked">
                      <span>🕒 Last Checked:</span>
                      <strong>{syncStatus?.last_completed_at ? new Date(syncStatus.last_completed_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : "Recently"}</strong>
                    </span>
                    <span className="sync-metric-chip" title="Total structured schemes verified in system">
                      <span>📑 Verified Schemes:</span>
                      <strong>{structuredSchemes.length}</strong>
                    </span>
                    {syncStatus?.last_result?.schemes_created > 0 && (
                      <span className="sync-metric-chip" style={{ color: "#10b981" }}>
                        <span>🆕 New:</span>
                        <strong>+{syncStatus.last_result.schemes_created}</strong>
                      </span>
                    )}
                    {syncStatus?.last_result?.schemes_updated > 0 && (
                      <span className="sync-metric-chip" style={{ color: "#0284c7" }}>
                        <span>🔄 Updated:</span>
                        <strong>{syncStatus.last_result.schemes_updated}</strong>
                      </span>
                    )}
                    {syncStatus?.last_result?.failed_sources?.length > 0 && (
                      <span className="sync-metric-chip" style={{ color: "#ef4444" }}>
                        <span>⚠️ Failed Sources:</span>
                        <strong>{syncStatus.last_result.failed_sources.length}</strong>
                      </span>
                    )}
                  </div>
                </div>

                <div className="sync-status-banner-right">
                  <span style={{ fontSize: "0.76rem", color: "var(--text-dim)" }}>
                    🛡️ Verified Official Sources Only • No Private Scraping
                  </span>
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

              {/* Section Navigation Scroll Bar */}
              <div style={{ margin: "16px 0 12px 0" }}>
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "8px", flexWrap: "wrap", gap: "8px" }}>
                  <span style={{ fontSize: "0.86rem", fontWeight: 700, color: "var(--accent)", display: "flex", alignItems: "center", gap: "6px" }}>
                    📑 {t.viewBySection || "Browse by Official Dataset Section"}:
                  </span>
                  {selectedSectionGroup !== "all" && (
                    <button
                      type="button"
                      style={{
                        background: "var(--bg-secondary)",
                        border: "1px solid var(--panel-border)",
                        borderRadius: "8px",
                        color: "var(--text-muted)",
                        cursor: "pointer",
                        fontSize: "0.78rem",
                        fontWeight: 600,
                        padding: "3px 10px",
                      }}
                      onClick={() => setSelectedSectionGroup("all")}
                    >
                      ✕ {t.filterAll || "Reset"}
                    </button>
                  )}
                </div>
                <div className="schemes-section-nav-scroll">
                  <button
                    type="button"
                    className={`schemes-section-nav-pill ${selectedSectionGroup === "all" ? "active" : ""}`}
                    onClick={() => setSelectedSectionGroup("all")}
                  >
                    <span>📑 {t.allSectionsPill || "All Dataset Sections"}</span>
                    <span className="section-count-badge">{structuredSchemes.length}</span>
                  </button>
                  {datasetSections.map((sec) => (
                    <button
                      key={sec.group_id}
                      type="button"
                      className={`schemes-section-nav-pill ${selectedSectionGroup === sec.group_id ? "active" : ""}`}
                      onClick={() => setSelectedSectionGroup(sec.group_id)}
                    >
                      <span>{sec.icon} {sec.group_name}</span>
                      <span className="section-count-badge">{sec.count}</span>
                    </button>
                  ))}
                </div>
              </div>

              {/* Schemes Cards Rendering */}
              {(() => {
                const filteredSchemes = structuredSchemes.filter((s) => {
                  const matchesSearch =
                    !schemeSearch ||
                    (s.scheme_name && s.scheme_name.toLowerCase().includes(schemeSearch.toLowerCase())) ||
                    (s.hindi_name && s.hindi_name.toLowerCase().includes(schemeSearch.toLowerCase())) ||
                    (s.eligibility && s.eligibility.toLowerCase().includes(schemeSearch.toLowerCase())) ||
                    (s.benefits && s.benefits.toLowerCase().includes(schemeSearch.toLowerCase())) ||
                    (s.dataset_section && s.dataset_section.toLowerCase().includes(schemeSearch.toLowerCase()));

                  const matchesCat =
                    schemeCategoryFilter === "all" ||
                    (schemeCategoryFilter === "Women"
                      ? s.category && (s.category.toLowerCase().includes("women") ||
                          s.category.toLowerCase().includes("child") ||
                          s.category.toLowerCase().includes("girl"))
                      : s.category && s.category.toLowerCase().includes(schemeCategoryFilter.toLowerCase()));

                  const matchesGroup =
                    selectedSectionGroup === "all" || s.section_group === selectedSectionGroup;

                  return matchesSearch && matchesCat && matchesGroup;
                });

                if (filteredSchemes.length === 0) {
                  return (
                    <div className="notice-card" style={{ padding: "40px 20px", textAlign: "center", justifyContent: "center", margin: "20px 0" }}>
                      <p style={{ margin: 0, color: "var(--text-muted)", fontSize: "1rem" }}>
                        🔍 {t.noResultsFound || "कोई योजना नहीं मिली। कृपया फ़िल्टर बदलें।"}
                      </p>
                    </div>
                  );
                }

                // If user is NOT searching and has selected "all" section groups, render section-wise groups!
                if (!schemeSearch && selectedSectionGroup === "all" && datasetSections.length > 0) {
                  const renderedGroupIds = new Set();
                  return (
                    <div>
                      {datasetSections.map((sec) => {
                        const secSchemes = filteredSchemes.filter((s) => s.section_group === sec.group_id);
                        if (secSchemes.length === 0) return null;
                        renderedGroupIds.add(sec.group_id);
                        return (
                          <div key={sec.group_id} className="dataset-section-group-block">
                            <div className="dataset-section-group-header">
                              <div className="dataset-section-group-header-left">
                                <div className="dataset-section-group-icon">{sec.icon}</div>
                                <div>
                                  <h3 className="dataset-section-group-title">{sec.group_name}</h3>
                                  <p className="dataset-section-group-sub">
                                    {sec.authority} {sec.source_file ? `• ${sec.source_file}` : ""}
                                  </p>
                                </div>
                              </div>
                              <div className="dataset-section-meta-tags">
                                {sec.source_file && (
                                  <span className="dataset-source-file-badge">📁 {sec.source_file}</span>
                                )}
                                <span className="dataset-section-count-chip">
                                  {secSchemes.length} {t.schemesCountLabel || "Schemes"}
                                </span>
                              </div>
                            </div>
                            <div className="schemes-card-directory-grid">
                              {secSchemes.map((s) => renderSchemeCard(s))}
                            </div>
                          </div>
                        );
                      })}

                      {/* Fallback for schemes not in recognized groups */}
                      {(() => {
                        const remaining = filteredSchemes.filter((s) => !renderedGroupIds.has(s.section_group));
                        if (remaining.length === 0) return null;
                        return (
                          <div className="dataset-section-group-block">
                            <div className="dataset-section-group-header">
                              <div className="dataset-section-group-header-left">
                                <div className="dataset-section-group-icon">🏛️</div>
                                <div>
                                  <h3 className="dataset-section-group-title">Additional Government Schemes</h3>
                                  <p className="dataset-section-group-sub">Central & State Portal Database</p>
                                </div>
                              </div>
                              <span className="dataset-section-count-chip">
                                {remaining.length} {t.schemesCountLabel || "Schemes"}
                              </span>
                            </div>
                            <div className="schemes-card-directory-grid">
                              {remaining.map((s) => renderSchemeCard(s))}
                            </div>
                          </div>
                        );
                      })()}
                    </div>
                  );
                }

                // Otherwise (searching or specific section group selected): single grid
                return (
                  <div className="schemes-card-directory-grid">
                    {filteredSchemes.map((s) => renderSchemeCard(s))}
                  </div>
                );
              })()}
            </div>
          )}

          {/* =========================================================================
              SCREEN 4: SCHEME DETAILS VIEW
              ========================================================================= */}
          {activeTab === "scheme-details" && (
            <div className="scheme-detail-screen">
              {schemeLoading && (
                <div className="notice-card" style={{ background: "var(--bg-secondary)", padding: "40px", justifyContent: "center", margin: "20px 0" }}>
                  <span className="spinner" />
                  <span style={{ fontWeight: 600, fontSize: "1.05rem" }}>
                    {selectedLang === "mr" ? "योजनेची अधिकृत माहिती लोड होत आहे..." : selectedLang === "hi" ? "योजना का आधिकारिक विवरण लोड हो रहा है..." : "Loading verified scheme details..."}
                  </span>
                </div>
              )}

              {schemeError && !schemeLoading && (
                <div className="notice-card error" style={{ padding: "24px", margin: "20px 0" }}>
                  <div className="notice-icon">⚠️</div>
                  <div className="notice-body">
                    <h3 style={{ margin: "0 0 8px 0" }}>{selectedLang === "mr" ? "योजना आढळली नाही" : selectedLang === "hi" ? "योजना नहीं मिली" : "Scheme Not Found"}</h3>
                    <p>{schemeError}</p>
                    <button
                      type="button"
                      className="btn-secondary"
                      onClick={() => {
                        setActiveTab("schemes");
                        setSelectedScheme(null);
                        setSchemeError(null);
                      }}
                      style={{ marginTop: "12px" }}
                    >
                      {t.backToSchemes || "← सभी योजनाएं"}
                    </button>
                  </div>
                </div>
              )}

              {!schemeLoading && !schemeError && selectedScheme && (
                <>
                  <div className="scheme-detail-header-nav">
                    <button type="button" className="askai-back-btn" onClick={() => setActiveTab("schemes")}>
                      {t.backToSchemes || "← सभी योजनाएं"}
                    </button>
                    <div style={{ display: "flex", gap: "8px", alignItems: "center", flexWrap: "wrap" }}>
                      {selectedScheme.scheme_id && (
                        <span style={{ background: "var(--bg-secondary)", padding: "4px 10px", borderRadius: "12px", fontSize: "0.78rem", fontWeight: 700, color: "var(--text-muted)", fontFamily: "monospace" }}>
                          ID: {selectedScheme.scheme_id}
                        </span>
                      )}
                      <span style={{ background: "var(--bg-secondary)", padding: "4px 12px", borderRadius: "12px", fontSize: "0.8rem", fontWeight: 700, color: "var(--accent)" }}>
                        🏷️ {selectedScheme.category}
                      </span>
                      {selectedScheme.dataset_section && (
                        <span style={{ background: "rgba(2, 132, 199, 0.12)", color: "var(--accent)", border: "1px solid rgba(2, 132, 199, 0.25)", padding: "4px 10px", borderRadius: "12px", fontSize: "0.78rem", fontWeight: 700 }}>
                          📑 {selectedScheme.dataset_section}
                        </span>
                      )}
                      <span
                        style={{
                          background: selectedScheme.is_discontinued ? "rgba(239, 68, 68, 0.15)" : (selectedScheme.verification_status === "Pending Review" ? "rgba(245, 158, 11, 0.15)" : "var(--emerald-bg)"),
                          color: selectedScheme.is_discontinued ? "#ef4444" : (selectedScheme.verification_status === "Pending Review" ? "#d97706" : "var(--emerald-text)"),
                          padding: "4px 10px",
                          borderRadius: "12px",
                          fontSize: "0.8rem",
                          fontWeight: 700,
                        }}
                      >
                        ● {selectedScheme.is_discontinued ? "Discontinued" : (selectedScheme.status || "Active")}
                      </span>
                      <span
                        style={{
                          background: "rgba(59, 130, 246, 0.12)",
                          color: "#2563eb",
                          padding: "4px 10px",
                          borderRadius: "12px",
                          fontSize: "0.78rem",
                          fontWeight: 700,
                        }}
                      >
                        {selectedScheme.verification_status === "Pending Review" ? "⏳ Pending Review" : "🛡️ Verified Scheme"}
                      </span>
                      <button
                        type="button"
                        className="btn-secondary"
                        style={{ padding: "4px 10px", fontSize: "0.76rem" }}
                        onClick={() => openSchemeHistory(selectedScheme)}
                        title="Inspect change history, content diffs, and revisions"
                      >
                        📜 Revision History
                      </button>
                    </div>
                  </div>

                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: "12px", marginBottom: "16px" }}>
                    <div>
                      <div style={{ display: "flex", alignItems: "center", gap: "10px", flexWrap: "wrap" }}>
                        <h1 style={{ fontFamily: "var(--font-heading)", fontSize: "1.85rem", margin: 0, color: "var(--text-main)", fontWeight: 800 }}>
                          {selectedScheme.hindi_name}
                        </h1>
                        <span className="scheme-badge-farmer">
                          {selectedScheme.category?.includes("Agriculture") || selectedScheme.category?.includes("Farmer") ? "🌾 किसान" : selectedScheme.category?.includes("Women") ? "👩 महिला" : selectedScheme.category}
                        </span>
                      </div>
                      <p style={{ margin: "4px 0 0 0", fontSize: "0.94rem", color: "var(--text-muted)" }}>
                        {selectedScheme.scheme_name} • 🏛️ {selectedScheme.department || selectedScheme.authority}
                      </p>
                    </div>

                    <div style={{ display: "flex", gap: "8px", alignItems: "center", flexWrap: "wrap" }}>
                      <span style={{ background: "var(--bg-secondary)", padding: "4px 12px", borderRadius: "12px", fontSize: "0.8rem", fontWeight: 700, color: "var(--accent)" }}>
                        📍 {selectedScheme.state_district}
                      </span>
                      {selectedScheme.last_verified && (
                        <span style={{ background: "var(--bg-secondary)", border: "1px solid var(--panel-border)", padding: "4px 10px", borderRadius: "12px", fontSize: "0.76rem", color: "var(--text-muted)" }}>
                          🛡️ Verified: {selectedScheme.last_verified.slice(0, 10)}
                        </span>
                      )}
                      {selectedScheme.last_checked && (
                        <span style={{ background: "var(--bg-secondary)", border: "1px solid var(--panel-border)", padding: "4px 10px", borderRadius: "12px", fontSize: "0.76rem", color: "var(--text-muted)" }}>
                          🔍 Checked: {selectedScheme.last_checked.slice(0, 10)}
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Dynamic Scheme Category Banner with Photos */}
                  {(() => {
                    const visual = getSchemeVisual(selectedScheme);
                    return (
                      <div className="scheme-banner-container">
                        <img
                          src={visual.photo}
                          alt=""
                          aria-hidden="true"
                          className="scheme-banner-bg-blur"
                        />
                        <img
                          src={visual.photo}
                          alt={selectedScheme.scheme_name}
                          className="scheme-detail-hero-banner"
                          loading="eager"
                          decoding="sync"
                          onError={(e) => {
                            if (e.target.dataset.fallbackTried === "primary") {
                              e.target.dataset.fallbackTried = "secondary";
                              e.target.src = "/assets/scheme_fallback.svg";
                            } else if (!e.target.dataset.fallbackTried) {
                              e.target.dataset.fallbackTried = "primary";
                              e.target.src = visual.fallback || "/assets/scheme_fallback.svg";
                            }
                          }}
                        />
                        <div className="scheme-banner-badge-overlay">
                          <span>{visual.icon}</span>
                          <span>{selectedScheme.hindi_name} • {visual.label}</span>
                        </div>
                      </div>
                    );
                  })()}

                  {/* Dataset Section Callout Card */}
                  {selectedScheme.dataset_section && (
                    <div className="scheme-detail-dataset-callout">
                      <div className="scheme-detail-dataset-callout-icon">📑</div>
                      <div style={{ flex: 1 }}>
                        <div className="scheme-detail-dataset-callout-title">
                          {t.officialCompendium || "Official Dataset Compendium"}
                        </div>
                        <div className="scheme-detail-dataset-callout-section-name">
                          {selectedScheme.dataset_section}
                        </div>
                        <div className="scheme-detail-dataset-callout-meta">
                          {selectedScheme.authority && (
                            <span>🏛️ <strong>प्राधिकरण / Authority:</strong> {selectedScheme.authority}</span>
                          )}
                          {selectedScheme.state_district && (
                            <span>📍 <strong>क्षेत्र / Jurisdiction:</strong> {selectedScheme.state_district}</span>
                          )}
                          {selectedScheme.category && (
                            <span>🏷️ <strong>वर्ग / Category:</strong> {selectedScheme.category}</span>
                          )}
                        </div>
                      </div>
                    </div>
                  )}

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

                  {/* Tab Content Display - Clean Layout */}
                  <div className="scheme-details-content-grid">
                    {schemeSubTab === "overview" && (
                      <>
                        <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
                          <div className="scheme-detail-info-card">
                            <span className="scheme-detail-card-title">📖 {t.schemeDescTitle || "योजना का विवरण"}</span>
                            <p className="scheme-detail-card-text" style={{ whiteSpace: "pre-line" }}>
                              {selectedScheme.description || selectedScheme.guidelines_summary || selectedScheme.scheme_name}
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
                                  : <li>अधिकृत शासकीय आर्थिक लाभ व अनुदान डीबीटी (DBT) द्वारे.</li>}
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
                                  : ["आधार कार्ड (Aadhaar Card)", "सक्रिय बँक खाते (Active Bank Account / Passbook)", "ओळख व रहिवासी पुरावा", "मोबाईल क्रमांक"]
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
                        <p className="scheme-detail-card-text" style={{ whiteSpace: "pre-line" }}>
                          {selectedScheme.eligibility || selectedScheme.eligibility_criteria || "सविस्तर पात्रता निकष अधिकृत पोर्टलवर उपलब्ध आहेत."}
                        </p>
                      </div>
                    )}

                    {schemeSubTab === "benefits" && (
                      <div className="scheme-detail-info-card" style={{ gridColumn: "1 / -1" }}>
                        <span className="scheme-detail-card-title">💰 {t.keyBenefitsTitle || "मुख्य लाभ (Benefits & Assistance)"}</span>
                        <p className="scheme-detail-card-text" style={{ whiteSpace: "pre-line" }}>
                          {selectedScheme.benefits || "शासकीय नियमांनुसार आर्थिक मदत आणि थेट लाभ हस्तांतरण (DBT)."}
                        </p>
                      </div>
                    )}

                    {schemeSubTab === "documents" && (
                      <div className="scheme-detail-info-card" style={{ gridColumn: "1 / -1" }}>
                        <span className="scheme-detail-card-title">📄 {t.reqDocsTitle || "आवश्यक दस्तावेज (Required Documents)"}</span>
                        <p className="scheme-detail-card-text" style={{ whiteSpace: "pre-line" }}>
                          {selectedScheme.documents || selectedScheme.required_documents || "आधार कार्ड, बँक पासबुक, पासपोर्ट फोटो व संबंधित प्रमाणपत्रे."}
                        </p>
                      </div>
                    )}

                    {schemeSubTab === "process" && (
                      <div className="scheme-detail-info-card" style={{ gridColumn: "1 / -1" }}>
                        <span className="scheme-detail-card-title">📝 {t.tabProcess || "आवेदन प्रक्रिया (Application Process)"}</span>
                        <p className="scheme-detail-card-text" style={{ whiteSpace: "pre-line" }}>
                          {selectedScheme.application_process || (
                            selectedScheme.official_source_url
                              ? `1. अधिकृत पोर्टलवर भेट द्या: ${selectedScheme.official_source_url}\n2. नवीन अर्ज नोंदणी (New Registration) पर्यायावर क्लिक करा.\n3. आवश्यक वैयक्तिक माहिती, बँक खाते व आधार तपशील भरा.\n4. कागदपत्रे अपलोड करून अर्ज सबमिट करा व पोचपावती (Acknowledgment) जतन करा.`
                              : "1. अधिकृत शासकीय पोर्टल किंवा नजीकच्या आपले सरकार / सीएससी सेवा केंद्रावर जा.\n2. विहित नमुन्यातील अर्ज भरून आवश्यक कागदपत्रे जोडा.\n3. बायोमेट्रिक किंवा ओटीपी द्वारे ई-केवायसी पूर्ण करा.\n4. अर्ज सादर करून पावती क्रमांक मिळवा."
                          )}
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
                        const q = `${selectedScheme.hindi_name} (${selectedScheme.scheme_name}) ची पात्रता आणि लाभ काय आहेत?`;
                        setQuestion(q);
                        ask(null, q, selectedLang, selectedScheme.scheme_id || selectedScheme.id);
                      }}
                    >
                      {t.askAiAboutThisSchemeBtn || "💬 इस योजना के बारे में AI से पूछें"}
                    </button>

                    {selectedScheme.application_url && (
                      <a
                        href={selectedScheme.application_url}
                        target="_blank"
                        rel="noreferrer"
                        className="scheme-official-portal-btn"
                        style={{ background: "linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%)", color: "#ffffff", boxShadow: "0 2px 8px rgba(37, 99, 235, 0.35)" }}
                        title="Direct link to official online application portal"
                      >
                        <span>📝 Apply Online (अधिकृत अर्ज पोर्टल) ↗</span>
                      </a>
                    )}

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
                </>
              )}
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

      {/* 6. MODAL: SYNC PIPELINE EXECUTION LOGS & RETRY */}
      {showSyncModal && (
        <div className="sync-modal-backdrop" onClick={() => setShowSyncModal(false)}>
          <div className="sync-modal-dialog" onClick={(e) => e.stopPropagation()}>
            <div className="sync-modal-header">
              <h3 className="sync-modal-title">
                <span>📊</span>
                <span>Automatic Scheme Update Pipeline Logs</span>
              </h3>
              <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
                <button
                  type="button"
                  className="sync-btn-sync-now"
                  onClick={handleRetrySync}
                  disabled={retryingSync || isSyncing}
                >
                  <span>{retryingSync ? "⏳ Retrying..." : "🔄 Retry Failed Sources"}</span>
                </button>
                <button className="close-btn" onClick={() => setShowSyncModal(false)}>✕</button>
              </div>
            </div>
            <div className="sync-modal-body">
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "12px", flexWrap: "wrap", gap: "8px" }}>
                <span style={{ fontSize: "0.85rem", color: "var(--text-muted)" }}>
                  Verified Official Government Catalogs Synchronization History
                </span>
                <button
                  type="button"
                  className="btn-secondary"
                  style={{ fontSize: "0.78rem", padding: "4px 10px" }}
                  onClick={fetchSyncLogs}
                  disabled={syncLogsLoading}
                >
                  {syncLogsLoading ? "Loading..." : "🔄 Refresh Logs"}
                </button>
              </div>

              {syncLogs.length === 0 ? (
                <div style={{ padding: "30px", textAlign: "center", color: "var(--text-muted)" }}>
                  No execution logs recorded yet. Click "Sync Now" to trigger the first run.
                </div>
              ) : (
                <table className="sync-logs-table">
                  <thead>
                    <tr>
                      <th>Source</th>
                      <th>Type</th>
                      <th>Status</th>
                      <th>Discovered</th>
                      <th>Created</th>
                      <th>Updated</th>
                      <th>Time</th>
                    </tr>
                  </thead>
                  <tbody>
                    {syncLogs.map((log) => (
                      <tr key={log.id}>
                        <td>
                          <strong>{log.source_name}</strong>
                          {log.error_message && (
                            <div style={{ fontSize: "0.74rem", color: "#ef4444", marginTop: "2px" }}>
                              ⚠️ {log.error_message}
                            </div>
                          )}
                        </td>
                        <td><span style={{ textTransform: "uppercase", fontSize: "0.72rem", background: "var(--bg-secondary)", padding: "2px 6px", borderRadius: "4px" }}>{log.source_type}</span></td>
                        <td>
                          <span className={`sync-status-badge ${log.status === "SUCCESS" ? "active" : log.status === "RUNNING" ? "running" : "failed"}`}>
                            {log.status}
                          </span>
                        </td>
                        <td>{log.schemes_discovered}</td>
                        <td><span style={{ color: log.schemes_created > 0 ? "#10b981" : "inherit" }}>+{log.schemes_created}</span></td>
                        <td><span style={{ color: log.schemes_updated > 0 ? "#0284c7" : "inherit" }}>{log.schemes_updated}</span></td>
                        <td style={{ fontSize: "0.75rem", color: "var(--text-dim)" }}>
                          {log.completed_at ? new Date(log.completed_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : "Running"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </div>
        </div>
      )}

      {/* 7. MODAL: SCHEME REVISION HISTORY & AUDIT TRAIL */}
      {showHistoryModal && (
        <div className="sync-modal-backdrop" onClick={() => setShowHistoryModal(false)}>
          <div className="sync-modal-dialog" onClick={(e) => e.stopPropagation()}>
            <div className="sync-modal-header">
              <h3 className="sync-modal-title">
                <span>📜</span>
                <span>Revision History: {historyTargetScheme?.hindi_name || historyTargetScheme?.scheme_name}</span>
              </h3>
              <button className="close-btn" onClick={() => setShowHistoryModal(false)}>✕</button>
            </div>
            <div className="sync-modal-body">
              <div style={{ marginBottom: "14px", fontSize: "0.82rem", color: "var(--text-muted)" }}>
                Canonical ID: <code style={{ fontWeight: 700, color: "var(--accent)" }}>{historyTargetScheme?.scheme_id || historyTargetScheme?.id}</code> • Audit trail of verified government changes
              </div>

              {historyLoading ? (
                <div style={{ padding: "30px", textAlign: "center", color: "var(--text-muted)" }}>
                  ⏳ Loading historical revisions...
                </div>
              ) : schemeHistoryList.length === 0 ? (
                <div style={{ padding: "30px", textAlign: "center", color: "var(--text-muted)" }}>
                  Initial baseline record verified. No post-registration revisions detected yet.
                </div>
              ) : (
                <div>
                  {schemeHistoryList.map((entry) => (
                    <div key={entry.id} className="sync-history-item">
                      <div className="sync-history-header">
                        <span className={`sync-history-type ${entry.change_type}`}>
                          {entry.change_type}
                        </span>
                        <span style={{ fontSize: "0.76rem", color: "var(--text-dim)" }}>
                          📅 {entry.recorded_at ? new Date(entry.recorded_at).toLocaleString() : ""}
                        </span>
                      </div>
                      {entry.source_url && (
                        <div style={{ fontSize: "0.76rem", color: "var(--text-muted)", marginBottom: "6px" }}>
                          Source: <a href={entry.source_url} target="_blank" rel="noreferrer">{entry.source_url}</a>
                        </div>
                      )}
                      {entry.changed_fields && entry.changed_fields.length > 0 && (
                        <div>
                          <span style={{ fontSize: "0.76rem", fontWeight: 700, color: "var(--text-main)" }}>Changed Fields:</span>
                          {entry.changed_fields.map((diff, i) => (
                            <div key={i} className="sync-diff-tag">
                              <strong>{diff.field}:</strong> <span style={{ color: "#ef4444" }}>{String(diff.old).slice(0, 80)}</span> ➔ <span style={{ color: "#10b981" }}>{String(diff.new).slice(0, 80)}</span>
                            </div>
                          ))}
                        </div>
                      )}
                      {entry.previous_hash && entry.new_hash && (
                        <div style={{ fontSize: "0.72rem", color: "var(--text-dim)", marginTop: "6px", fontFamily: "monospace" }}>
                          Hash: {entry.previous_hash.slice(0, 10)}... ➔ {entry.new_hash.slice(0, 10)}...
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
