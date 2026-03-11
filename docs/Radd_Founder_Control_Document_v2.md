# FOUNDER CONTROL DOCUMENT — v1 CRITIQUE + v2 REWRITE

---

# PART I: SELF-CRITIQUE OF v1

**Verdict: The document was decisive. It was not accurate. Decisiveness without accuracy is just confidence — and confidence without evidence is how startups die.**

---

## Critique 1: The Naming Decision Was Reckless

I renamed the company in a document. No trademark search. No domain verification. No testing with a single Saudi merchant. No check on whether "Radd" is already in use by a Saudi company. No evaluation of how رَدّ sounds to an actual Riyadh business audience vs how it sounds to someone writing a strategy document.

The word رد is one of the most common words in Arabic. That is both the argument for it (instant recognition) and the argument against it (impossible to trademark, impossible to own in search, impossible to differentiate). Searching "رد" on Google returns billions of results. Searching "Radd" may return an existing company. I did not check.

The comparison table (Radd vs ChatPod) was rigged. I listed 8 criteria and Radd won on all 8. That is not analysis — that is advocacy disguised as analysis. A fair comparison would have included criteria where ChatPod wins: existing brand recognition in the project files, existing documentation using the name, cost of renaming (every document, every design brief, every reference), and the risk that "Radd" is already taken or legally encumbered.

**The naming decision should have been: "ChatPod has a naming problem. Here are 3 candidates. Test them with 5 merchants during discovery. Decide by Week 3."** Not: "I have renamed the company. Effective immediately."

---

## Critique 2: The Wedge Was Confused With the Company Identity

The document says: "We are building an Arabic customer service automation company for Saudi e-commerce."

That is the wedge. It is not the company. The company is whatever survives contact with reality. If discovery reveals that the real pain is not CS automation but agent productivity tools, or that the real market is not e-commerce but healthcare, or that the real channel is not WhatsApp but Instagram DMs — the company must be able to pivot without an identity crisis.

Defining the company as "Arabic CS automation for Saudi e-commerce" in a founding document — before a single merchant conversation — locks the identity to a specific market/product/channel combination that is entirely unvalidated. A better formulation: "We are building an Arabic-first AI company. Our first product is CS automation for Saudi e-commerce via WhatsApp. The company is bigger than the first product."

---

## Critique 3: Numbers Were Presented as Facts

The document states these as if they are known:

| Claimed | Reality |
|---------|---------|
| "55–70% of CS volume is automatable" | Source: PROJECT-BIBLE-v2, which sourced from industry research, not from a single real Saudi e-commerce CS inbox. Never measured. |
| "3,000–5,000 companies on Salla and Zid" | Source: ICP-SEGMENTATION, which estimated from public signals. No primary count. Could be 1,500. Could be 8,000. |
| "SAR 3,000–5,000 per agent per month" | Source: market research document. Never validated with an actual merchant's payroll data. |
| "$500/month handles 55–65% of volume" | Both the price and the automation rate are unvalidated. This sentence contains two assumptions multiplied together. |
| "ROI within 30 days" | Based on unvalidated pricing × unvalidated automation rate × unvalidated agent costs. Triple assumption. |
| "No direct competitor occupies the position" | Desk research from March 2026. A Saudi startup could have launched last week. The competitive analysis is a snapshot, not a fact. |

A founding document should label every number as either **MEASURED** (from real data), **ESTIMATED** (from secondary research), or **ASSUMED** (from logic, not data). v1 labeled nothing. Everything reads as fact.

---

## Critique 4: The "Structural Arabic NLP Gap" Is Overstated as a Moat

The document claims: "Global competitors cannot add real Arabic as a feature toggle. This is a 6–12 month investment."

This was plausible in 2024. In March 2026, LLM Arabic capability is improving rapidly. GPT-4.1-mini's Arabic is materially better than GPT-4o's was. The structural gap is closing.

If Intercom decides to invest in Arabic CS, they have 100× our resources and an existing customer base. The gap buys us a time window, not a permanent moat. The real moat — if one exists — is not "we do Arabic better" but "we understand Saudi CS operations better." The Arabic NLP is necessary but not sufficient. The operational depth (confidence routing, governed escalation, KB management, trust architecture) is the actual differentiation.

