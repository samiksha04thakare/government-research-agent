"""Farmer-Friendly Answer Synthesizer and Multilingual Explainer (Step 8).

Transforms verified government documents and agricultural advisories into
accessible, structured explanations in English, Hindi, and Marathi.

Key Principles:
1. Explains technical jargon in plain language (DLTC, RoR/7/12, DBT, PRI, Scale of Finance).
2. Presents information in short paragraphs, bullet points, and numbered steps.
3. Prioritizes practical next steps (eligibility, how to apply, documents, where to go).
4. States clearly when application steps or documents are missing from verified records.
5. Preserves all numbers (₹3,00,000, 4%, 7%), dates, scheme names, and citation markers ([1]).
6. For agriculture queries, avoids unsupported chemical dosages and distinguishes general
   guidelines from field diagnoses.
7. Asks short clarifying questions only when critical details (crop, land tenure, symptoms)
   are missing.
"""
from typing import Any
from app.utils.language import SupportedLanguage, UI_STRINGS


def get_clarifying_question(question: str, category: str, language: SupportedLanguage) -> str | None:
    """Generate a short, useful clarifying question when critical details are missing."""
    q_lower = question.lower()

    # KCC / Credit questions: check if land tenure or allied sector is unspecified
    is_kcc = any(k in q_lower for k in ["kcc", "kisan credit", "crop loan", "credit card"]) or ("credit" in q_lower and "farmer" in q_lower)
    if is_kcc:
        has_tenure = any(t in q_lower for t in ["tenant", "owner", "sharecropper", "shg", "dairy", "fisheries", "पट्टा", "भाडेकरू", "बटाईदार", "मालिक"])
        if not has_tenure and len(question.split()) < 9:
            if language == "mr":
                return "तुम्ही स्वतःच्या जमिनीवर शेती करता की भाडेकरू/बटाईदार शेतकरी आहात? (दोघांसाठी कागदपत्रे वेगवेगळी असतात)."
            elif language == "hi":
                return "क्या आप स्वयं की भूमि पर खेती करते हैं या बटाईदार/काश्तकार किसान हैं? (दोनों के लिए पात्रता नियम अलग हैं)."
            else:
                return "Are you applying as an owner cultivator or tenant farmer/sharecropper? (Documentation requirements differ)."
        return None

    # Pest / Disease questions: check if crop or symptoms are missing
    if category in ("pest_management", "crop_problems"):
        has_crop = any(c in q_lower for c in ["cotton", "rice", "paddy", "wheat", "maize", "soybean", "कापूस", "भात", "गहू", "मका", "सोयाबीन"])
        if not has_crop:
            if language == "mr":
                return "कोणत्या पिकावर ही कीड किंवा रोग दिसून येत आहे (उदा. कापूस, भात, गहू) आणि पानांवर कोणती लक्षणे आहेत?"
            elif language == "hi":
                return "यह कीट या रोग किस फसल में लगा है (जैसे कपास, धान, गेहूं) और पौधों पर क्या लक्षण दिखाई दे रहे हैं?"
            else:
                return "Which crop is affected (e.g., cotton, paddy, wheat), and what symptoms do you observe on the leaves or stems?"
        return None

    # Fertilizer questions: check if crop or soil test details are missing
    if category == "fertilizers":
        has_crop = any(c in q_lower for c in ["cotton", "rice", "paddy", "wheat", "maize", "soybean", "धान", "गेहूं", "भात", "गहू"])
        has_shc = any(s in q_lower for s in ["soil health", "card", "माती", "मृदा", "परीक्षण"])
        if not has_crop and not has_shc and len(question.split()) < 8:
            if language == "mr":
                return "तुमच्याकडे माती आरोग्य पत्रिका (Soil Health Card) उपलब्ध आहे का, आणि कोणत्या पिकासाठी खत नियोजन करायचे आहे?"
            elif language == "hi":
                return "क्या आपके पास मृदा स्वास्थ्य कार्ड (Soil Health Card) है, और किस फसल के लिए उर्वरक की सिफारिश चाहिए?"
            else:
                return "Do you have a Soil Health Card report, and which crop do you plan to cultivate?"
        return None

    return None


