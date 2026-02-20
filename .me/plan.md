# 📋 RGPV Live – COMPLETE PRODUCT SPECIFICATION (MERGED & FINAL)

**Version:** 1.1  
**Last Updated:** January 2025  
**Target Audience:** RGPV (Rajiv Gandhi Proudyogiki Vishwavidyalaya) B.Tech Students  

---

## 🎯 PRODUCT VISION

**RGPV Live** is a freemium, exam-focused education platform built specifically for RGPV engineering students.

### Core Offerings
1. **Free Resources**
   - PYQ question papers
   - Official syllabus
   - Subject & unit previews
2. **Premium Content**
   - PYQ solutions
   - Chapter-wise notes
   - Important questions
   - Short notes & formula sheets
   - MCQs with explanations
   - AI-powered learning tools
3. **Flexible Monetization**
   - Individual purchases
   - Combo packs
   - Semester / monthly / yearly subscriptions
4. **AI-Powered**
   - Smart doubt solving
   - Cheat-sheet generation
   - Repeated-question detection
5. **Exam-Oriented**
   - Designed purely to help students pass and score better in RGPV exams

**Core Goal:**  
Maximize revenue using a smart freemium model while delivering genuine, exam-relevant value.

---

## 💰 MONETIZATION STRATEGY (FREEMIUM MODEL)

---

## 🆓 FREE TIER (ALWAYS FREE)

| Resource | What’s Free | Purpose |
|-------|------------|--------|
| PYQ Papers | Last 5 years | Trust & traffic |
| Syllabus | Complete | SEO & onboarding |
| Subject Listing | All subjects | Discovery |
| Unit Overview | Unit names only | Premium preview |
| Basic Search | Subject/topic search | Engagement |

---

## 💎 PREMIUM TIER (PAID)

---

### 🔹 TYPE 1: INDIVIDUAL PRODUCTS (ONE-TIME PURCHASE)

> ⚠️ **Prices are NOT fixed. They vary by subject complexity and are fully admin-configurable.**

| Product | Base Price Range | Validity |
|------|----------------|----------|
| PYQ Solutions | ₹49–₹99 | Till RGPV |
| Chapter Notes | ₹79–₹199 | Till RGPV |
| Important Questions | ₹39–₹79 | Till RGPV |
| Short / Revision Notes | ₹29–₹59 | Till RGPV |
| Formula Sheet | ₹19–₹49 | Till RGPV |
| Unit-wise MCQs | ₹59–₹99 | Till RGPV |
| AI Doubt Solver | ₹99/month | 1 month |

#### 📌 Pricing Logic
- **Maths / Signals / Control Systems:** Higher pricing due to depth
- **Core Theory Subjects:** Mid-range pricing
- **Light / Memory-Based Subjects:** Lower pricing

All prices are controlled via the **Admin Panel** (no hardcoding).

---

### 🔹 TYPE 2: COMBO PACKS (BEST VALUE)

| Combo | Price | Includes | Savings |
|----|------|---------|--------|
| Semester Survival Pack | ₹999 | Notes + PYQs + Important Qs + Short Notes (All Subjects) | ~40% |
| Exam Cracker Pack | ₹799 | PYQs + Important Qs + Formula Sheets | ~35% |
| Complete Subject Pack | ₹599 | Notes + PYQs + MCQs + Important Qs (Single Subject) | ~30% |

---

### 🔹 TYPE 3: SUBSCRIPTIONS (RECURRING / TIME-BOUND)

| Plan | Price | Duration | Access |
|---|-----|---------|-------|
| Semester Pass | ₹199 | Till exam date | All premium content (semester) |
| Monthly Pass | ₹99 | 1 month | All premium (current sem) |
| Year Pass | ₹599 | 1 year | All content (all semesters) |

#### Rules
- Semester Pass auto-expires after exam date
- Monthly & Yearly are auto-renewable
- Cancellation anytime before renewal

---

## 🔄 DYNAMIC PRICING & FULL ADMIN CONTROL (CRITICAL)

### Admin Can Configure:
- Price per **Branch**
- Price per **Semester**
- Price per **Subject**
- Price per **Content Type**
- Original vs discounted price
- Exam-season discounts
- Make any content free/paid anytime

✅ **All pricing comes from DB, not code**

---

## ➕ ACADEMIC STRUCTURE (SCALABLE)

Admin can:
- Add / edit **Branches** (CSE, AI-DS, Cyber, etc.)
- Add / edit **Semesters**
- Add / edit **Subjects**
- Update subject codes & names
- Modify syllabus & units
- Archive deprecated subjects

---

## 🏗️ TECHNICAL & ARCHITECTURAL HIGHLIGHTS

### 1. Zero-PDF Native Rendering (Anti-Piracy & UX)
- Users will **not** download PDFs.
- All notes and PYQs are parsed into structured data and rendered via **HTML + Tailwind CSS** directly on the web app.
- Math equations and formulas are handled via **Markdown + LaTeX (KaTeX/MathJax)**.
- Disables right-click and text-selection to drastically limit sharing/piracy.

### 2. PWA & Offline Support
- Implementing a **Progressive Web App (PWA)** strategy.
- Users can "Save for Offline" – securely caching the JSON/HTML in their browser/device without exposing raw document files.