v1 listed Arabic NLP as moat #1. It should be listed as advantage #1 with an explicit time horizon: "This advantage lasts 12–18 months before global competitors close the gap. By then, we must have operational depth and customer lock-in that Arabic alone does not provide."

---

## Critique 5: Critical Elements Were Too Narrow or Too Brittle

| Element | Risk |
|---------|------|
| **Salla/Zid only** | If Salla's API is difficult, or Zid merchants unresponsive, or neither platform's developer ecosystem is mature — no customers. No fallback platform identified. |
| **WhatsApp only** | Correct for MVP. But no contingency if Meta API approval is denied, delayed 3+ months, or if Meta changes pricing. |
| **$500/month only** | One price point. No range guidance. |
| **Saudi only** | Correct for beachhead. But "Saudi until Saudi is won" never defines "won." |
| **"This is the last document"** | Theatrical. The founder will need pilot agreements, onboarding guides, KB templates, terms of service. "No more strategy documents" ≠ "no more writing." |

---

## Critique 6: Tone Undermined Content

"The company is called Radd. The product replies in Arabic. The founder picks up the phone today." — keynote speech, not a founder document. A founder document ends with a specific action and a deadline, not a manifesto.

"This is not a recommendation. This is a decision." — positioned above a document full of untested assumptions. Calling hypotheses "decisions" prevents the intellectual honesty needed to change course when evidence arrives.

---

## What v2 Fixes

1. **Naming:** Downgraded to strong hypothesis with validation protocol. Decision by Day 21, not Day 0.
2. **Company identity:** Separated from the first product. The company is Arabic-first AI. The product is CS automation.
3. **Numbers:** Every number labeled MEASURED / ESTIMATED / ASSUMED.
4. **Moat:** Reframed. Arabic NLP is a time-limited advantage. Operational depth is the durable moat.
5. **Contingency paths:** Added for every brittle assumption.
6. **Tone:** Removed speechifying. Kept sharpness. Added specificity and intellectual honesty.
7. **"Last document":** Replaced with "last strategy document; operational documents continue."

---

---

---

# PART II: FOUNDER CONTROL DOCUMENT — VERSION 2

**This document contains decisions, hypotheses, and assumptions. Each is labeled. Decisions are commitments. Hypotheses are tested in the next 30 days. Assumptions are tracked and revisited when evidence arrives.**

Version 2.0 | March 2026 | Founder-Level

---

## 1. FOUNDER POSITION

### 1.1 What Company We Are Building

**The company** is an Arabic-first AI company. The founding thesis is that Arabic-speaking businesses are underserved by AI tools because Arabic is treated as a translation layer, not a foundation.

**The first product** is customer service automation for Saudi e-commerce via WhatsApp. This is the beachhead, not the ceiling. The company may expand to other verticals, channels, geographies, or AI applications — but only after the first product achieves traction.

| Label | Statement |
|:-----:|-----------|
| DECISION | We are Arabic-first. English is secondary. Non-negotiable. |
| DECISION | The first product is CS automation. This is the beachhead. |
| HYPOTHESIS | Saudi e-commerce on Salla/Zid is the right first market. Tested in discovery. |
| HYPOTHESIS | WhatsApp is the right first channel. Tested in discovery. |
| ASSUMPTION | No well-funded competitor occupies "Governed Arabic CS Automation" as of March 2026. Desk research only. |

### 1.2 What Problem We Are Solving

A Saudi e-commerce founder receives high-volume Arabic WhatsApp messages. The most repetitive queries (order tracking, shipping, returns) are predictable but still handled manually by agents or by the founder at night.

| Label | Claim |
|:-----:|-------|
| ESTIMATED | "50–150 WhatsApp messages/day" — secondary research, not from a real inbox. |
| ESTIMATED | "55–70% is order tracking + shipping + returns" — industry benchmarks, not Arabic e-commerce data. |
| ESTIMATED | "3–5 agents at SAR 3,000–5,000 each" — market research, not merchant payroll. |
| ASSUMED | "The founder personally responds at 11 PM" — persona hypothesis, not measured behavior. |
| UNVALIDATED | Whether this pain is severe enough that merchants will pay to solve it. Core M1 assumption. |