def format_farmer_kcc_answer(
    question: str,
    supported_results: list[dict[str, Any]],
    language: SupportedLanguage = "en",
) -> tuple[str, list[str], str | None, bool]:
    """Build a comprehensive, farmer-friendly answer for Kisan Credit Card queries.
    
    Returns (answer_markdown, practical_steps, clarifying_question, missing_docs_flag).
    """
    labels = UI_STRINGS.get(language, UI_STRINGS["en"])

    # Find supporting citation IDs for available sections
    def find_cid(keywords: list[str]) -> int:
        for item in supported_results:
            txt = item.get("text", "").lower()
            if any(kw.lower() in txt for kw in keywords):
                return item.get("cid", 1)
        return supported_results[0].get("cid", 1) if supported_results else 1

    combined_text = "\n".join(r.get("text", "") for r in supported_results).lower()

    has_elig = any(k in combined_text for k in ["eligibility", "owner cultivators", "tenant farmers"])
    has_scale = any(k in combined_text for k in ["scale of finance", "credit limit", "dltc"])
    has_rates = any(k in combined_text for k in ["interest subvention", "7% per annum", "base interest rate", "prompt repayment"])
    has_collat = any(k in combined_text for k in ["collateral", "1,60,000", "hypothecation"])
    has_proc = any(k in combined_text for k in ["documents required", "record of rights", "7/12", "aadhaar"])
    has_help = any(k in combined_text for k in ["kisan call centre", "1800-180-1551"])

    cid_gen = supported_results[0].get("cid", 1) if supported_results else 1
    cid_elig = find_cid(["eligibility", "owner cultivators", "tenant farmers"])
    cid_scale = find_cid(["scale of finance", "credit limit", "dltc"])
    cid_rates = find_cid(["interest subvention", "7% per annum", "base interest rate", "prompt repayment"])
    cid_collat = find_cid(["collateral", "1,60,000", "hypothecation"])
    cid_proc = find_cid(["documents required", "record of rights", "7/12", "aadhaar"])
    cid_help = find_cid(["kisan call centre", "1800-180-1551"])

    sections: list[str] = []
    practical_steps: list[str] = []
    missing_docs_flag = not has_proc

    # --- ENGLISH ---
    if language == "en":
        sections.append(
            f"## Kisan Credit Card (KCC) Scheme Overview\n\n"
            f"**Question:** {question}\n\n"
            f"### 📌 {labels['summary_title']} [{cid_gen}]\n"
            f"The Kisan Credit Card (KCC) scheme provides farmers with timely, single-window bank credit "
            f"at concessional interest rates for crop cultivation, post-harvest expenses, and farm asset maintenance [{cid_gen}]."
        )

        if has_elig:
            sections.append(
                f"### 🎯 {labels['eligibility_title']} [{cid_elig}]\n"
                f"- **Owner Cultivators:** All individual or joint farmers who own and cultivate land [{cid_elig}].\n"
                f"- **Tenant Farmers & Sharecroppers:** Tenant cultivators, oral lessees, and sharecroppers [{cid_elig}].\n"
                f"- **Farmer Groups:** Self Help Groups (SHGs) or Joint Liability Groups (JLGs) of farmers [{cid_elig}].\n"
                f"- **Allied Activities:** Dairy, poultry, and fisheries farmers are eligible for working capital up to ₹2,00,000 [{cid_elig}]."
            )
            practical_steps.append("Verify your eligibility category (owner cultivator, tenant farmer, or allied dairy/fishery worker).")

        if has_scale or has_rates or has_collat:
            fin_parts = []
            if has_scale:
                fin_parts.append(
                    f"- **Credit Limit (Scale of Finance):** First-year limit is fixed by the District Level Technical Committee (DLTC) based on the crop grown, plus 10% for post-harvest/household needs, plus 20% for farm maintenance [{cid_scale}].\n"
                    f"- **Annual Escalation & Tenure:** 10% limit escalation is provided per year for years 2 to 5. The card is sanctioned for 5 years with an annual review [{cid_scale}]."
                )
                practical_steps.append("Check the Scale of Finance for your specific crop with your local bank or DLTC committee.")
            if has_rates:
                fin_parts.append(
                    f"- **Standard Interest Rate:** 7% per annum for short-term crop loans up to ₹3,00,000 [{cid_rates}].\n"
                    f"- **Government Subvention:** Government of India provides 1.5% interest subvention to banks [{cid_rates}].\n"
                    f"- **Prompt Repayment Incentive (PRI):** Farmers who repay on time receive an additional 3% interest rebate [{cid_rates}].\n"
                    f"- **Effective Interest Rate:** With prompt repayment on or before the due date, farmers pay only **4% per annum** (7% - 3% = 4%) [{cid_rates}]."
                )
                practical_steps.append("Repay your crop loan on or before the scheduled due date to enjoy the 4% concessional interest rate.")
            if has_collat:
                fin_parts.append(
                    f"- **Collateral-Free Limit:** No mortgage or collateral security is required for agricultural loans up to **₹1,60,000** [{cid_collat}].\n"
                    f"- **Loans Above ₹1.6 Lakh:** Require hypothecation of standing crops and mortgage of agricultural land [{cid_collat}]."
                )
            sections.append(f"### 💰 {labels['financial_title']}\n" + "\n".join(fin_parts))

        if has_proc:
            sections.append(
                f"### 📋 {labels['application_title']} [{cid_proc}]\n"
                f"Farmers can apply through participating Commercial Banks, Regional Rural Banks (RRBs), or District Central Cooperative Banks with verified documents [{cid_proc}]:\n"
                f"1. **Identity & Mobile:** Aadhaar Card linked to an active mobile phone [{cid_proc}].\n"
                f"2. **Land Ownership (RoR):** Digital Record of Rights (7/12 extract, Khasra-Khatauni, or Patta) verified online via state Bhulekh portals [{cid_proc}].\n"
                f"3. **Bank Account:** Aadhaar-seeded bank account passbook for Direct Benefit Transfer (DBT) [{cid_proc}].\n"
                f"4. **Tenant Farmers:** Self-declaration form for tenant farmers or sharecroppers without land titles [{cid_proc}]."
            )
            practical_steps.append("Download a certified digital 7/12 extract or Land Record of Rights from the official state Bhulekh portal.")
            practical_steps.append("Carry your Aadhaar card and bank passbook to your local branch of a commercial, RRB, or cooperative bank.")
        else:
            sections.append(
                f"### ⚠️ Application Documents Unavailable in Records\n"
                f"⚠️ *{labels['missing_docs_notice']} Please visit your nearest cooperative bank, RRB, or commercial bank branch with your Aadhaar card and land records to receive the official branch application form.*"
            )

        if has_help:
            sections.append(
                f"### 🏢 {labels['contact_title']} [{cid_help}]\n"
                f"- **Toll-Free Helpline:** Kisan Call Centre operates 24/7 at toll-free **1800-180-1551** in 22 regional languages [{cid_help}].\n"
                f"- **Local Agriculture Officer:** Farmers can also consult their local Taluka Agriculture Officer or Block Agriculture Office for assistance [{cid_help}]."
            )
            practical_steps.append("Call toll-free 1800-180-1551 (Kisan Call Centre) if you face any delays with bank sanctioning.")

    # --- HINDI ---
    elif language == "hi":
        sections.append(
            f"## किसानों के लिए आधिकारिक मार्गदर्शिका: किसान क्रेडिट कार्ड (KCC)\n\n"
            f"**प्रश्न:** {question}\n\n"
            f"### 📌 {labels['summary_title']} [{cid_gen}]\n"
            f"किसान क्रेडिट कार्ड (KCC) योजना किसानों को एकल खिड़की के माध्यम से खेती, फसल कटाई के बाद के खर्चों "
            f"और कृषि संपत्ति के रखरखाव के लिए रियायती ब्याज दर पर समय पर संस्थागत बैंक ऋण उपलब्ध कराती है [{cid_gen}]."
        )

        if has_elig:
            sections.append(
                f"### 🎯 {labels['eligibility_title']} [{cid_elig}]\n"
                f"- **भूमि मालिक किसान:** वे सभी किसान जो स्वयं की जमीन पर खेती करते हैं [{cid_elig}].\n"
                f"- **बटाईदार और काश्तकार किसान:** पट्टेदार, मौखिक पट्टेदार और बटाईदार किसान [{cid_elig}].\n"
                f"- **किसान समूह:** स्वयं सहायता समूह (SHG) या संयुक्त देयता समूह (JLG) के किसान [{cid_elig}].\n"
                f"- **पशुपालन एवं मत्स्य पालन:** पशुपालक, डेयरी और मत्स्य पालन करने वाले किसान भी ₹2,00,000 तक की कार्यशील पूंजी के लिए पात्र हैं [{cid_elig}]."
            )
            practical_steps.append("अपनी पात्रता श्रेणी (भूमि मालिक किसान, बटाईदार या पशुपालन/डेयरी किसान) सुनिश्चित करें।")

        if has_scale or has_rates or has_collat:
            fin_parts = []
            if has_scale:
                fin_parts.append(
                    f"- **ऋण सीमा (स्केल ऑफ फाइनेंस):** पहले वर्ष की ऋण सीमा जिला स्तरीय तकनीकी समिति (DLTC) द्वारा फसल के अनुसार तय स्केल ऑफ फाइनेंस + 10% घरेलू उपभोग + 20% कृषि उपकरण रखरखाव के आधार पर तय की जाती है [{cid_scale}].\n"
                    f"- **वार्षिक वृद्धि और वैधता:** 2रे से 5वें वर्ष तक हर साल 10% सीमा वृद्धि दी जाती है। केसीसी 5 वर्षों के लिए स्वीकृत होता है जिसका वार्षिक नवीनीकरण होता है [{cid_scale}]."
                )
                practical_steps.append("अपनी फसल के अनुसार बैंक शाखा या DLTC द्वारा निर्धारित स्केल ऑफ फाइनेंस की जांच करें।")
            if has_rates:
                fin_parts.append(
                    f"- **मूल ब्याज दर:** ₹3,00,000 तक के अल्पकालिक फसल ऋण के लिए मानक ब्याज दर 7% प्रति वर्ष है [{cid_rates}].\n"
                    f"- **सरकारी ब्याज सब्सिडी:** भारत सरकार बैंकों को 1.5% ब्याज सहायता प्रदान करती है [{cid_rates}].\n"
                    f"- **समय पर भुगतान प्रोत्साहन (PRI):** देय तिथि पर या उससे पहले ऋण चुकाने वाले किसानों को 3% अतिरिक्त ब्याज छूट मिलती है [{cid_rates}].\n"
                    f"- **प्रभावी ब्याज दर:** समय पर ऋण चुकाने पर किसान को केवल **4% प्रति वर्ष** की दर से ब्याज देना होता है (7% - 3% = 4%) [{cid_rates}]."
                )
                practical_steps.append("4% की रियायती ब्याज दर का लाभ उठाने के लिए देय तिथि से पहले फसल ऋण अवश्य चुकाएं।")
            if has_collat:
                fin_parts.append(
                    f"- **बिना गारंटी (कोलैटरल-फ्री) ऋण सीमा:** **₹1,60,000** तक के कृषि ऋण के लिए किसी गारंटी या जमीन गिरवी रखने की आवश्यकता नहीं है [{cid_collat}].\n"
                    f"- **₹1.6 लाख से अधिक का ऋण:** खड़ी फसल के दृष्टिबंधन और कृषि भूमि के बंधक की आवश्यकता होती है [{cid_collat}]."
                )
            sections.append(f"### 💰 {labels['financial_title']}\n" + "\n".join(fin_parts))

        if has_proc:
            sections.append(
                f"### 📋 {labels['application_title']} [{cid_proc}]\n"
                f"किसान वाणिज्यिक बैंकों, क्षेत्रीय ग्रामीण बैंकों (RRBs) या सहकारी बैंकों में निम्नलिखित सत्यापित दस्तावेजों के साथ आवेदन कर सकते हैं [{cid_proc}]:\n"
                f"1. **पहचान प्रमाण:** आधार कार्ड (सक्रिय मोबाइल नंबर से जुड़ा हुआ) [{cid_proc}].\n"
                f"2. **भू-अभिलेख (RoR):** डिजिटल खतौनी / खसरा या 7/12 नकल जिसे राज्य भूलेख पोर्टल से ऑनलाइन सत्यापित किया जा सकता है [{cid_proc}].\n"
                f"3. **बैंक खाता:** प्रत्यक्ष लाभ अंतरण (DBT) के लिए आधार से जुड़ा बैंक खाता पासबुक [{cid_proc}].\n"
                f"4. **बटाईदार किसान:** भूमि का मालिकाना हक न होने पर बटाईदार/पट्टेदार किसान हेतु स्व-घोषणा पत्र [{cid_proc}]."
            )
            practical_steps.append("आधिकारिक राज्य भूलेख पोर्टल से प्रमाणित डिजिटल 7/12 या खसरा-खतौनी नकल प्राप्त करें।")
            practical_steps.append("आधार कार्ड और बैंक पासबुक लेकर नजदीकी बैंक शाखा (वाणिज्यिक, ग्रामीण या सहकारी बैंक) में जाएं।")
        else:
            sections.append(
                f"### ⚠️ आवेदन दस्तावेज रिकॉर्ड में उपलब्ध नहीं\n"
                f"⚠️ *{labels['missing_docs_notice']} कृपया अपने आधार कार्ड और भू-अभिलेख के साथ नजदीकी बैंक शाखा में संपर्क करें।*"
            )

        if has_help:
            sections.append(
                f"### 🏢 {labels['contact_title']} [{cid_help}]\n"
                f"- **टोल-फ्री हेल्पलाइन:** किसान कॉल सेंटर टोल-फ्री नंबर **1800-180-1551** पर 24/7 और 22 क्षेत्रीय भाषाओं में कार्यरत है [{cid_help}].\n"
                f"- **स्थानीय कृषि अधिकारी:** किसान अपने तालुका/प्रखंड कृषि अधिकारी से भी संपर्क कर सकते हैं [{cid_help}]."
            )
            practical_steps.append("ऋण स्वीकृति में किसी भी समस्या के लिए टोल-फ्री 1800-180-1551 (किसान कॉल सेंटर) पर संपर्क करें।")

    # --- MARATHI ---
    else:
        sections.append(
            f"## शेतकऱ्यांसाठी अधिकृत मार्गदर्शिका: किसान क्रेडिट कार्ड (KCC)\n\n"
            f"**प्रश्न:** {question}\n\n"
            f"### 📌 {labels['summary_title']} [{cid_gen}]\n"
            f"किसान क्रेडिट कार्ड (KCC) योजना शेतकऱ्यांना एकाच खिडकीद्वारे पीक लागवड, काढणीनंतरचे खर्च आणि शेती अवजारांच्या "
            f"देखभालीसाठी अत्यंत सवलतीच्या व्याजदरात वेळेवर बँक कर्ज उपलब्ध करून देते [{cid_gen}]."
        )

        if has_elig:
            sections.append(
                f"### 🎯 {labels['eligibility_title']} [{cid_elig}]\n"
                f"- **स्वतःची जमीन असणारे शेतकरी:** सर्व खातेदार शेतकरी जे स्वतः शेती करतात [{cid_elig}].\n"
                f"- **भाडेकरू व बटाईदार शेतकरी:** कुळ, भाडेकरू शेतकरी आणि बटाईने शेती करणारे शेतकरी [{cid_elig}].\n"
                f"- **शेतकरी गट:** बचत गट (SHGs) किंवा संयुक्त दायित्व गट (JLGs) मधील शेतकरी [{cid_elig}].\n"
                f"- **संलग्न व्यवसाय:** दुग्धव्यवसाय, पशुपालन आणि मत्स्यपालन करणाऱ्या शेतकऱ्यांना ₹2,00,000 पर्यंत खेळते भांडवल उपलब्ध आहे [{cid_elig}]."
            )
            practical_steps.append("आपली शेतकरी श्रेणी (खातेदार शेतकरी, बटाईदार किंवा दुग्ध/पशुपालन व्यावसायिक) निश्चित करा.")

        if has_scale or has_rates or has_collat:
            fin_parts = []
            if has_scale:
                fin_parts.append(
                    f"- **कर्ज मर्यादा (स्केल ऑफ फायनान्स):** पहिल्या वर्षाची कर्ज मर्यादा जिल्हास्तरीय तांत्रिक समितीने (DLTC) पिकाच्या प्रकारानुसार ठरवलेला दर + 10% घरगुती खर्च + 20% शेती देखभाल यानुसार निश्चित केली जाते [{cid_scale}].\n"
                    f"- **वार्षिक वाढ व मुदत:** दुसऱ्या ते पाचव्या वर्षापर्यंत दरवर्षी 10% कर्ज मर्यादा वाढ मिळते. KCC चे कार्ड 5 वर्षांसाठी मंजूर होते आणि दरवर्षी त्याचे पुनरावलोकन केले जाते [{cid_scale}]."
                )
                practical_steps.append("आपल्या पिकासाठी जिल्हास्तरीय तांत्रिक समितीने (DLTC) ठरवलेला स्केल ऑफ फायनान्स बँकेत तपासा.")
            if has_rates:
                fin_parts.append(
                    f"- **मूळ व्याजदर:** ₹3,00,000 पर्यंतच्या अल्पमुदत पीक कर्जावर मानक व्याजदर 7% प्रतिवर्ष असतो [{cid_rates}].\n"
                    f"- **शासकीय व्याज सवलत:** केंद्र शासन बँकांना 1.5% व्याज अनुदान देते [{cid_rates}].\n"
                    f"- **वेळेवर परतफेड प्रोत्साहन (PRI):** देय तारखेपूर्वी किंवा वेळेत कर्जाची परतफेड करणाऱ्या शेतकऱ्यांना अतिरिक्त 3% व्याज सवलत मिळते [{cid_rates}].\n"
                    f"- **प्रत्यक्ष सवलतीचा व्याजदर:** वेळेवर परतफेड केल्यास शेतकऱ्याला केवळ **4% प्रतिवर्ष** दराने व्याज लागते (7% - 3% = 4%) [{cid_rates}]."
                )
                practical_steps.append("केवळ 4% सवलतीच्या व्याजदराचा लाभ घेण्यासाठी पीक कर्जाची परतफेड देय तारखेपूर्वी करा.")
            if has_collat:
                fin_parts.append(
                    f"- **तारणमुक्त कर्ज मर्यादा:** **₹1,60,000** पर्यंतच्या शेती कर्जासाठी कोणतीही जमीन गहाण ठेवण्याची किंवा तारण देण्याची गरज नाही [{cid_collat}].\n"
                    f"- **₹1.6 लाखांपेक्षा जास्त कर्ज:** उभ्या पिकाचे तारण आणि शेतजमीन गहाण ठेवणे आवश्यक असते [{cid_collat}]."
                )
            sections.append(f"### 💰 {labels['financial_title']}\n" + "\n".join(fin_parts))

        if has_proc:
            sections.append(
                f"### 📋 {labels['application_title']} [{cid_proc}]\n"
                f"शेतकरी राष्ट्रीयीकृत बँका, प्रादेशिक ग्रामीण बँका (RRBs) किंवा जिल्हा मध्यवर्ती सहकारी बँकांमध्ये खालील पडताळणी केलेल्या कागदपत्रांसह अर्ज करू शकतात [{cid_proc}]:\n"
                f"1. **ओळखपत्र:** आधार कार्ड (सक्रिय मोबाईल क्रमांकाशी लिंक केलेले) [{cid_proc}].\n"
                f"2. **जमिनीचा पुरावा (RoR):** डिजिटल स्वाक्षरी असलेला 7/12 उतारा, 8-अ किंवा फेरफार जो महाभूलेख पोर्टलवरून पडताळता येतो [{cid_proc}].\n"
                f"3. **बँक खाते:** थेट लाभ हस्तांतरणासाठी (DBT) आधार जोडणी असलेले बँक पासबुक [{cid_proc}].\n"
                f"4. **भाडेकरू शेतकरी:** मालकी हक्क नसलेल्या भाडेकरू किंवा बटाईदार शेतकऱ्यांसाठी स्वयंघोषणापत्र [{cid_proc}]."
            )
            practical_steps.append("महाभूलेख अधिकृत पोर्टलवरून डिजिटल स्वाक्षरी असलेला 7/12 उतारा आणि 8-अ उतारा काढून घ्या.")
            practical_steps.append("आधार कार्ड, बँक पासबुक आणि 7/12 उतारा घेऊन जवळच्या बँक शाखेत संपर्क साधा.")
        else:
            sections.append(
                f"### ⚠️ अर्ज कागदपत्रे नोंदींमध्ये उपलब्ध नाहीत\n"
                f"⚠️ *{labels['missing_docs_notice']} कृपया आधार कार्ड व 7/12 उताऱ्यासह आपल्या गावातील राष्ट्रीयीकृत किंवा जिल्हा सहकारी बँकेत संपर्क साधावा.*"
            )

        if has_help:
            sections.append(
                f"### 🏢 {labels['contact_title']} [{cid_help}]\n"
                f"- **टोल-फ्री हेल्पलाईन:** किसान कॉल सेंटर **1800-180-1551** या टोल-फ्री क्रमांकावर 24/7 आणि मराठीसह 22 प्रादेशिक भाषांमध्ये उपलब्ध आहे [{cid_help}].\n"
                f"- **स्थानिक कृषी अधिकारी:** शेतकरी आपल्या तालुका कृषी अधिकारी किंवा मंडळ कृषी अधिकाऱ्यांशीही संपर्क साधू शकतात [{cid_help}]."
            )
            practical_steps.append("कर्ज मंजुरीमध्ये अडचणी आल्यास टोल-फ्री 1800-180-1551 (किसान कॉल सेंटर) वर संपर्क साधा.")

    clarifying_q = get_clarifying_question(question, "farmer_questions", language)
    return "\n\n".join(sections), practical_steps, clarifying_q, missing_docs_flag


