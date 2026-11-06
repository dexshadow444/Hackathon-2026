# JM Vertex Hackathon 2027 · Registration Platform & Admin Portal

> **Stack:** FastAPI (Python 3.14 / 3.11+) · Supabase (PostgreSQL & Storage) · Vanilla HTML5/CSS3/ES6 · Vercel / Render Deployment  
> **Theme:** Green (`#147A47`) + Light Blue (`#5BB8E8`) + White (`#FFFFFF`) · Glassmorphism & High-Tech Aesthetics

---

## 🚀 Live Demo & Route Directory

| Route | Type | Description |
|---|---|---|
| `/` | Page | **JM Vertex Landing Page** with live countdown pass, four tracks, timeline, live team counter, FAQ accordion, and pre-registration alerts. |
| `/register` | Page | **3-Step Registration Wizard** (Team & Crew composition, Idea Submission with live char counters & PPT upload, Review & Payment with mandatory Terms consent). |
| `/terms` | Page | **Full Terms & Conditions** detailing IP ownership, R&D rights, data privacy, and refund policies. |
| `/confirmation/{team_code}` | Page | **Official Team Access Pass & Payment Receipt** with a printable ticket layout, barcode/QR visual, and Print/Save as PDF. |
| `/admin/login` | Page | **Minimal, Secure Admin Authentication Portal** (hashed credential verification & session cookies). |
| `/admin` | Page | **Minimal Admin Command Center** with 6 metrics cards, live search, multi-filters (track, review status, payment status), team dossier modal with instant auto-saving status/notes, and 1-click Excel/CSV export. |
| `/download/idea-template` | File | Serves the official 5-slide PowerPoint deck template (`.pptx`). |
| `/robots.txt` & `/sitemap.xml` | SEO | Complete search engine crawling and indexing configuration. |

---

## ⚡ Quick Start (Local Run)

### 1. Setup Virtual Environment & Install Dependencies
```bash
# Windows PowerShell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 2. Configure Environment
```bash
cp .env.example .env
```
*(The application features a built-in automated local fallback database (`data/hackathon.db`). Razorpay API keys are required to accept registration payments.)*

### 3. Seed Sample Teams (Optional Demonstration)
```bash
python scripts/seed_data.py
```

### 4. Launch Development Server
```bash
python -m app.main
```
Open **[http://127.0.0.1:8000](http://127.0.0.1:8000)** in your browser.

---

## ☁️ What Data to Collect & Provide for Supabase

To connect your live Supabase project to the website, create a free project at [supabase.com](https://supabase.com) and collect these **5 items**:

1. **`SUPABASE_URL`**:
   - Go to **Project Settings** → **API**.
   - Copy the **Project URL** (e.g. `https://your-project-id.supabase.co`).
2. **`SUPABASE_SERVICE_KEY`**:
   - In **Project Settings** → **API**, find **Project API Keys**.
   - Copy the **`service_role`** key (secret key for server-side operations that bypasses RLS). *Never expose this in client-side code.*
3. **`SUPABASE_BUCKET`**:
   - Go to **Storage** in the left sidebar.
   - Click **New Bucket**, name it `hackathon-ideas`, and keep it **Private** (checked).
4. **Run the Database Schema**:
   - Go to **SQL Editor** in Supabase.
   - Copy and paste the entire contents of `supabase/schema.sql`.
   - Click **Run** (creates the `registrations` table, `preregistration_alerts` table, team code sequence `team_code_seq`, triggers, and indexes).
5. **Admin & Payment Keys**:
   - Provide your chosen `ADMIN_USERNAME` and `ADMIN_PASSWORD`.
   - Provide your `RAZORPAY_KEY_ID` and `RAZORPAY_KEY_SECRET` (from Razorpay Dashboard → Settings → API Keys in Test Mode).

Add these into your `.env` file locally or your **Vercel / Render Environment Variables**.

---

## 🌐 Deploying to Vercel

The repository includes `vercel.json` and `api/index.py` configured for Vercel Serverless Python runtime:

1. Push your repository to GitHub / GitLab.
2. In the [Vercel Dashboard](https://vercel.com), click **Add New** → **Project** and select this repository.
3. In **Settings** → **Environment Variables**, add:
   - `APP_ENV` = `production`
   - `SECRET_KEY` = `<random-32-char-string>`
   - `ADMIN_USERNAME` = `<your-admin-user>`
   - `ADMIN_PASSWORD` = `<your-admin-pass>`
   - `SUPABASE_URL` = `<your-supabase-url>`
   - `SUPABASE_SERVICE_KEY` = `<your-supabase-service-key>`
   - `SUPABASE_BUCKET` = `hackathon-ideas`
   - `RAZORPAY_KEY_ID` = `<your-rzp-key>`
   - `RAZORPAY_KEY_SECRET` = `<your-rzp-secret>`
   - `FORCE_UNLOCK_REGISTRATION` = `false`
4. Click **Deploy**. Vercel will build and assign your live production URL!

---

## 🛡️ Security Architecture & Privacy

- **Zero Client Secrets**: No API keys, database secrets, or admin credentials exist in frontend code.
- **Server-Side Enforcement**: Uniqueness of team names, 4–6 crew member capacity, character constraints, file extensions, and mandatory Terms & Conditions checkbox consent are validated strictly on the server (HTTP 422 on violations).
- **Private Presentation Storage**: Uploaded decks are saved under randomized UUID filenames in private Supabase Storage (`hackathon-ideas`) or protected server storage. Files are never publicly browsable and can only be downloaded by authenticated organizers via `GET /api/admin/registration/{id}/file`.
- **Payment Verification**: Payments cannot be faked. Transactions require cryptographic HMAC signature verification from Razorpay.
- **Session Protection**: Admin sessions use tamper-proof HMAC tokens signed with `itsdangerous` stored in HttpOnly, SameSite cookies.
- **Defensive Headers**: `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: strict-origin-when-cross-origin`, and slowapi rate limiting.
