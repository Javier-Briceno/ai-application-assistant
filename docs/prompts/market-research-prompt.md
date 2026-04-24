# Market Research Prompt — Job Application Workflow Setup

## How to use this prompt

Open Claude.ai with Deep Research activated. Fill in the four fields marked with brackets before sending. Do not modify the section structure — the utility workflow expects these exact sections to extract `role_type_scores` and other structured data.

---

## The prompt

You are a job market analyst. Conduct deep research on the current job market for the candidate profile below and produce a structured report I will use to configure an AI job application assistant.

**Candidate profile:**
- Target role: [e.g. Werkstudent Data Engineering]
- Current profile summary: [e.g. CS student 5th semester, Python/SQL/Docker/PostgreSQL/Node.js, GPA 1.7, no cloud experience]
- Location: [e.g. Siegen, NRW, Germany]
- Availability: [e.g. Werkstudent 15–20h/week]
- Languages: [e.g. German C1, English C1, Spanish native]

**Research requirements:**

Search actively for current data from the last 6 months where possible. Use job portals (LinkedIn, Indeed, StepStone, Glassdoor, Campusjäger, Workwise), industry reports (Bitkom, IW Köln, Ratbacher, Lünendonk), company career pages, and salary databases (Gehalt.de, Glassdoor, Kununu) as primary sources. Cite specific numbers with sources in parentheses. Do not estimate without a source — if data is unavailable for a sub-point, say so explicitly rather than omitting or guessing.

Produce a report with exactly these seven sections in this order:

**Section 1: Market size and role distribution**
- How many active postings exist nationally for the target role right now
- How many postings exist for each adjacent role type (list every relevant type)
- Ratio of Werkstudent to Praktikum postings for this role
- Which portals have the highest posting volume for this role type
- Seasonal patterns if relevant (semester start, hiring cycles)

**Section 2: Regional breakdown**
- Which cities and regions have the highest concentration of relevant postings (with numbers)
- Commute viability from the candidate's location to each major region
- Remote and hybrid availability percentage by region
- Language requirements by region (where German is mandatory vs. optional)
- Specific employers per region worth targeting

**Section 3: Salary data**
- Hourly rate range for the target role by region, gross (Werkstudent format)
- Sector-specific variations (finance vs. consulting vs. tech vs. industry)
- How profile level affects rate (Bachelor vs. Master, semester)
- Negotiation floor the candidate should not go below
- Ceiling that is realistic for this profile without experience

**Section 4: Role landscape and bridge paths**

This section is critical. For every role type the candidate might encounter in their job search, provide:
- Exact role type name as it appears in job postings
- Posting frequency in the target market: high / medium / low / rare
- Bridge quality toward the target role: strong / moderate / weak / none
- Explanation of why the bridge quality is what it is
- Typical tech stack overlap with the candidate profile

List all role types ordered from most to least aligned with the target role. Include both primary target roles and every realistic adjacent or bridge role. Do not omit roles that appear frequently even if they are weak bridges — the candidate needs to know about them.

**Section 5: Required vs. differentiating skills**
- Skills that appear in 70% or more of postings for the target role (must-haves)
- Skills that appear in 30–60% of postings (differentiators that separate candidates)
- Skills the candidate has that are explicitly valued in this market
- Skills the candidate lacks that are frequently required, ordered by how often they appear as hard requirements vs. nice-to-have

**Section 6: Known gaps and how to frame them**

For each skill gap relevant to this candidate profile:
- How commonly it appears as a hard requirement vs. a nice-to-have
- Whether candidates without hands-on experience are regularly hired anyway
- The honest framing that works in a cover letter or interview for this specific gap
- Whether acquiring surface-level knowledge meaningfully changes the candidate's position

**Section 7: Market timing and competition**
- Current market tightness for this role type (employer market vs. candidate market)
- Estimated application-to-interview conversion rate for junior candidates at this level
- Average time from application to start date
- Whether selectivity is increasing or decreasing compared to 12 months ago
- Any structural factors affecting the market in the next 6 months (economic, regulatory, AI impact)

**Output format:**

Structured prose with clear section headers. Include specific numbers with sources cited inline in parentheses. Where you find conflicting data across sources, report both and note the discrepancy. Be specific — no generic statements without supporting data. Minimum 2,000 words. No maximum — completeness takes priority over brevity.

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
- You change your target role or target region
- A significant market event occurs (major layoffs, economic shift, new visa rules)
- Your `role_type_scores` no longer reflect what you are seeing in actual job postings
