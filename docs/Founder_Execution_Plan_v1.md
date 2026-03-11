# FOUNDER EXECUTION PLAN v1

**Governing document:** Founder Control Document v2
**Source of truth:** 30 project files (~294,000 words) + Founder Control Document v2
**Purpose:** Turn the founder thesis into a real operating plan with exact outputs, gates, and deadlines
**This is not strategy. This is the work.**
Version 1.0 | March 2026

---

## 1. EXECUTION OBJECTIVE

### 1.1 What We Are Trying to Achieve Now

Get from 294,000 words of specification and zero code to one Saudi e-commerce merchant whose real WhatsApp customers are being served by our product, who is paying for it, and whose case study we can publish. Timeline: 21 weeks.

### 1.2 What This Phase Is Meant to Prove

- **Market:** Saudi e-commerce founders will pay for Arabic CS automation via WhatsApp. (M1, M2, M3, M4)
- **Technology:** Arabic NLP quality is sufficient for grounded, dialect-aware CS responses with <3% hallucination. (T1, T2, T3, T5, T8)
- **Economics:** Cost per conversation ($0.03–0.055 blended) sustains 40–70% gross margins at $500/month.

### 1.3 What Success Looks Like

| Metric | Target | Source |
|--------|--------|--------|
| Pilot automation rate | >55% | PROJECT-BIBLE-v2 §8.4 |
| Hallucination rate | <3% | Consistent across all docs |
| CSAT | >3.5/5.0 | PROJECT-BIBLE-v2 §5.4 |
| P95 latency | <4 seconds | NFR-REQUIREMENTS §PERF-05 |
| Uptime | >99.5% | NFR-REQUIREMENTS §AVAIL-01 |
| Pilot converts to paid | Yes | The only metric that truly matters |

---

## 2. CURRENT REALITY

### 2.1 What Is Already Defined

| Area | Depth | Source |
|------|-------|--------|
| Market thesis + ICP + competitive landscape | 3 ICPs, 8 competitors × 14 dimensions | ICP-SEGMENTATION, COMPETITIVE-ANALYSIS |
| MVP scope (in/out) | Explicit table, 12 deferred features | PROJECT-BIBLE-v2 §5 |
| Product design | 13 flows, 150+ Arabic messages, 10 error states | CONVERSATION-FLOWS, PRD-v1 |
| Technical architecture | 7+11 layers, 28 entities, 87 endpoints, 87 security reqs | SYSTEM-ARCHITECTURE, TECHNICAL-ARCHITECTURE |
| Engineering plan | 6 sprints + 2 hardening, 11 milestones, 38-item checklist | ENGINEERING-EXECUTION-PLAN |
| GTM playbook | Founder-led sales, Arabic scripts, 90-day plan | GTM-STRATEGY |
| Arabic style guide | Voice, 3 dialects, do/don't tables, 8 tone contexts | ARABIC-STYLE-GUIDE |
| Pricing model | 8 models evaluated, 3 tiers, unit economics | BUSINESS-MODEL-PRICING |

### 2.2 What Is Still Unvalidated

| Item | Risk Level | Method |
|------|:----------:|--------|
| Merchants will pay for Arabic CS automation (M1) | EXISTENTIAL | 10 discovery conversations |
| Governance overcomes trust barrier (M4) | EXISTENTIAL | Discovery + governance concept |
| Arabic NLP quality (T1, T3) | EXISTENTIAL | 100-query benchmark |
| WhatsApp is dominant CS channel (M2) | STRUCTURAL | Discovery conversations |
| $500/month is the right price | STRUCTURAL | Van Westendorp |
| 55–70% of CS volume is automatable | ESTIMATED | Real inbox analysis |
| Product name resonates in Saudi | MEDIUM | Merchant reactions |

### 2.3 What Could Block Execution Right Now

| Blocker | Impact | Resolution | Time |
|---------|--------|------------|------|
| No committed founder | FATAL | Declare or stop | Day 1 |
| Meta verification delay | Blocks WhatsApp | Submit immediately; Twilio/360dialog backup | 2–4 weeks |
| Salla API inaccessible | Blocks wedge | Contact developer relations; CSV fallback | Week 1 |
| Arabic AI quality poor | Blocks RAG path | NLP benchmark; template-heavy pivot | Day 1–2 |
| Cross-document contradictions | Confuses developers | Reconciliation note | Day 14 |

---

## 3. STRATEGIC PRIORITIES

### 3.1 What Matters Now