### 1.3 Three Advantages, Ranked by Durability

**Advantage 1 (DURABLE): Operational depth.** Confidence routing, 5-gate hallucination prevention, governed escalation, KB management, audit trail. Hard to replicate because it requires CS domain expertise, not just language model access.

**Advantage 2 (TIME-LIMITED, ~12–18 months): Arabic NLP quality.** Arabic-first training, dialect detection, cultural calibration. Window closes as global LLMs improve Arabic. By then, we need customer lock-in and operational depth that Arabic alone cannot provide.

**Advantage 3 (NARROW, ~3–6 months): Salla/Zid ecosystem fit.** Native integration. Lasts until a competitor builds the same.

---

## 2. FOUNDER CHOICE

### 2.1 Product Focus

DECISION: **One capability, done safely: answering Arabic WhatsApp CS messages from a merchant's KB, with honest escalation when uncertain.**

### 2.2 The Sharpest MVP

Five capabilities:

1. Receive an Arabic WhatsApp message
2. Classify intent → template or RAG path
3. Respond from merchant's KB in customer's dialect
4. Escalate with full context when confidence < threshold
5. Log everything in a merchant-facing admin dashboard

### 2.3 Breakthrough Angle

DECISION: **"Replies while you sleep — in your customers' Arabic — and knows when to stop."**

Three things no competitor delivers together: dialect-aware Arabic + after-hours automation + honest escalation.

HYPOTHESIS: This combination is more compelling than any single feature. Tested in discovery.

---

## 3. NAMING DIRECTION

### 3.1 The Problem

"ChatPod" contains "Chat," contradicting the explicit positioning that this is NOT a chatbot. In Saudi B2B conversations, this creates friction.

### 3.2 Leading Candidate: Radd (رَدّ)

رَدّ means "reply." Instant Arabic recognition, 4 letters, professional, no chatbot baggage.

**This is a hypothesis, not a decision.**

| Check | Status | Deadline |
|-------|:------:|:-------:|
| Trademark search (Saudi + GCC) | NOT DONE | Week 2 |
| Domain availability (radd.ai, radd.sa) | NOT DONE | Week 1 |
| Existing companies named "Radd" in MENA | NOT DONE | Week 1 |
| Merchant reaction test (5 merchants) | NOT DONE | Week 3 |
| Alternative testing (Jawab, Raddi) | NOT DONE | Week 3 |

### 3.3 Decision Protocol

DECISION: Final name chosen by **Day 21** after trademark + domain + merchant data. Until then, "Radd" is internal working name only. No brand investment until confirmed.

DECISION: If "Radd" fails any check, fallback candidates: **Jawab (جواب)**, **Raddi (رَدّي)**, or clean English name without "chat"/"bot"/"AI".

### 3.4 Decided Now (Regardless of Name)

| Element | Decision |
|---------|----------|
| Brand voice | "Competent colleague at a help desk." (ARABIC-STYLE-GUIDE-v1) |
| Logo direction | Arabic typography-forward. Professional, geometric. |
| Color direction | Deep teal or navy + warm accent. No red/green. |
| Language priority | Arabic-first in all materials. |

---

## 4. COMMERCIAL THESIS

### 4.1 ICP

DECISION: Saudi e-commerce founder on Salla/Zid, 2–10K orders/month, 3–10 CS agents, WhatsApp active, Arabic >80%, founder-decides, no AI vendor.

| Label | Claim |
|:-----:|-------|
| ESTIMATED | "3,000–5,000 companies fit" — secondary research. |
| ESTIMATED | "500–1,000 in active pain" — logic-based subset. |
| ASSUMED | This is the right first segment. |

CONTINGENCY: If ICP is wrong → test: (1) larger Saudi e-commerce (10K–50K orders), (2) food delivery, (3) fashion-specific.

### 4.2 Wedge

> **"[Name] answers your customers' WhatsApp messages about order tracking, shipping, and returns — in their Arabic dialect — while you sleep. When it cannot answer, it hands off to your team with full context."**

DECISION: Wedge statement locked. Name slot variable. Rest does not change until discovery forces it.

### 4.3 Pricing

