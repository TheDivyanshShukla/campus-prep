# RGPV Live - Project State

## Overview
This document serves as a memory checkpoint for the RGPV Live project, a study portal built for engineering students to access AI-parsed PYQs (Previous Year Questions), detailed notes, formula sheets, and more. 

## Tech Stack
- **Backend:** Django 5.2 (Python)
- **Frontend Core:** HTML, Vanilla JavaScript, Tailwind CSS (CDN)
- **Design System:** HeroUI / Shadcn aesthetic (Sleek dark mode, glassmorphism, micro-animations)
- **Math/Markdown:** KaTeX for LaTeX rendering, library for client-side Markdown rendering
- **Package Manager:** `uv`

## Architecture
- **Apps-Driven:** The project uses a `config` folder for root settings and an `apps` directory for modular Django functionality (e.g., `apps.users`, `apps.content`, `apps.academics`).
- **Data Models:**
  - `academics`: `Branch`, `Semester`, `Subject`
  - `content`: `ParsedDocument` (JSON structured data for storing AI outputs)
  - `users`: Extending standard `User` flows

## Completed Features

### 1. Authentication & Onboarding
- **Auth Views:** Functioning `login`, `signup`, and `logout` views.
- **Onboarding Flow:** New users are redirected to `/onboarding/` to select their `Branch` and `Semester`.
- **Global Auth UI:** Auth buttons dynamically render in the navbar; mobile menu correctly handles authenticated vs. guest states.

### 2. UI / UX Design & Theming
- **Sleek Base System:** `base.html` includes a robust Tailwind configuration mapped to a comprehensive CSS variables system (`--primary`, `--background`, `--card`, etc.).
- **Dark Mode:** Fully functional dark mode with an **Anti-FOUC (Flash of Unstyled Content)** implementation:
  - Cooks the `theme=dark` state into the user's browser via cookies.
  - Intercepted server-side by Django templates `{% if request.COOKIES.theme == 'dark' %}dark{% endif %}`.
  - Head `<script>` paint-blocking fallback.
- **Responsive Layout:** A mobile-first navbar with a hidden hamburger drawer for mobile navigation.

### 3. Subject & User Dashboard
- **Dashboard (`dashboard.html`):** A remarkably lean dashboard. The massive hero headers were stripped down, presenting the user with an elegant "My Study Vault" inline title, subtle Branch/Sem status badges, and an immediate grid of their `Subjects`.
- **Global Actions:** Account actions like "Change Program" and "Get Global Pass" were moved directly into the navbar to keep the viewport clean.

### 4. Zero-Scroll Tabbed Subject Interface
- **Subject Detail (`subject_dashboard.html`):** Transformed a vertically long, scrollable list of document types into a horizontal, Javascript-driven Pill Navigation system.
- **Tabs Available:** `Curriculum`, `Solved PYQs`, `Detailed Notes`, `Short Notes`, `Important Qs`.
- **Tab Memory Checkpoint:** Remembers the active tab specifically for *that* subject ID using `localStorage` and injects an anti-FOUC dynamic `<style>` block in the head to prevent the UI from flickering back to the default tab on refresh.
- **Premium Locks:** Unauthenticated or free users see styled glassmorphic overlays locking premium content.

### 5. Native Document Renderer
- **Reader Interface (`document_reader.html`):** Built to inherently parse and render complex JSON `structured_data` natively in HTML without relying on sluggish static PDFs.
- **LaTeX Math Support:** Integrated `KaTeX` for beautiful, native rendering of mathematical equations both inline `$` and block `$$`.
- **Markdown parsing:** Incorporated `marked.js` to format markdown for detailed and quick notes.
- **Dynamic Content Support:**
  - **PYQs:** Distinct question/solution blocks, clear mark badging, OR-choice highlighted tags.
  - **Syllabus:** Rendered iteratively by unit and individual sub-topics.
  - **Important Qs:** Displays lists of highly-repeated questions with "Frequency" badges.
  - **Notes:** Full markdown output.
  - **Formula Sheets:** Grids rendering pure math formulas side by side.

### 6. Dummy Data Injection
- `seed_dummy_ai.py`: A robust Django management command that autonomously populates the Postgres database with completely faked "AI-parsed" dummy payloads for UI prototyping, including rich LaTeX snippets and modular JSON structures.

## Next Steps / Focus Areas
- Ensure full backend integration for the premium paywall.
- Begin scaffolding the actual AI Parser workflows to start writing real parsed JSON data into the DB instead of dummy data.
- User profile & settings extensions.