| Priority | Deadline |
|----------|:--------:|
| Founder commitment (name + hours + money) | Day 1 |
| Arabic NLP benchmark (100 queries) | Day 2 |
| 5 merchant conversations | Day 14 |
| Product name validation (trademark + domain + merchant) | Day 21 |
| Cross-document reconciliation | Day 14 |
| Meta Business verification submitted | Day 3 |

### 3.2 What Does Not Matter Now

Post-MVP features. Investor materials. Salla/Zid partnership deck. SOC 2. Custom analytics. Agent performance dashboards. Mobile responsive admin. Multi-geography.

### 3.3 What Must Be Delayed

| Item | Until | Why |
|------|-------|-----|
| Agent workstation UI | Sprint 4 | Design from real observation, not specs |
| Post-MVP specs | After pilot conversion | Pilot reveals real priorities |
| Investor deck | After 1 paying customer | Pitch with proof |
| Salla partnership | After 5 customers | Earn from traction |
| Onboarding playbook | Sprint 5 | Informed by actual onboarding |

### 3.4 Founder Must Stop

- Writing strategy documents
- Debating decided architecture (ECS, Neon, FastAPI, Next.js)
- Perfecting 13 conversation flows before real data
- Planning for scale at 0 customers
- Reading 30 documents end-to-end (create a 5-page Developer Start Guide instead)

---

## 4. MVP EXECUTION DEFINITION

### 4.1 What the MVP Must Include

| Capability | Engineering Deliverables | Sprint |
|------------|--------------------------|:------:|
| Receive Arabic WhatsApp message | Webhook, HMAC, parser, normalizer, session mgmt | S1 |
| Classify intent → template or RAG | Keyword v0 (S1), AraBERT v1 (S2). Decision tree. | S1–S2 |
| Respond from KB in dialect | Templates (S1). KB + RAG + NLI (S2–S3). | S1–S3 |
| Escalate with context | Confidence routing. Hard/soft escalation. Context package. | S4 |
| Log in admin dashboard | Conversation viewer, KB CRUD, escalation queue, settings, 8 KPIs | S5 |

**Safety (non-negotiable):** PII redaction (S5), audit trail (S1+), RLS tenant isolation (S1), Salla order status (S4).

### 4.2 What the MVP Must Exclude

Web chat/email/voice. Levantine/Maghreb. Assisted review. Advanced analytics. Auto KB ingestion. Callback scheduling. Agent performance. Custom tenant branding.

### 4.3 What the MVP Validates

| Question | Success | Failure |
|----------|---------|---------|
| Can Arabic AI respond accurately enough? | >90% accuracy, <3% hallucination | >5% hallucination |
| Will merchants pay? | 1 pilot converts ~$500/month | Pilot refuses to continue |
| Is template + RAG split right? | Templates >50% of volume | <30% template coverage |
| Is architecture sound? | >99.5% uptime, <4s P95 | SEV-1 incident |

---

## 5. VALIDATION PLAN

### 5.1 Assumptions Tested First

| Order | Assumption | Method | Deadline | Go | Stop |
|:-----:|-----------|--------|:--------:|----|----|
| 1 | Arabic NLP quality (T1, T3) | 100-query benchmark | Day 2 | >80% intent accuracy | <70% |
| 2 | Merchants will pay (M1) | 5 conversations | Day 14 | ≥3/5 strong behavioral | 4/5 reject |
| 3 | Trust barrier crossable (M4) | Same conversations | Day 14 | ≥3/5 say governance helps | 4/5 say "never" |
| 4 | WhatsApp primary channel (M2) | Same conversations | Day 14 | ≥4/5 confirm | Majority use phone/email |
| 5 | $500/month viable | Van Westendorp in convs 6–10 | Day 30 | Median "easy yes" $400–700 | Median "too expensive" <$400 |

### 5.2 Validation Gates (Non-Negotiable)

| Gate | Condition | Before Building | Deadline |
|:----:|-----------|----------------|:--------:|
| G1 | Arabic NLP ≥80% intent + natural generation | RAG pipeline | Day 2 |
| G2 | ≥3/5 strong M1 signals | Full 14-week build commitment | Day 14 |
| G3 | Go/no-go from 10 conversations | Sprints 3–6 | Day 30 |
| G4 | Template accuracy >90% on 200 tests | RAG complexity investment | Week 6 |
| G5 | Pilot customer committed + KB content | Hardening phase | Week 10 |

### 5.3 Naming Validation

Every conversation: "If you saw a product called [Radd / رَدّ], what would you think?" Test 1 alternative in half.

Parallel: trademark + domain by Day 14.

Decision: Day 21.

### 5.4 Pricing Validation

Van Westendorp (4 questions, no anchoring) in conversations 6–10.