### 3. Smart Database Strategy
- Utilizing **PostgreSQL `JSONB`** columns instead of XML.
- Allows lightning-fast querying (e.g., *"Find all 7-mark questions from Unit 3 from 2022"*).
- LangChain + OpenAI Structured Outputs guarantees valid JSON format, encapsulating any LaTeX safely.

### 4. Scalable Storage (Future-Proofing)
- **Phase 1 (MVP):** Local server storage.
- **Phase 2 (Scale):** Move to **AWS S3 / Cloudflare R2** with a CDN to prevent Django server crashes during peak pre-exam traffic spikes.

---

## 🔄 CONTENT VERSIONING SYSTEM

Each content item supports versioning:
- Notes v1.0 → v1.1 → v2.0
- Users always see latest version
- Admin can:
  - Keep old versions
  - Push update notifications
  - Track user access by version

---

## 🚀 COMPLETE USER FLOW

### LANDING PAGE (NO LOGIN)

```

Branch → Semester → Subject → Subject Page

```

Free users can:
- View PYQs dynamically (No PDFs)
- View syllabus
- View unit names
- See locked premium content

---

### USER FLOW: INDIVIDUAL PURCHASE

```

Select Content → Login → Checkout → Pay → Unlock Content

```

---

### USER FLOW: SUBSCRIPTION

```

Select Plan → Login → Pay → Unlock Entire Semester

```

---

### USER FLOW: ADMIN

```

Admin → Dashboard → Manage Users / Products / Pricing / Exam Dates

```

---

## 🖥️ ADMIN PANEL FEATURES

### Dashboard
- Users
- Active subscriptions
- Revenue (Daily / Monthly / Yearly)
- Top products
- Expiring subscriptions

---

### User Management
- Filter by branch / semester
- View purchase history
- Manual extensions
- Refund processing

---

### Product & Pricing Management
- Add / edit / delete products
- Dynamic pricing
- Combo creation
- Discount rules

---

### Subscription & Exam Date Management

Admin sets exam dates:
```

Branch → Semester → Exam Date

```

Auto actions:
- 7 days before: expiry warning
- On exam date: auto-expire
- After expiry: renewal email

---

### Content Management
- Upload Source PDFs or Multiple Images (Only for Admin).
- AI converts PDFs/images to structured JSON (Admin tweaks & publishes).
- Organize by branch/semester/subject.
- Version control.
- Activate / deactivate content.

---

## 🤖 AI FEATURES (MODULAR)

- AI Doubt Solver
- AI Cheat Sheet Generator
- AI Repeated Question Detector
- **AI Scanner & Parser (LangChain + OpenAI Structured Outputs):**
  - Automates extraction of raw PYQ papers and Notes from **PDFs or Multiple Images**.
  - Structures content into **JSON format (stored in JSONB)**. Handles math natively via LaTeX/Markdown.
  - Enables granular usage of individual questions for quizzes, topic-wise filtering, and dynamic HTML rendering on the frontend.

Admin can:
- Bundle with plans
- Sell separately
- Limit usage
- Enable/disable anytime

---

## 💳 PAYMENT INTEGRATION

**Razorpay (Recommended)**
- UPI, Cards, Netbanking
- One-time & subscription payments
- Robust Webhooks (Crucial for auto-resolving pending UPI transactions)
- Refunds
- Invoices

---

## 📄 LEGAL & POLICIES

### Key Points
- Semester pass auto-expiry
- No redistribution (Prevented by Zero-PDF policy & disabled text-selection)
- No downloads (Offline access managed via PWA cache only)
- Refunds only if content inaccessible
- Auto-renew disclosure
- Exam date changes handled dynamically
- One account per user
- AI outputs are assistive, not guaranteed

---

## 📱 REQUIRED PAGES

### Public
- `/`
- `/terms`
- `/privacy`
- `/refund`

### Auth
- `/login`
- `/signup`
- `/forgot-password`

### User
- `/dashboard` (Auto-loads user's branch/semester based on profile)
- `/checkout`
- `/purchases`
- `/bookmarks` (Saved/starred tough questions for revision)
- `/settings`
- `/support` (Ticketing for payment issues)

### Content
- `/notes/{subject}` (Native web view, No PDF)
- `/pyq-solutions/{subject}` (Native web view, No PDF)
- `/quiz/{subject}` (Dynamic assessment using AI-parsed JSON)
- `/mcq/{subject}`

### Admin
- `/admin`
- `/admin/ai-parser` (Upload PDF/Multiple Images, preview JSON, tweak formatting, publish)
- `/admin/users`
- `/admin/products`
- `/admin/subscriptions`
- `/admin/exam-dates`
- `/admin/revenue`
- `/admin/content`

---

## 📊 SUCCESS METRICS (KPIs)

- MAU
- Free → Paid conversion
- AOV
- MRR
- Churn
- Content downloads
- AI usage

---

## 🚨 CRITICAL SUCCESS FACTORS

1. High-quality, accurate content
2. Student-friendly pricing
3. Fast, mobile-first UX
4. Trust & transparency
5. Timely launch before exams
6. Strong campus & WhatsApp marketing

---

## ✅ FINAL NOTE

RGPV Live is:
- Fully scalable
- Admin-controlled
- Pricing-flexible
- Exam-adaptive
- Revenue-optimized

**No hardcoding. No rigidity. Fully future-proof.**