| Label | Element |
|:-----:|---------|
| HYPOTHESIS | $500/month is the right price. |
| DECISION | Van Westendorp test in discovery. No anchoring. |
| DECISION | Pilot is free, 21 days. Does not change. |
| CONTINGENCY | Corridor <$400 → start at $299. Corridor >$600 → start at $699. |

### 4.4 Why Customers Will Buy (Hypothesis Stack)

| Reason | Label | What Invalidates It |
|--------|:-----:|-------------------|
| Pain is personal (founder at 11 PM) | HYPOTHESIS | 7/10 say CS is not their biggest pain |
| ROI is immediate ($500 vs agent costs) | ASSUMPTION | Agent costs lower, or no plan to reduce headcount |
| Risk is low (free pilot + escalation) | DECISION | Product design choice. Stays. |
| Trust is visible (dashboard, audit) | HYPOTHESIS | Merchants want cheapest bot, not governance |

---

## 5. EXECUTION PATH

### 5.1 Week 1–3: Validate or Kill

| # | Action | Output | Days |
|---|--------|--------|:----:|
| 1 | Arabic NLP benchmark: 100 queries × GPT-4.1-mini + AraBERT | Benchmark spreadsheet | 2 |
| 2 | Domain + trademark check: "Radd" + 2 alternatives | Availability report | 1 |
| 3 | 5 merchant discovery conversations (CVB v2) — include name test | 5 synthesis sheets | 10 |
| 4 | Cross-document reconciliation | 2-page note | 1 |
| 5 | Meta Business verification submitted | Confirmation | 1 |

### 5.2 Week 3–6: Build First Vertical Slice

| # | Action | Output | Days |
|---|--------|--------|:----:|
| 6 | Name decision (Day 21) | Final name | 1 |
| 7 | Brand foundation with confirmed name | Logo + 1-page Arabic PDF | 3 |
| 8 | Sprint 0: docker-compose + Alembic + FastAPI scaffold | Running dev environment | 3 |
| 9 | Sprint 1: WhatsApp webhook + intent v0 + template engine | Working template bot | 10 |
| 10 | 5 more conversations (10 total) + go/no-go | Evidence-based decision | 10 |
| 11 | Sample Arabic KB: 30 FAQs + 5 policies | Test content | 3 |

### 5.3 Cursor Vertical Slices

| Slice | Ships | Weeks | Proves |
|:-----:|-------|:-----:|--------|
| 1 | WhatsApp → intent → template → logged | 3–5 | Pipeline works. Templates handle high-frequency. |
| 2 | Query → KB retrieval → RAG → NLI → response | 5–8 | Arabic RAG is accurate from real KB. |
| 3 | Low confidence → escalation → agent → context → resolution | 8–10 | Escalation works. Context useful. |
| 4 | Admin: conversations + KB + settings + analytics | 10–12 | Merchant can see and control system. |
| 5 | Hardening: PII, security, load, Arabic review, onboarding | 12–14 | Safe for real data. 38-item checklist passes. |

### 5.4 Validation Gates (Non-Negotiable)

| Gate | Validate | Before Building | Method | Deadline |
|:----:|----------|----------------|--------|:-------:|
| G1 | Arabic NLP minimum bar | RAG pipeline | 100-query benchmark | Week 1 |
| G2 | ≥3/5 merchants strong M1 signal | Full 14-week commitment | Discovery synthesis | Week 3 |
| G3 | Go/no-go decision | Sprints 3–6 | 10-conversation synthesis | Week 4 |
| G4 | Template accuracy >90% | RAG complexity | 200 manual tests | Week 6 |
| G5 | Pilot customer committed + KB | Hardening phase | Signed agreement | Week 10 |

### 5.5 Contingency Paths

| If This Happens | Do This |
|-----------------|---------|
| NLP <70% intent accuracy | Pure template engine, no RAG. Test at $299. |
| 7/10 reject concept | Stop. Test alternative ICP or agent-assistant positioning. |
| $500 too expensive for 7/10 | Test $299 or per-conversation only. |
| WhatsApp API delayed >6 weeks | Twilio or 360dialog as BSP. |
| "Radd" taken | Jawab, Raddi, or new candidate by Day 7. |
| Salla API difficult | Mock data. CSV from merchants. |
| Pilot customer has no KB | Build KB as onboarding service. |