Output: price corridor.

Contingency: corridor <$400 → $299. >$600 → $699.

---

## 6. BUILD PLAN

### Phase 1 — Immediate Founder Focus (Days 1–7)

**Objective:** Resolve existential unknowns. Start lead-time clocks.

| Output | Days |
|--------|:----:|
| Founder declaration: name, hours/week, runway, skills | 1 |
| Arabic NLP benchmark: 100 queries (GPT-4.1-mini + AraBERT) | 2 |
| Domain + trademark check (Radd + 2 alternatives) | 1 |
| Prospect list: 15 merchants (Salla + Maroof + Twitter) | 2 |
| Meta Business verification submitted | 1 |
| Salla developer account requested | 1 |

**Decision:** NLP benchmark → proceed / template-heavy pivot / stop.
**Risk:** NLP quality below threshold.
**Go/no-go:** ≥80% intent accuracy + natural generation → GO. <70% → template-only contingency. <60% → reassess.

### Phase 2 — Validation and Market Signal (Days 8–21)

**Objective:** 5 conversations. Name decision. Sprint 0. Document reconciliation.

| Output | Days |
|--------|:----:|
| 10 outreach messages sent (Gulf Arabic + MSA) | 2 |
| 3 discovery conversations + 3 synthesis sheets | 7 |
| 3-interview checkpoint: adjust 1 question | 1 |
| Cross-document reconciliation (2-page note) | 1 |
| Sprint 0: docker-compose + .env + Alembic (7 tables + RLS) + FastAPI scaffold | 3 |
| Conversations 4–5 + name reaction test | 5 |
| Name decision (Day 21) | 1 |

**Decision:** Name locked. ≥3/5 positive → full speed. 4/5 negative → pause, adjust ICP.
**Risk:** Low response rate. Name blocked. Salla API delayed.
**Go/no-go:** 5 conversations done + ≥3 strong M1 → proceed to Phase 3.

### Phase 3 — MVP Definition + Go/No-Go (Days 21–30)

**Objective:** Working template bot. 10 conversations. Go/no-go. Pilot candidate.

| Output | Days |
|--------|:----:|
| Brand: logo + 1-page Arabic PDF (confirmed name) | 3 |
| Sprint 1: WhatsApp webhook + intent v0 + template engine | 10 |
| Conversations 6–10 (Van Westendorp pricing) | 10 |
| Full synthesis: scorecard + pricing corridor + pipeline | 2 |
| Go/no-go decision | 1 |
| Sample KB: 30 FAQs + 5 policies | 3 |
| Pilot candidate identified (Rung 3+ commitment) | By Day 30 |

**Decision:** GO / ADJUST / PIVOT / STOP per Founder Control Doc v2.
**Risk:** Template bot harder than expected. Ambiguous signals. No Rung 3+ prospect.
**Go/no-go:** Existential assumptions (M1 + M4) pass → GO. Fail → ADJUST/PIVOT/STOP.

### Phase 4 — Cursor Build (Weeks 5–12)

*Only if Phase 3 = GO or ADJUST.*

| Sprint | Weeks | Ships | Proves |
|:------:|:-----:|-------|--------|
| S2 | 5–6 | KB upload + chunking + embedding + hybrid retrieval | Arabic KB search works |
| S3 | 7–8 | RAG generation + NLI verification + confidence routing + template/RAG routing | <3% hallucination on 200 tests |
| S4 | 9–10 | Escalation + context package + Salla order status + agent notifications | Escalation works. Wedge works. |
| S5 | 11–12 | Admin dashboard (RTL) + PII redaction + audit viewer | Merchant can see and control |

Each sprint gate: Previous sprint acceptance criteria pass in staging.

### Phase 5 — Pilot Readiness (Weeks 12–14)

**Objective:** Safe for real data. 38-item checklist. Onboarding complete.

| Output | Weeks |
|--------|:-----:|
| Security audit (OWASP LLM Top 10, prompt injection) | 12 |
| Load test (50 sessions, P95 <4s) | 12 |
| Arabic review (500 test conversations, <3% hallucination) | 12–13 |
| 38-item pilot readiness checklist passes | 13 |
| Pilot onboarding (KB loaded, agents trained, dry run) | 13–14 |
| Shadow mode (48 hours, zero critical errors) | 14 |

**Go/no-go:** All 38 items + shadow clean → go live. Any critical error → fix and re-shadow.

### Phase 6 — Traction and Iteration (Weeks 14–21)