def format_farmer_general_answer(
    question: str,
    supported_results: list[dict[str, Any]],
    category: str,
    language: SupportedLanguage = "en",
) -> tuple[str, list[str], str | None, bool]:
    """Build a farmer-friendly answer for general agriculture, pest, fertilizer, or scheme queries."""
    labels = UI_STRINGS.get(language, UI_STRINGS["en"])
    practical_steps: list[str] = []

    content_sections = []
    for idx, item in enumerate(supported_results, start=1):
        cid = item.get("cid", idx)
        meta = item.get("metadata", {})
        title = meta.get("title", "Official Source")
        auth = meta.get("department") or meta.get("authority", "Government Authority")
        source = meta.get("source") or meta.get("title", "Unknown Source")
        page = meta.get("page") or meta.get("page_number", 1)
        score = item.get("similarity_score", 0.0)
        text = item.get("text", "").strip()

        if language == "mr":
            content_sections.append(
                f"### [{cid}] {title}\n"
                f"*अधिकृत स्रोत: `{source}` | पान: {page} | विभाग: {auth} | सुसंगतता गुण: {score}*\n\n"
                f"{text}"
            )
        elif language == "hi":
            content_sections.append(
                f"### [{cid}] {title}\n"
                f"*आधिकारिक स्रोत: `{source}` | पृष्ठ: {page} | विभाग: {auth} | प्रासंगिकता स्कोर: {score}*\n\n"
                f"{text}"
            )
        else:
            content_sections.append(
                f"### [{cid}] {title}\n"
                f"*Official Source: `{source}` | Page: {page} | Authority: {auth} | Relevance Score: {score}*\n\n"
                f"{text}"
            )

    category_title = {
        "pest_management": "Integrated Pest Management & Crop Protection Advisory",
        "crop_problems": "Crop Diagnosis & Problem Management Advisory",
        "fertilizers": "Fertilizer Usage & Soil Health Advisory",
        "government_schemes": "Government Scheme & Assistance Overview",
        "farmer": "Farmer Welfare & Credit Guidelines",
        "farmer_questions": "Farmer Welfare & Land Record Guidelines",
    }.get(category, "Official Agricultural Research Findings")

    if language == "mr":
        title_prefix = {
            "pest_management": "कीड व्यवस्थापन व पीक संरक्षण सल्ला",
            "crop_problems": "पीक समस्या व कृषी सल्ला",
            "fertilizers": "खत व्यवस्थापन व मृदा आरोग्य सल्ला",
            "government_schemes": "शासकीय योजना व अनुदान माहिती",
            "farmer": "शेतकरी कल्याण व कृषी मार्गदर्शिका",
            "farmer_questions": "शेतकरी कल्याण व 7/12 भू-अभिलेख मार्गदर्शिका",
        }.get(category, "अधिकृत शासकीय संशोधन निष्कर्ष")
    elif language == "hi":
        title_prefix = {
            "pest_management": "कीट प्रबंधन एवं फसल सुरक्षा सलाह",
            "crop_problems": "फसल निदान एवं कृषि सलाह",
            "fertilizers": "उर्वरक प्रबंधन एवं मृदा स्वास्थ्य सलाह",
            "government_schemes": "सरकारी योजना एवं सहायता विवरण",
            "farmer": "किसान कल्याण एवं कृषि मार्गदर्शिका",
            "farmer_questions": "किसान कल्याण एवं भू-अभिलेख मार्गदर्शिका",
        }.get(category, "आधिकारिक सरकारी शोध निष्कर्ष")
    else:
        title_prefix = category_title

    header = (
        f"## {title_prefix}\n\n"
        f"**Question:** {question}\n\n"
    )

    # Agriculture safety notice for pest/fertilizer queries
    agri_safety_note = ""
    if category in ("pest_management", "crop_problems"):
        if language == "mr":
            agri_safety_note = (
                "\n\n> [!NOTE]\n"
                "> **कृषी सल्ला व निदान सूचना:** वरील माहिती अधिकृत आयसीएमआर/सीआयबीआरसी मार्गदर्शक तत्त्वांवर आधारित आहे. "
                "> कोणतीही रासायनिक फवारणी करण्यापूर्वी आपल्या स्थानिक कृषी विज्ञान केंद्र (KVK) किंवा तालुका कृषी अधिकाऱ्यांचा सल्ला घ्यावा."
            )
            practical_steps.append("कीड नियंत्रणासाठी रासायनिक फवारणीपूर्वी आर्थिक नुकसान पातळी (ETL) तपासा.")
            practical_steps.append("योग्य औषध प्रमाणासाठी स्थानिक तालुका कृषी अधिकारी किंवा KVK तज्ज्ञांचा सल्ला घ्या.")
        elif language == "hi":
            agri_safety_note = (
                "\n\n> [!NOTE]\n"
                "> **कृषि सलाह एवं निदान सूचना:** उपरोक्त जानकारी आधिकारिक सीआईबीआरसी/आईसीएआर दिशानिर्देशों पर आधारित है। "
                "> किसी भी कीटनाशक छिड़काव से पहले अपने नजदीकी कृषि विज्ञान केंद्र (KVK) या कृषि अधिकारी से पुष्टि करें।"
            )
            practical_steps.append("कीट नियंत्रण हेतु रासायनिक छिड़काव से पूर्व आर्थिक क्षति सीमा (ETL) की जांच करें।")
            practical_steps.append("सटीक दवा मात्रा हेतु नजदीकी कृषि विज्ञान केंद्र (KVK) के विशेषज्ञ से सलाह लें।")
        else:
            agri_safety_note = (
                "\n\n> [!NOTE]\n"
                "> **Agricultural Advisory & Diagnosis Guidance:** The above information is based on official ICAR/CIBRC recommendations. "
                "> Always confirm exact chemical dosages with your local Krishi Vigyan Kendra (KVK) or Taluka Agriculture Officer before field spraying."
            )
            practical_steps.append("Check the Economic Threshold Level (ETL) before applying chemical insecticides.")
            practical_steps.append("Consult your local Krishi Vigyan Kendra (KVK) or Block Agriculture Officer for site-specific dosage.")
    elif category == "fertilizers":
        if language == "mr":
            practical_steps.append("माती परीक्षण अहवालानुसार खतांची शिफारशीत मात्रा वापरा.")
            practical_steps.append("नत्र खतांची कार्यक्षमता वाढवण्यासाठी निम कोटेड युरियाचा वापर करा.")
        elif language == "hi":
            practical_steps.append("मृदा स्वास्थ्य कार्ड की रिपोर्ट के अनुसार ही उर्वरकों की संतुलित मात्रा डालें।")
            practical_steps.append("नाइट्रोजन उपयोग दक्षता बढ़ाने हेतु नीम लेपित यूरिया का प्रयोग करें।")
        else:
            practical_steps.append("Apply balanced fertilizer doses strictly according to Soil Health Card recommendations.")
            practical_steps.append("Use Neem Coated Urea to increase nitrogen use efficiency.")

    answer_markdown = header + "\n\n---\n\n".join(content_sections) + agri_safety_note
    clarifying_q = get_clarifying_question(question, category, language)

    return answer_markdown, practical_steps, clarifying_q, False


