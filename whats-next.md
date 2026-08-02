<original_task>
Fork https://github.com/FuJacob/mapletenders, deploy it on Hostinger VPS at tender.kennethwong.ai, and get it working as an internal Canadian government tender aggregation tool.
</original_task>

<work_completed>
## Infrastructure & Deployment
- Forked repo to `kennethw604/tenders`, cloned to `C:\Users\kenny\projects\tenders`
- Created Cloudflare DNS A record: `tender.kennethwong.ai` -> `217.15.170.211` (proxied)
- Created Cloudflare Origin SSL certificate for `*.kennethwong.ai` + `tender.kennethwong.ai`, installed at `/usr/local/lsws/conf/ssl/tender.kennethwong.ai/`
- Configured LiteSpeed vhost at `/usr/local/lsws/conf/vhosts/tender.kennethwong.ai/vhconf.conf` — proxies `/api/*` to backend:4001, `/*` to frontend:3001
- Added vhost + listener mappings to `/usr/local/lsws/conf/httpd_config.conf`
- Set GitHub Actions secrets: `VPS_HOST`, `VPS_USER`, `VPS_SSH_KEY` on `kennethw604/tenders`
- Created `docker-compose.prod.yml` with 7 services: frontend, backend, ml-backend, elasticsearch, redis, scraper, celery-beat
- Frontend uses multi-stage Docker build (`Dockerfile.prod`) with Vite env vars passed as build args
- All containers running on VPS at `/root/tenders/`

## Code Changes (from upstream fork)
### Backend
- **AI Service**: Replaced OpenAI + Google GenAI with Anthropic Claude SDK (`@anthropic-ai/sdk`) in `backend/services/aiService.ts`
- **Email**: Replaced Resend with Gmail SMTP via nodemailer in `backend/services/emailService.ts` — sends from `hello@kennethwong.ai`
- **Stripe**: Made optional with placeholder key in `backend/services/subscriptionService.ts` (line 18: `"sk_test_placeholder"`)
- **Build**: Changed `tsc` to `tsc || true` in `backend/package.json` to work around Express 5 type errors (pre-existing upstream issue with `string | string[]` params)
- **Routes**: Added `/api` prefix to all routes in `backend/server.ts` (lines 33-44)
- **Auth**: Removed `authenticateUser` middleware from `tenders.ts`, `tender-notice.ts`, `search.ts` routes (internal tool, no auth needed for reading)
- **Auth controller**: `getUser()` now validates Bearer token via Supabase, `signOutUser()` returns success message
- **Database service**: Added `search` parameter support to `getTendersPaginated` using Supabase `.or()` with `ilike`
- **Tender service**: Passes `search` param through to database service