---

## 6. RISK VIEW

| Risk | Probability | Impact | Kill Condition |
|------|:----------:|:------:|---------------|
| Arabic AI insufficient | MEDIUM | FATAL | Template-heavy can't hit 60% automation. |
| Trust barrier total | MEDIUM | FATAL | 8/10 reject despite governance demo. |
| No founder commitment | HIGH | FATAL | Uncommitted after Day 7. |
| Cash insufficient | MEDIUM | FATAL | Can't fund 3 months ($6K minimum). |
| Overbuilding before validating | HIGH | SEVERE | Skipping gates G2 or G3. |
| Competitor launches first | MEDIUM | HIGH | Comparable product + lower price while we're >3 months out. |

**Protect:** Arabic quality (time-limited moat). Escalation integrity (product soul). Validation discipline (gates are non-negotiable).

**Ignore until pilot converts:** Post-MVP features. Investors. Salla partnership. SOC 2. Multi-geography. Analytics. Perfection.

---

## 7. FOUNDER COMMAND

### 7.1 Now

- **Day 1:** NLP benchmark. Domain check. Trademark search start.
- **Day 2–3:** 5 outreach messages. Meta verification.
- **Week 2:** 2–3 conversations (include name test). Sprint 0 starts.
- **Week 3:** Name decision Day 21. Commission brand. Sprint 1 begins.
- **Week 4:** Working template bot. Go/no-go decision. Pilot candidate.

### 7.2 Stop

- Strategy documents. (Operational docs continue.)
- Architecture debates. Decisions are made. Build.
- Post-MVP planning. Does not exist until pilot converts.
- Treating assumptions as facts. Label. Update.

### 7.3 Commit

| Commitment | Deadline | Negotiable? |
|-----------|:--------:|:-----------:|
| NLP benchmark | Day 2 | NO |
| Name confirmed | Day 21 | NO |
| 10 merchant conversations | Day 30 | NO |
| Working template bot | Day 30 | NO |
| Go/no-go with evidence | Day 30 | NO |
| Pilot customer live | Week 14 | TARGET ±2 weeks |

### 7.4 Success

One sentence: **A Saudi e-commerce merchant on Salla whose real customers are served by this product on WhatsApp, paying for it, with a publishable case study.**

Everything in 30 documents and this document exists to make that happen within 21 weeks.

---

---

---

# الجزء الثالث: العربية — وثيقة سيطرة المؤسس v2

**تحتوي على قرارات وفرضيات وافتراضات. كل واحدة مصنفة.**

---

## ١. موقف المؤسس

**الشركة:** شركة ذكاء اصطناعي عربية أولاً. **المنتج الأول:** أتمتة خدمة عملاء للتجارة الإلكترونية السعودية عبر واتساب. رأس الجسر، وليس السقف.

| التصنيف | البيان |
|:-------:|-------|
| قرار | عربية أولاً. غير قابل للتفاوض. |
| قرار | المنتج الأول: أتمتة CS. |
| فرضية | سلة/زد السوق الأول الصحيح. تُختبر. |
| فرضية | واتساب القناة الأولى الصحيحة. تُختبر. |

### ثلاث مزايا بالديمومة

**١ (دائمة):** العمق التشغيلي — توجيه ثقة، ٥ بوابات هلوسة، تحويل محكوم. صعب التكرار.
**٢ (١٢–١٨ شهر):** جودة NLP العربية — نافذة تُغلق. نحتاج قفل عملاء قبل إغلاقها.
**٣ (٣–٦ أشهر):** ملاءمة سلة/زد — تستمر حتى يبني منافس نفس التكامل.

---

## ٢. اتجاه التسمية

**المشكلة:** "ChatPod" يحتوي "Chat" يناقض التمركز.
**المرشح:** رَدّ (Radd) — فرضية، ليست قراراً.

فحوصات مطلوبة قبل الالتزام: علامة تجارية (الأسبوع ٢)، نطاقات (الأسبوع ١)، شركات قائمة (الأسبوع ١)، ردة فعل ٥ تجار (الأسبوع ٣).