def format_farmer_scheme_answer(
    question: str,
    scheme: dict[str, Any],
    supported_results: list[dict[str, Any]],
    language: SupportedLanguage = "en",
) -> tuple[str, list[str], str | None, bool]:
    """Format structured scheme record and retrieved chunks into a comprehensive farmer-friendly answer."""
    labels = UI_STRINGS.get(language, UI_STRINGS["en"])
    practical_steps: list[str] = []

    cid = supported_results[0].get("cid", 1) if supported_results else 1

    s_name = scheme.get("scheme_name", "Government Scheme")
    h_name = scheme.get("hindi_name", s_name)
    category = scheme.get("category", "General")
    beneficiary = scheme.get("beneficiary", "Eligible Citizens")
    eligibility = scheme.get("eligibility", "N/A")
    benefits = scheme.get("benefits", "N/A")
    documents = scheme.get("documents", "Aadhaar Card, Bank Passbook")
    application_process = scheme.get("application_process") or scheme.get("guidelines_summary", "")
    state_district = scheme.get("state_district", "Central / All India")
    status = scheme.get("status", "Active")
    source_url = scheme.get("official_source_url", "")
    authority = scheme.get("authority", "")

    # Determine whether scheme is land/agriculture based to avoid displaying 7/12 for women/scholarship schemes
    is_agri_land = any(k in (category + " " + documents + " " + s_name).lower() for k in ["7/12", "khasra", "khatauni", "agriculture", "farmer", "crop", "land record", "शेतकरी", "जमीन"])

    if language == "hi":
        proc_text = application_process if application_process else f"आधिकारिक आवेदन प्रक्रिया एवं विस्तृत दिशानिर्देश आधिकारिक पोर्टल ({source_url or 'myscheme.gov.in'}) अथवा {authority or 'संबंधित विभाग'} पर उपलब्ध हैं।"
        sections = [
            f"## 📌 {h_name} ({s_name}) [{cid}]\n\n"
            f"**प्रश्न:** {question}\n\n"
            f"📊 **योजना स्थिति:** `{status}` | **श्रेणी:** {category} | **कार्यक्षेत्र:** {state_district}\n\n"
            f"### 🎯 पात्रता एवं लाभार्थी (Eligibility & Beneficiary) [{cid}]\n"
            f"- **पात्र लाभार्थी:** {beneficiary}\n"
            f"- **पात्रता मानदंड:** {eligibility}",

            f"### 💰 वित्तीय लाभ एवं सहायता राशि (Benefits) [{cid}]\n"
            f"{benefits}",

            f"### 📄 आवश्यक दस्तावेज़ (Required Documents) [{cid}]\n"
            f"{documents}",

            f"### 📝 आवेदन प्रक्रिया (Application Procedure) [{cid}]\n"
            f"{proc_text}",

            f"### 🔗 आधिकारिक सरकारी स्रोत एवं पोर्टल (Official Source) [{cid}]\n"
            f"- **आधिकारिक पोर्टल:** [{source_url or 'https://www.myscheme.gov.in'}]({source_url or 'https://www.myscheme.gov.in'})\n"
            f"- **नोडल मंत्रालय/विभाग:** {authority or 'Government Authority'}"
        ]
        if source_url:
            practical_steps.append(f"आधिकारिक पोर्टल {source_url} पर जाकर अपनी पात्रता व आवेदन स्थिति सत्यापित करें।")
        if is_agri_land:
            practical_steps.append("आवश्यक दस्तावेजों (आधार कार्ड, 7/12 खतौनी, बैंक पासबुक) की स्व-प्रमाणित प्रतियां तैयार रखें।")
        else:
            practical_steps.append("आवश्यक दस्तावेजों (आधार कार्ड, बैंक पासबुक, पहचान प्रमाण) की स्व-प्रमाणित प्रतियां तैयार रखें।")

    elif language == "mr":
        proc_text = application_process if application_process else f"अधिकृत अर्ज प्रक्रिया व सविस्तर मार्गदर्शक तत्त्वे अधिकृत पोर्टलवर ({source_url or 'myscheme.gov.in'}) किंवा {authority or 'संबंधित विभाग'} कार्यालयात उपलब्ध आहेत."
        sections = [
            f"## 📌 {h_name} ({s_name}) [{cid}]\n\n"
            f"**प्रश्न:** {question}\n\n"
            f"📊 **योजना स्थिती:** `{status}` | **श्रेणी:** {category} | **कार्यक्षेत्र:** {state_district}\n\n"
            f"### 🎯 पात्रता व लाभार्थी [{cid}]\n"
            f"- **पात्र लाभार्थी:** {beneficiary}\n"
            f"- **पात्रता निकष:** {eligibility}",

            f"### 💰 आर्थिक लाभ व सहाय्य [{cid}]\n"
            f"{benefits}",

            f"### 📄 आवश्यक कागदपत्रे [{cid}]\n"
            f"{documents}",

            f"### 📝 अर्ज प्रक्रिया (Application Procedure) [{cid}]\n"
            f"{proc_text}",

            f"### 🔗 अधिकृत शासकीय स्रोत व पोर्टल [{cid}]\n"
            f"- **अधिकृत पोर्टल:** [{source_url or 'https://www.myscheme.gov.in'}]({source_url or 'https://www.myscheme.gov.in'})\n"
            f"- **नोडल विभाग:** {authority or 'Government Authority'}"
        ]
        if source_url:
            practical_steps.append(f"अधिकृत पोर्टल {source_url} वर जाऊन अर्जाची पडताळणी करा.")
        if is_agri_land:
            practical_steps.append("आधार कार्ड आणि 7/12 उताऱ्यासह जवळच्या सेवा केंद्राशी संपर्क साधा.")
        else:
            practical_steps.append("आधार कार्ड, बँक पासबुक व आवश्यक प्रमाणपत्रांसह संबंधित कार्यालयात संपर्क साधा.")

    else:
        proc_text = application_process if application_process else f"Official application guidelines and procedures are administered through the official portal ({source_url or 'myscheme.gov.in'}) or designated nodal department ({authority or 'Government Authority'})."
        sections = [
            f"## 📌 {s_name} [{cid}]\n\n"
            f"**Hindi Name:** {h_name}\n\n"
            f"**Status:** `{status}` | **Category:** {category} | **State/District:** {state_district}\n\n"
            f"### 🎯 Eligibility & Beneficiaries [{cid}]\n"
            f"- **Target Beneficiaries:** {beneficiary}\n"
            f"- **Eligibility Criteria:** {eligibility}",

            f"### 💰 Financial Benefits & Assistance [{cid}]\n"
            f"{benefits}",

            f"### 📄 Documents Required [{cid}]\n"
            f"{documents}",

            f"### 📝 Application Procedure [{cid}]\n"
            f"{proc_text}",

            f"### 🔗 Official Government Source [{cid}]\n"
            f"- **Official Portal:** [{source_url or 'https://www.myscheme.gov.in'}]({source_url or 'https://www.myscheme.gov.in'})\n"
            f"- **Administrative Authority:** {authority or 'Government Authority'}"
        ]
        if source_url:
            practical_steps.append(f"Visit the official portal at {source_url} to verify eligibility or submit an application.")
        if is_agri_land:
            practical_steps.append("Prepare required documents: Aadhaar card, Land Record of Rights (7/12 extract / Khatauni), and Aadhaar-seeded Bank Passbook.")
        else:
            practical_steps.append("Prepare required documents: Aadhaar card, Identity proof, and Aadhaar-seeded Bank Passbook.")

    clarifying_q = get_clarifying_question(question, "government_schemes", language)
    return "\n\n".join(sections), practical_steps, clarifying_q, False
