TwinEnergyAIHome (MVP) — Telegram Energy Assistant



TwinEnergyAIHome is a coursework MVP Telegram bot that helps household users diagnose likely reasons for electricity bill spikes and receive practical energy-saving recommendations.

The project also includes \*\*SQLite-based event logging\*\* to calculate pilot KPIs (funnel conversion, completion rate, return proxy).







1\) Key MVP capabilities

•	Onboarding via `/start` (events: `bot\_start`, `onboarding\_done`)

•	Energy analysis output (event: `analysis\_generated`)

•	Basic command usage tracking (event: `command\_used`)

•	Product analytics in SQLite (`data.db`, table `events`)

•	KPI SQL scripts stored in `sql/` for evidence screenshots (DB Browser for SQLite)







2\) Tech stack

•	Language: Python 3.x

•	Telegram bot framework: see `requirements.txt`

•	Database: SQLite (`data.db`)

•	Development OS: Windows 10/11



Exact library versions are defined in `requirements.txt`.







3\) Project structure

tgproject/

&nbsp; main.py

&nbsp; analytics.py

&nbsp; db.py

&nbsp; utils.py

&nbsp; keyboards.py

&nbsp; texts.py

&nbsp; config.py

&nbsp; requirements.txt



&nbsp; data.db                  # local SQLite database (do NOT commit if it contains user data)

&nbsp; sql/

&nbsp;   kpi\_queries.sql         # KPI queries (completion, funnel conversion, return proxy)

&nbsp; screenshots/              # evidence screenshots (DB Browser outputs, KPI tables, bot flow)







4\) Setup \& Run (Windows)



4.1 Create and activate virtual environment

python -m venv .venv

.venv\\Scripts\\Activate.ps1



4.2 Install dependencies

pip install -r requirements.txt



4.3 Configure environment variables

Create a `.env` file in the project root (do NOT commit it). Use `.env.example` as a template.



4.4 Run the bot

python main.py







5\) Environment variables



Create `.env` (not tracked by git):



BOT\_TOKEN=PASTE\_YOUR\_TELEGRAM\_BOT\_TOKEN\_HERE

DB\_PATH=./data.db



Template file (tracked by git): `.env.example`







6\) Data storage (SQLite) and evidence



6.1 SQLite file

•	Database file: `data.db`

•	Used for storing event logs needed for KPI calculations and practical evidence.



6.2 Events table (analytics)

Main analytics table: `events`



Current columns (as in DB):

•	`id` (INTEGER, PK)

•	`ts\_utc` (TEXT)

•	`user\_hash` (TEXT) — anonymized identifier

•	`session\_id` (TEXT)

•	`state` (TEXT)

•	`event\_name` (TEXT) — examples: `bot\_start`, `onboarding\_done`, `analysis\_generated`

•	`command` (TEXT) — examples: `/start`, `/demo`

•	optional: `meta` (TEXT) — can store user feedback rating 1–5



6.3 KPI queries (for report evidence)

KPI SQL scripts are stored in:

•	`sql/kpi\_queries.sql`



Recommended KPI screenshots for the report:

•	event distribution: `event\_name` + counts

•	funnel conversion (start → onboarding → analysis)

•	completion rate

•	return proxy metric (if verified savings is not implemented)

•	DB schema screenshot (table `events`)







7\) How to generate KPI evidence (DB Browser for SQLite)

1\) Open DB Browser for SQLite

2\) Open database file: `data.db`

3\) Go to \*\*Execute SQL\*\*

4\) Run queries from `sql/kpi\_queries.sql`

5\) Save screenshots to `screenshots/`







8\) Repository hygiene (important for final grade)



8.1 Do NOT commit secrets

•	Never commit `.env` with `BOT\_TOKEN`



8.2 Do NOT commit runtime artifacts

•	Ignore `\_\_pycache\_\_`, `.venv`, `.idea`



8.3 Recommended `.gitignore`

\_\_pycache\_\_/

\*.pyc

.venv/

.idea/

.env

\*.db

\*.sqlite

\*.sqlite3







9\) License

Coursework / educational project.