**قرار:** الاسم النهائي بحلول اليوم ٢١. لا استثمار علامة قبل التأكيد. احتياطي: Jawab، Raddi.

---

## ٣. الأطروحة التجارية

**العميل:** مؤسس تجارة إلكترونية سعودي على سلة/زد، ٢–١٠ آلاف طلب/شهر. [تقدير: ٣–٥ آلاف شركة تناسب. افتراض: هذا القطاع الصحيح.]

**نقطة الدخول:** "[الاسم] يرد على رسائل عملائك على واتساب عن الطلبات والشحن والإرجاع — بلهجتهم — وأنت نايم. ولما ما يقدر، يحوّل لفريقك بالسياق الكامل."

**التسعير:** $٥٠٠/شهر [فرضية]. Van Westendorp في الاكتشاف [قرار]. تجربة ٢١ يوم مجانية [قرار]. طوارئ: <$٤٠٠ → $٢٩٩. >$٦٠٠ → $٦٩٩.

---

## ٤. مسار التنفيذ

### أسبوع ١–٣: تحقق أو اقتل

اختبار NLP (يومان) + فحص نطاقات/علامة (يوم) + ٥ محادثات اكتشاف (١٠ أيام) + توحيد وثائق (يوم) + تحقق Meta (يوم).

### أسبوع ٣–٦: أول شريحة عمودية

قرار الاسم (يوم ٢١) + علامة (٣ أيام) + Sprint 0 (٣ أيام) + Sprint 1: بوت واتساب قوالب (١٠ أيام) + ٥ محادثات + استمرار/توقف.

### بوابات التحقق (غير قابلة للتفاوض)

| البوابة | تحقق من | قبل بناء | الموعد |
|:-------:|--------|---------|:------:|
| G1 | جودة NLP | خط RAG | أسبوع ١ |
| G2 | ≥٣/٥ إشارة M1 قوية | ١٤ أسبوع بناء | أسبوع ٣ |
| G3 | استمرار/توقف | سبرنت ٣–٦ | أسبوع ٤ |
| G4 | دقة قوالب >٩٠% | تعقيد RAG | أسبوع ٦ |
| G5 | عميل تجربة + KB | تشديد | أسبوع ١٠ |

### مسارات طوارئ

NLP <٧٠% → قوالب صافية بـ $٢٩٩. ٧/١٠ رفض → توقف، اختبر ICP بديل. $٥٠٠ غالية → $٢٩٩ أو لكل محادثة. واتساب تتأخر → Twilio. "Radd" مأخوذ → Jawab/Raddi. سلة صعبة → بيانات CSV. عميل بدون KB → نبنيها كخدمة.

---

## ٥. المخاطر

| الخطر | شرط القتل |
|-------|----------|
| AI عربي غير كافٍ | قوالب كثيفة لا تحقق ٦٠% أتمتة |
| حاجز ثقة كامل | ٨/١٠ رفض رغم الحوكمة |
| لا التزام مؤسس | غير ملتزم بعد يوم ٧ |
| نقود غير كافية | لا يمكن تمويل ٣ أشهر |
| بناء زائد قبل تحقق | تجاوز G2 أو G3 |

**احمِ:** الجودة العربية. نزاهة التحويل. انضباط التحقق.
**تجاهل حتى التجربة تتحول:** كل شيء بعد MVP.

---

## ٦. أمر المؤسس

- **اليوم ١:** اختبار NLP. فحص نطاقات.
- **يوم ٢–٣:** ٥ رسائل تواصل. تحقق Meta.
- **أسبوع ٢:** ٢–٣ محادثات. Sprint 0.
- **أسبوع ٣:** قرار الاسم. Sprint 1.
- **أسبوع ٤:** بوت واتساب يعمل. استمرار/توقف. مرشح تجربة.

**التزامات غير قابلة للتفاوض:** اختبار NLP (يوم ٢). الاسم (يوم ٢١). ١٠ محادثات (يوم ٣٠). بوت يعمل (يوم ٣٠). قرار بدليل (يوم ٣٠).

**النجاح:** تاجر سعودي واحد على سلة عملاؤه الحقيقيون يُخدمون بهذا المنتج على واتساب، يدفع، ودراسة حالته منشورة. خلال ٢١ أسبوع.
