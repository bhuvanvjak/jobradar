# Job Radar

Watches company job boards, scores every opening against your resume, and
emails you when something worth applying to shows up.

![grid](docs/grid.png)

It tracks 56 companies across seven ATS platforms — Greenhouse, Lever, Ashby,
Workable, Workday, Oracle Recruiting Cloud — which is what it takes to cover
both startups and large enterprises on one list.

## What it does

- **Finds new openings.** Every job gets a stable id, so "new" means new.
- **Notices when jobs close.** A posting that disappears is marked dead and hidden.
- **Ranks against your resume.** 0–10 with a reason, from an LLM that reads the
  job description.
- **Daily alerts** for a shortlist of companies — email plus a desktop notification.
- **Weekly digest** every Monday, ranked.
- **A local web UI** to search and filter everything.

![email](docs/email.png)

## Why it isn't just keyword matching

Two rules run in code, not in the prompt, because a model asked nicely will
comply inconsistently:

**Seniority.** A Senior/Staff/Principal title caps at 3/10 however well the
skills match. Without this, senior roles held 31 of the top 100 slots and the
first junior role sat at position #67 — the jobs a new graduate could actually
get were buried under the ones they could not.

**Relevance.** A role weak on both skills and domain caps at 3/10. Otherwise a
branch-office internship scores 8/10 for a developer purely because it is an
internship.

Both are arithmetic on data already stored, so `recap` re-applies them for free.

## Setup

Needs Python 3.11+ and a Mac (the schedules use launchd).

```bash
git clone https://github.com/suvamneog/jobradar.git
cd jobradar
./install.sh
```

Then three things:

**1. Your resume** — put a PDF in the folder, point `resume_path` at it in
`config.yaml`.

**2. Your keys** — `cp run.example.sh run.sh`, then fill in:

- An LLM key. Any OpenAI-compatible endpoint works; the default is
  [xkiro](https://xkiro.com) with Mistral Large 3, which has a free tier.
- A [Gmail App Password](https://myaccount.google.com/apppasswords) for sending
  mail. Needs 2FA on the account first.

**3. Check it works**

```bash
./run.sh test          # sends a test email
./run.sh scan          # fetch, diff, score
./run-web.sh           # http://localhost:8765
```

## Windows setup (added in this fork)

The upstream project assumes a Mac (launchd schedules, bash scripts). This
fork adds a Windows-native path alongside it - same Python package, same
`config.yaml`, different shell and scheduler.

```powershell
cd "C:\Randomchetta\Hook or Crook\jobradar"
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
copy config.example.yaml config.yaml     # already pre-filled with a starter
                                          # company list and Groq as the LLM -
                                          # see "Auto-apply module" below
copy run.example.ps1 run.ps1             # then edit run.ps1 and fill in your keys
```

Put your resume at the path `resume_path` points to in `config.yaml`
(PDF or plain text both work). Then:

```powershell
.\run.ps1 test          # sends a test email - proves SMTP works
.\run.ps1 scan          # fetch, diff, score
.\run.ps1 webui         # jobradar's own scoring dashboard - http://localhost:8765
```

To schedule the daily/weekly jobs the way `install.sh` does on a Mac, use
Windows Task Scheduler instead of launchd - see "Auto-apply module" below
for the scheduler script this fork adds (it also covers `scan`/`apply`).

## Configuration

```yaml
companies:
  - { name: 'Adobe', board: workday, slug: 'adobe/wd5/external_experienced' }

alerts:
  companies: [Adobe, Oracle, Atlassian]   # checked daily
  min_score: 6

llm:
  provider: xkiro
  model: mistralai/mistral-large-2512
  daily_token_limit: 1000000
```

Find a company's board and slug in its careers URL:

| URL | board | slug |
|---|---|---|
| `boards.greenhouse.io/figma` | greenhouse | `figma` |
| `jobs.ashbyhq.com/ramp` | ashby | `ramp` |
| `jobs.lever.co/spotify` | lever | `spotify` |
| `adobe.wd5.myworkdayjobs.com/external_experienced` | workday | `adobe/wd5/external_experienced` |

Board APIs have name collisions - a guessed slug can resolve to a wrong
company sharing the name (`lever/porter` is a Massachusetts healthcare
staffing firm, not the Indian logistics company; `greenhouse/slice` is a
Balkans customer-support shop, not the Indian fintech). Before trusting a
slug, hit the URL and read a few job locations/titles back:

```powershell
curl.exe "https://boards-api.greenhouse.io/v1/boards/<slug>/jobs" | more
```

## Commands

```bash
./run.sh scan          # fetch, diff, score
./run.sh alert         # check the shortlist, alert if anything opened
./run.sh digest        # send the weekly email
./run.sh recap         # re-apply the scoring rules, no tokens
./run.sh list          # the week's finds in the terminal
./run-web.sh           # web UI
```

`install.sh` registers two launchd jobs: daily alerts at 09:30, weekly digest
Mondays at 09:00.

## Auto-apply module (added in this fork)

Everything above finds and ranks jobs but stops at telling you about them.
This fork adds `jobradar/apply/`, which picks up where the scan leaves off:
for the best unapplied scored jobs, it tailors your resume, writes a cover
letter or cold email with an LLM, and either sends the cold email directly
or queues the job-board application for your one-click approval. Every
application is logged to Notion.

**What gets automated, and what doesn't:**

| Track | Automatic | Needs you |
|---|---|---|
| Cold email | Finds a contact, tailors resume, writes and sends the email, logs it | Sourcing the contact list once |
| Job-board posting | Tailors resume + cover letter, logs it, queues it | One click in the review queue to actually submit |

Job-board applications are never auto-submitted - most ATS platforms
(Workday, Greenhouse, Lever) actively block bots with CAPTCHAs, and
several explicitly prohibit automated applying in their terms of service.
The AI does the writing; you do the final click. Cold email carries no
such restriction (it's just your own outbound email), so it's safe to
send unattended - but review the first batch of drafts by hand (set
`apply.cold_email.send_automatically: false` in `config.yaml` while you
do) before trusting it to run twice a day with nobody watching.

### Setup

**1. Pick your writing model** - `apply.tailor_llm` in `config.yaml`,
independent of the `llm:` block above (which only scores fit). Groq is
free (`console.groq.com/home`, no card) and is the default; Anthropic
costs a few cents a day but is more consistent about not embellishing
your experience - a reasonable path is Groq while you're dialing in your
resume with `--dry-run`, Anthropic once you trust it for live runs.

**2. Create the Notion database** - a table with these exact column names
and types, then **Share → invite your integration** on it:

- `Company` - Title (rename the default title column)
- `Role`, `Location`, `Why It Fits`, `Resume File`, `Letter/Email` - Text
- `Status` - Select: `Pending Review`, `Applied - Cold Email`,
  `Applied - Job Board`, `Skipped`, `Replied`, `Rejected`, `Interview`
- `Channel` - Select: `Cold Email`, `Job Board`
- `Source` - Select: `greenhouse`, `lever`, `ashby`, `workday`, `oracle`,
  `atlassian`, `remotive`, `arbeitnow`
- `Date Applied` - Date
- `Job URL` - URL

Copy the database ID from its URL into `NOTION_DATABASE_ID` in `run.ps1`
(the 32-character string after your workspace name, before `?v=`).

**3. Fill in `apply.candidate`** in `config.yaml` (name/email/phone/
location/links) and, if you want cold email, `data/target_companies.csv`:
`company,contact_name,contact_email,role_title,notes,source_url`. **You
source these contacts yourself** - company site, a tool like Hunter.io,
or an address already printed in a posting - nothing here scrapes or
guesses addresses.

**4. Test, then schedule:**

```powershell
.\run.ps1 scan                              # populate the database first
.\run.ps1 apply --count 5 --dry-run         # calls the LLM for real, sends/logs nothing
.\run.ps1 apply --count 5                   # live run
.\run.ps1 review                            # http://localhost:5055 - approve job-board applications
.\scripts\setup_task_scheduler.ps1          # registers 9 AM / 9 PM Windows Task Scheduler runs
```

Each scheduled run does `scan` then `apply --count 5` - two runs a day,
five jobs each, ten applications a day. Output is appended to
`jobradar.log`. State lives in an `applications` table inside the same
`jobradar.db` SQLite file the scanner already uses (see
`jobradar/apply/applydb.py`) - a job already in that table is never
picked again, so the two daily runs never double-apply.

One accepted simplification: job descriptions come from jobradar's own
`jobs` table, which trims them to 1,500 characters on ingest to keep the
database small across thousands of tracked postings. That's usually
plenty to tailor against - most postings put real requirements up front -
but it's not the full original listing.

## Token budget

Free tiers have a daily cap, so the budget is checked before every request and
recorded per batch. A run that hits the ceiling stops and resumes next time —
it can't lock you out of your key.

Jobs are scored 25 per request with compact positional replies. A full 3,400-job
scan costs about 340K tokens. After that only new postings are scored, which is
a few thousand a week.

## Tests

```bash
for t in tests/test_*.py; do ./.venv/bin/python "$t"; done
```

Ten suites. Most exist because something broke in use — a threading crash in
the live scan, an alert that would have fired 142 notifications at once, a
malformed reply that killed a 3,000-job run.

See [OVERVIEW.md](OVERVIEW.md) for architecture and design notes.

## Notes

Built by [@suvamneog](https://github.com/suvamneog). The grid UI took small
inspiration from [this post](https://x.com/sarvagya_kul/status/2100980770206879849).

Scores are a sort order, not a verdict — a 4/10 is still worth a glance.

MIT