| Output | Weeks |
|--------|:-----:|
| Pilot: shadow → 10% → 50% → full traffic | 15–18 |
| Weekly metrics reports to merchant | 15–18 |
| KB optimization from real gaps | 15–18 |
| Threshold calibration from real data | 15–18 |
| Day 22 exit meeting → conversion decision | 18 |
| Case study draft (48 hours post-pilot) | 18 |
| 2nd and 3rd pilots started (if converted) | 19–21 |

**Success:** Automation >55%, hallucination <3%, CSAT >3.5, pilot converts, case study published.

---

## 7. CURSOR EXECUTION COORDINATION

### 7.1 What Cursor Builds First (Sprint 1, Weeks 3–5)

| Component | Build Fully | Stub |
|-----------|:-----------:|:----:|
| FastAPI modular monolith structure | ✓ | |
| 7 core PostgreSQL tables + RLS + Alembic | ✓ | |
| WhatsApp webhook (receive + verify + ack) | ✓ | |
| Arabic text normalizer | ✓ | |
| Redis session management (30-min timeout) | ✓ | |
| Keyword intent classifier v0 (6 intents) | ✓ | |
| Rule-based dialect detector v0 | ✓ | |
| Template response engine (5 templates) | ✓ | |
| WhatsApp response delivery | ✓ | |
| Confidence scoring | | ✓ (all=1.0) |
| RAG pipeline | | ✓ (escalation stub) |
| Escalation engine | | ✓ (log only) |
| Admin dashboard | | ✓ (Grafana + DB) |

### 7.2 What Cursor Must NOT Build Yet

| Do Not Build | Until | Why |
|--------------|-------|-----|
| RAG pipeline | Sprint 2 | Template first. Validate simple path. |
| Admin dashboard UI | Sprint 5 | Backend first. Grafana + DB queries until then. |
| Agent workstation | Sprint 4 | No UI for nonexistent backend. |
| AraBERT classifier | Sprint 2 | Keyword v0 proves pipeline. ML improves accuracy. |
| Advanced analytics | Post-pilot | 8 KPI cards are enough. |

### 7.3 Build Dependency Chain

```
Week 3: Schema + RLS + Alembic + FastAPI + Redis + docker-compose
   ↓
Week 4: Webhook + normalizer + sessions + intent v0 + templates + delivery
   ↓ SLICE 1: WhatsApp in → template out → logged
Week 5–6: Qdrant + KB upload + chunking + embedding + hybrid retrieval
   ↓
Week 7–8: RAG generation + NLI + confidence scoring + routing
   ↓ SLICE 2: complex query → grounded response → verified
Week 9–10: Escalation + context + agent queue + Salla API + WebSocket
   ↓ SLICE 3: low confidence → escalation → agent → resolution
Week 11–12: Admin dashboard (Next.js RTL) + PII + audit
   ↓ SLICE 4: merchant sees and controls everything
Week 13–14: Security + load test + Arabic review + onboarding
   ↓ PILOT-READY
```

### 7.4 Manual Tests Before More Coding

| Test | When | Pass |
|------|------|------|
| WhatsApp round-trip (real message → real response) | Week 4 end | Correct template in <3s |
| Arabic normalization (50 messages) | Week 4 | All normalize correctly |
| Intent accuracy (100 queries) | Week 4 | >70% on v0 |
| KB retrieval relevance (50 queries) | Week 6 | Correct passage in top 3 for >80% |
| RAG accuracy (200 queries) | Week 8 | >90% accurate, <3% hallucination |
| Cross-tenant isolation | Every sprint | 100% isolation |
| PII redaction (50 messages) | Week 12 | >95% recall |

### 7.5 What First Working Version Does (Day 30)

1. Receives WhatsApp message from any phone
2. Detects Arabic
3. Classifies intent (6 categories)
4. Template intent → correct Arabic response in detected dialect
5. Non-template → "سأحولك لأحد فريقنا" (escalation stub)
6. Logs conversation in PostgreSQL with tenant_id
7. Does NOT crash, leak data, or lose messages

---

## 8. 30-DAY FOUNDER SPRINT PLAN

### Week 1 (Days 1–7)

| Do | Ship | Validate | Build | Decide | Ignore |
|----|------|----------|-------|--------|--------|
| Founder declaration. NLP benchmark. Domain/trademark. Prospects. Meta verification. | Founder doc. Benchmark spreadsheet. Domain report. 15-prospect sheet. Meta confirmation. | G1: NLP ≥80%? | Nothing in Cursor yet. | Am I doing this? Does the AI work? | Everything not about the next 30 days. |

### Week 2 (Days 8–14)