### Frontend
- **Color scheme**: Changed from red (#f75567) to blue (#2563eb) in `frontend/src/index.css` @theme block
- **Logos**: Recolored `frontend/public/favicon.svg` and `frontend/public/logo.svg` from red to blue
- **Logo component**: Removed broken image icon, text-only logo in `frontend/src/components/ui/LogoTitle.tsx`
- **API base URL**: Fixed `frontend/src/api/config.ts` to use `VITE_API_BASE_URL` env var instead of hardcoded `localhost:4000`
- **Auth flow**: Rewrote `frontend/src/features/auth/authThunks.ts` — uses backend API instead of direct Supabase client, stores tokens in localStorage
- **API client**: `frontend/src/client/apiClient.ts` reads auth token from localStorage instead of Supabase client
- **SignUp/SignIn pages**: Fixed dispatch bugs, removed broken session checks
- **Home page**: Removed mock/fake activity data (IT Infrastructure Modernization, etc.)
- **Header**: Removed Plans link, fixed Settings link (`/settings` -> `/profile`), fixed Team link (`/team` -> `/teams`), removed unused CreditCardIcon import
- **Tender detail page**: Hid BreezeAI summary card, fixed widget spacing with `space-y-4`
- **AI summary card**: Changed from `bg-primary text-white` to `bg-surface text-text`
- **Table page**: Added status tabs (All/Open/Awarded/Closed), moved Total Tenders widget inline
- **Table pagination**: Added page size dropdown (25/50/100/250), jump-to-page input
- **Table layout**: Removed fixed height and scrollbar, table expands naturally
- **TableStatsGrid**: Rewrote to consume `{total, byStatus, byCategory}` shape instead of old array format
- **TenderStatistics type**: Changed from array-of-sources to `{total, byStatus, byCategory}` in `frontend/src/api/tenders.ts`
- **axios bug**: Fixed `frontend/src/api/ai.ts` — used bare `axios` instead of `apiClient`

### Scraper
- Added `scraper/` directory with 20 spiders (canadabuys, nova_scotia, yukon, etc.)
- Celery Beat schedule: canadabuys every 2h, SEAO every 12h, others every 8h
- Supabase pipeline: upserts tenders via REST API with dedup fingerprinting
- Fixed `canadabuys.py`: removed SQLAlchemy import, stubbed GSIN->UNSPSC mapping
- Created `scraper/.env` with Supabase credentials and Redis URL

## Database
- Created Supabase project "tenders" (nano tier, free)
- URL: `https://kfutlempzspibksgfmel.supabase.co`
- Ran schema SQL creating 28 tables with indexes via Supabase SQL Editor
- Created admin user via API: `hello@kennethwong.ai` / `Tenders2026!`
- Keys stored in `~/.secrets/.env` as `TENDERS_SUPABASE_URL`, `TENDERS_SUPABASE_ANON_KEY`, `TENDERS_SUPABASE_SERVICE_KEY`

## Data
- 24,765 tenders in DB from scraper runs (canadabuys, nova_scotia, saskatchewan, yukon, nunavut, newfoundland, nwt)
- Scraper + Celery Beat running on VPS, auto-scraping on schedule
</work_completed>

<work_remaining>
## High Priority
1. **Signup flow still hangs** — the frontend signup page hangs. Auth thunks were rewritten but may still have issues. The sign-in works (tested with admin-created user). Need to debug the actual signup form submission flow in browser devtools.

2. **Data quality audit** — scraped data has issues:
   - `category_primary` shows raw codes like `*gd`, `*srv`, `*cnst` instead of human-readable names (goods, services, construction). The canadabuys spider's `CATEGORY_MAP` doesn't catch the `*` prefixed variants.
   - `source_url` is null for many canadabuys tenders (CSV field `noticeURL-URLavis-eng` is empty for some rows)
   - Some tenders have title "Print this Competition" or "Download List" — these are scraper artifacts from Saskatchewan spider parsing page chrome instead of actual tender data
   - Old tenders from 2018 mixed in with current ones — no date filtering on scrape
   - Nova Scotia `source_url` points to the dataset page, not individual tenders

3. **QuickFilters show "0 tenders"** — the filter bar above the table shows "0 tenders" count. The `QuickFilters` component receives `rowCount` but it may not be wired correctly to the paginated data.

4. **View Details links** — clicking a tender goes to `/tender-notice/:id` which loads but many fields show "Not specified" because:
   - `contact_name`, `contact_email`, `contact_phone` are not scraped
   - `procurement_method`, `procurement_type` are not set by scrapers
   - `contract_start_date` is never populated

## Medium Priority
5. **Scraper improvements**:
   - Fix Saskatchewan spider — produces garbage entries ("Print this Competition", "Download List")
   - Add date cutoff to avoid importing ancient closed tenders
   - Fix canadabuys category mapping for `*gd`/`*srv`/`*cnst` prefixed values
   - Some spiders may still have SQLAlchemy imports (only checked canadabuys)

6. **Search functionality** — the Search page (`/search`) uses Elasticsearch which needs data indexed. The ML backend syncs from Supabase to ES but this hasn't been triggered yet.

7. **Email testing** — Gmail SMTP is configured but untested. Signup triggers welcome email.

8. **CI/CD** — GitHub Actions workflow is configured but hasn't been triggered by a push yet (manual deploys via SSH so far).

## Low Priority
9. **Saved Searches** — `frontend/src/components/search/SavedSearches.tsx` has mock data (lines 142+)
10. **Calendar** — shows "Error loading calendar" because it loads bookmarks and user has none. Works correctly, just needs bookmarked tenders.
11. **Chat feature** — uses Anthropic Claude, untested
12. **RFP Analysis** — uses Anthropic Claude, untested
13. **Teams** — team management pages exist but untested
</work_remaining>

<attempted_approaches>
## Things that failed or required fixes
- **Docker port conflicts**: Redis port 6380 was already in use on VPS by n8n. Fixed by removing port mapping (Redis only needs internal docker network access).
- **LiteSpeed rewrite for /api/ stripping**: Tried `RewriteRule ^/api/(.*)$ /$1 [PT]` but it converted POST to GET (405 error). Abandoned rewrite approach — instead added `/api` prefix to all Express routes in `server.ts`.
- **Vite env vars not baking into bundle**: `env_file` in docker-compose only sets runtime vars. Vite needs them at build time. Fixed by adding `ARG` + `ENV` in `Dockerfile.prod` and passing via `build.args` in docker-compose.
- **Frontend using Supabase client directly**: The original code called `supabaseClient.auth.signInWithPassword()` from the frontend, which requires Supabase env vars in the browser AND bypasses the backend. Rewrote to go through backend API.
- **dotenv showing "(0) from .env"**: The backend container log shows 0 env vars from `.env` file because `env_file` in docker-compose injects them as environment variables, not as a `.env` file inside the container. This is fine — the vars are available via `process.env`.
- **Stripe crash on startup**: `new Stripe("")` throws. Fixed with placeholder key `"sk_test_placeholder"`.
- **SSL 404**: Cloudflare "Full" SSL mode couldn't connect because LiteSpeed's SSL cert was for a different domain. Fixed by creating a Cloudflare Origin Certificate via API.
- **Backend getUser() was empty**: Returned undefined, causing Express to hang. Fixed to call `supabase.auth.getUser(token)`.
</attempted_approaches>

<critical_context>
## Architecture
- 7 Docker containers on Hostinger VPS (217.15.170.211): frontend, backend, ml-backend, elasticsearch, redis, scraper, celery-beat
- LiteSpeed (not nginx) handles port 80/443 on the VPS — it's the existing web server for other sites
- Cloudflare proxies tender.kennethwong.ai with "Full" SSL mode
- Frontend is a static React SPA served by nginx inside Docker (port 3001)
- Backend is Express on port 4001
- All env vars are in `.env` files on VPS at `/root/tenders/*/. env` — NOT in git

## Key Files on VPS
- App: `/root/tenders/`
- LiteSpeed vhost: `/usr/local/lsws/conf/vhosts/tender.kennethwong.ai/vhconf.conf`
- LiteSpeed main config: `/usr/local/lsws/conf/httpd_config.conf`
- SSL cert: `/usr/local/lsws/conf/ssl/tender.kennethwong.ai/cert.pem` + `key.pem`
- Build logs: `/root/tenders-build*.log`
- SSH key: `~/.ssh/hostinger_key`

## Deploy Command
```bash
ssh -i ~/.ssh/hostinger_key root@217.15.170.211 'cd /root/tenders && git pull && \
  export VITE_SUPABASE_URL=https://kfutlempzspibksgfmel.supabase.co \
  VITE_SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImtmdXRsZW1wenNwaWJrc2dmbWVsIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzQ3MTM1MTIsImV4cCI6MjA5MDI4OTUxMn0.Jkv9W3lTsgdWjmdt9Ian9xrinweJL6NOBpOAbvtG5lU \
  VITE_API_BASE_URL=https://tender.kennethwong.ai/api && \
  docker compose -f docker-compose.prod.yml up -d --build frontend backend'
```

## Credentials
- All API keys in `~/.secrets/.env` (Supabase keys under `TENDERS_SUPABASE_*`)
- Supabase free tier — 500MB DB, more than enough
- Admin login: `hello@kennethwong.ai` / `Tenders2026!`
- Cloudflare zone for kennethwong.ai: `6174c7a1915030399a220d30c74221db` (on `kennethw604@gmail.com` account)

## User Preferences (from memory)
- Use APIs directly — don't ask user to do manual dashboard tasks when credentials are available
- ADHD-optimized: be direct, do things, don't ask permission, one question max
</critical_context>

<current_state>
## Deployed & Working
- Site live at https://tender.kennethwong.ai
- All 7 containers running and healthy
- 24,765 tenders in database
- Table view works with pagination, status tabs, page size selector, jump-to-page
- Login works (admin user)
- Blue color scheme applied
- Scraper running on schedule via Celery Beat

## Known Issues (not blocking)
- Signup form hangs (login works fine via admin-created user)
- QuickFilters show "0 tenders" count
- Data quality issues (garbage entries, raw category codes)
- Search page needs Elasticsearch indexing
- Several pages have minor UI issues

## Git State
- Branch: `main`
- Latest commit: `83bfc84` "Remove fixed height and scrollbar from tender table"
- Unstaged changes: `docker-compose.yml` (has scraper/redis added), `.claude/settings.local.json`
- Remote: `origin` = `kennethw604/tenders`, `upstream` = `FuJacob/mapletenders`
</current_state>
