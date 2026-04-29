# Market Research Prompt - Job Application Workflow Setup

## How to use this prompt

Open Claude.ai with Deep Research activated. Fill in every field marked with brackets before sending. Do not modify the section structure - the utility workflow expects these exact sections to extract `role_type_scores` and other structured data.

Before sending, replace these placeholders:

- `[TARGET ROLE]` - the main role or career target (e.g. Werkstudent Data Engineering, Junior Backend Developer, Product Manager, Data Analyst)
- `[TARGET COUNTRY / MARKET]` - the country or hiring market to research (e.g. Germany, DACH, UK, Netherlands)
- `[CURRENT PROFILE SUMMARY]` - the candidate's current education, experience, skills, constraints, and known gaps
- `[LOCATION]` - the candidate's home base and realistic commute or relocation area
- `[AVAILABILITY / CONTRACT TYPE]` - the desired format (e.g. Werkstudent 15-20h/week, full-time junior, internship, part-time, remote-only)
- `[LANGUAGES]` - languages and levels relevant to hiring in the target market

---

## The prompt

You are a job market analyst. Conduct deep research on the current job market for the candidate profile below and produce a structured report I will use to configure an AI job application assistant.

**Candidate profile:**
- Target role: [TARGET ROLE]
- Target country / market: [TARGET COUNTRY / MARKET]
- Current profile summary: [CURRENT PROFILE SUMMARY]
- Location: [LOCATION]
- Availability / contract type: [AVAILABILITY / CONTRACT TYPE]
- Languages: [LANGUAGES]

**Research requirements:**

Search actively for current data from the last 6 months where possible. Use sources relevant to [TARGET COUNTRY / MARKET], including major local job portals, international job portals, public employment agencies, industry reports, recruiting firms, company career pages, professional associations, and salary databases.

For Germany / DACH, useful sources may include LinkedIn, Indeed, StepStone, Glassdoor, Campusjaeger, Workwise, Bitkom, IW Koeln, Ratbacher, Luenendonk, Gehalt.de, Kununu, and employer career pages. For other markets, choose equivalent local sources instead of forcing German sources.

Cite specific numbers with sources in parentheses. Do not estimate without a source - if data is unavailable for a sub-point, say so explicitly rather than omitting or guessing.

The report must be specific to [TARGET ROLE], [TARGET COUNTRY / MARKET], [LOCATION], [AVAILABILITY / CONTRACT TYPE], [LANGUAGES], and [CURRENT PROFILE SUMMARY]. Do not assume the candidate is a student, junior candidate, software developer, or Germany-based unless the profile says so.

Produce a report with exactly these seven sections in this order:

**Section 1: Market size and role distribution**
- How many active postings exist in [TARGET COUNTRY / MARKET] for the target role right now
- How many postings exist for each adjacent role type (list every relevant type)
- Ratio of contract formats relevant to [AVAILABILITY / CONTRACT TYPE] for this role, such as full-time vs part-time, internship vs student job, permanent vs contract, remote vs hybrid vs on-site, or other locally relevant formats
- Which portals have the highest posting volume for this role type
- Seasonal patterns if relevant (semester start, graduate cycles, fiscal-year hiring, industry cycles, internship cycles, or other target-specific patterns)

**Section 2: Regional breakdown**
- Which cities and regions have the highest concentration of relevant postings (with numbers)
- Commute viability from the candidate's location to each major region
- Remote and hybrid availability percentage by region
- Language requirements by region, including where the local language, English, or other languages are mandatory vs optional
- Specific employers per region worth targeting

**Section 3: Salary data**
- Compensation range for the target role by region, using the format relevant to [AVAILABILITY / CONTRACT TYPE] and [TARGET COUNTRY / MARKET] (hourly, monthly, annual gross, day rate, internship stipend, or local equivalent)
- Sector-specific variations (finance vs. consulting vs. tech vs. industry, or other sectors relevant to [TARGET ROLE])
- How profile level affects compensation (student vs graduate, junior vs mid-level, degree level, years of experience, portfolio strength, certifications, or other relevant factors)
- Negotiation floor the candidate should not go below
- Ceiling that is realistic for this profile without overstating experience

**Section 4: Role landscape and bridge paths**

This section is critical. For every role type the candidate might encounter in their job search, provide:
- Exact role type name as it appears in job postings
- Posting frequency in the target market: high / medium / low / rare
- Bridge quality toward the target role: strong / moderate / weak / none
- Explanation of why the bridge quality is what it is
- Typical skill, tool, domain, responsibility, or seniority overlap with the candidate profile

List all role types ordered from most to least aligned with the target role. Include both primary target roles and every realistic adjacent or bridge role. Do not omit roles that appear frequently even if they are weak bridges - the candidate needs to know about them.

**Section 5: Required vs. differentiating skills**
- Skills, qualifications, domain knowledge, credentials, tools, or experience that appear in 70% or more of postings for the target role (must-haves)
- Skills, qualifications, domain knowledge, credentials, tools, or experience that appear in 30-60% of postings (differentiators that separate candidates)
- Strengths the candidate has that are explicitly valued in this market
- Gaps the candidate has that are frequently required, ordered by how often they appear as hard requirements vs. nice-to-have

**Section 6: Known gaps and how to frame them**

For each gap relevant to this candidate profile:
- How commonly it appears as a hard requirement vs. a nice-to-have
- Whether candidates without hands-on experience, formal credentials, or direct background in that area are regularly hired anyway
- The honest framing that works in a cover letter or interview for this specific gap
- Whether acquiring surface-level knowledge, a certificate, a portfolio project, or adjacent experience meaningfully changes the candidate's position

**Section 7: Market timing and competition**
- Current market tightness for this role type (employer market vs. candidate market)
- Estimated application-to-interview conversion rate for candidates at this profile level
- Average time from application to start date
- Whether selectivity is increasing or decreasing compared to 12 months ago
- Any structural factors affecting the market in the next 6 months (economic, regulatory, AI impact, sector-specific hiring cycles, visa or work authorization changes if relevant)

**Output format:**

Structured prose with clear section headers. Include specific numbers with sources cited inline in parentheses. Where you find conflicting data across sources, report both and note the discrepancy. Be specific - no generic statements without supporting data. Minimum 2,000 words. No maximum - completeness takes priority over brevity.

---

## After you receive the output

Send the complete output including all sections through `POST /profile-setup` in `utility-extract-profile.json` using the `market_research` field.

Include `profile_id` when updating an existing profile.

Then run the workflow to regenerate `candidate_profile` and `role_type_scores` and persist the updated source text back to `candidate_context`.

Do not update the `candidate_context` table manually for this normal refresh flow. The utility workflow treats the webhook payload as the source of truth and will overwrite the stored `market_research` value on the next run.

See `config/candidate_context_template.md` for the `market_research` key details.

---

## When to regenerate

Run this prompt again when any of these conditions are true:
- The research is older than 4 months
- You change your target role, target market, contract type, or target region
- A significant market event occurs (major layoffs, economic shift, new visa rules)
- Your `role_type_scores` no longer reflect what you are seeing in actual job postings