| Do | Ship | Validate | Build | Decide | Ignore |
|----|------|----------|-------|--------|--------|
| 10 outreach messages. 3 conversations. Reconciliation. Sprint 0. | 10 messages. 3 synthesis sheets. Reconciliation note. Running docker-compose. | M1 + M4 signals. Name reactions. | Sprint 0: docker-compose, .env, Alembic, FastAPI scaffold. | Name: initial data. Architecture: reconciled. | Perfect outreach. Perfect project structure. |

### Week 3 (Days 15–21)

| Do | Ship | Validate | Build | Decide | Ignore |
|----|------|----------|-------|--------|--------|
| Conversations 4–5. 3-interview checkpoint. Name decision. Sprint 1 starts. Brand. | 5 synthesis sheets. Checkpoint notes. Name locked. Design brief sent. Webhook + normalizer. | ≥3/5 M1? Name confirmed? | Sprint 1: webhook, normalizer, sessions, intent v0, template engine starts. | Name: LOCKED. 4/5+ positive → full speed. | Logo perfection. RAG. Admin UI. |

### Week 4 (Days 22–30)

| Do | Ship | Validate | Build | Decide | Ignore |
|----|------|----------|-------|--------|--------|
| Conversations 6–10 (Van Westendorp). Sprint 1 complete. Synthesis. Go/no-go. | Working template bot. 10 sheets. Pricing corridor. Decision record. Brand materials. Pilot candidate. | Full go/no-go. Pricing. | Sprint 1: dialect v0, templates, delivery, logging. | GO/ADJUST/PIVOT/STOP. Price. Pilot customer. | Conversations 9–10 if clear at 8. Post-MVP. |

---

## 9. KILL RISKS

| Category | Risk | Warning Sign | Response |
|----------|------|-------------|---------|
| Strategic | No product-market fit | 7/10 reject or deflect | STOP or PIVOT ICP |
| Strategic | Building wrong thing | Conversations reveal different pain | ADJUST scope |
| Commercial | Price too high | Van Westendorp "easy" <$300 | Start at $299 |
| Commercial | ICP too narrow | <15 prospects found | Expand geography + lower floor |
| Technical | Arabic AI insufficient | Benchmark <70% | Template-only pivot |
| Technical | Hallucination >3% | RAG test fails | Tighten thresholds, more templates |
| Technical | WhatsApp blocked | Meta rejects/delays | Twilio/360dialog BSP |
| Founder | Writing instead of building | Any new strategy doc | STOP WRITING. OPEN CURSOR. |
| Founder | Avoiding merchant calls | Week 2, zero conversations | Non-negotiable. Make 3 calls. |
| Founder | Perfecting before shipping | Sprint 1 >2 weeks | Ship imperfect. Iterate Sprint 2. |

---

## 10. FOUNDER OPERATING RULES

1. Validate and build in parallel. Discovery while coding. Neither waits.
2. Ship a vertical slice every 2 weeks. End-to-end or not done.
3. Every gate is non-negotiable. G1–G5 are hard stops.
4. Template first, RAG second. Templates are the floor. RAG adds depth.
5. Default to MSA when uncertain. Ship. Improve with data.
6. Escalate early with context. Never guess. Product soul.
7. One customer beats ten plans. Everything is hypothesis until real traffic.
8. Talk to merchants every week. Until 10 paying customers.
9. Hire at Sprint 3, not Sprint 0. Validate before scaling cost.
10. No more strategy documents. Operational docs continue. Strategy is done.

---

## 11. FINAL EXECUTION COMMAND

### What We Do Next

- **Today:** Declare. NLP benchmark. Domain check. Trademark search. Meta verification.
- **This week:** 5 outreach messages. Prospect list. Sprint 0 on Day 5.
- **Next week:** 3 conversations. Sprint 0 complete. Sprint 1 starts.
- **By Day 30:** Working template bot. 10 conversations. Go/no-go. Pilot candidate. Brand confirmed.

### What We Do Not Do Yet

RAG. Admin dashboard. Agent UI. Post-MVP features. Investor materials. Salla partnership. Multi-geography. Scale optimization. Perfection.

### What Success in 30 Days Depends On

1. **NLP benchmark GO signal (Day 2).** Cheapest, fastest test of the most important technical assumption.
2. **≥3/5 merchants show strong demand (Day 14).** Behavioral signals, not polite interest.
3. **Template bot works on WhatsApp (Day 30).** Real message → real Arabic response → logged.

If all three: Week 5 starts Sprint 2 with confidence and a pilot warming up.

If any fails: contingency paths activate before resources are wasted.

**The plan is done. The next thing that happens is not a document. It is an action.**
