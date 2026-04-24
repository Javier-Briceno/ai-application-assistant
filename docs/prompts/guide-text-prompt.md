# Guide Text Prompt — Job Application Workflow Setup

## How to use this prompt

Open Claude.ai with Deep Research activated. Before sending, replace every placeholder in brackets:

- `[TARGET COUNTRY]` — the target country (e.g. Germany, Switzerland, Austria)
- `[DOCUMENT NAME]` — the document type (e.g. Anschreiben, cover letter, letter of motivation)
- `[DOCUMENT LANGUAGE]` — the language in which the document itself should be written and in which all document examples must appear (e.g. Deutsch, English)
- `[OUTPUT LANGUAGE]` — the language of the guide itself (e.g. English, Español)

Important notes before sending:
- The guide must reflect the real recruiting standards of `[TARGET COUNTRY]`, not generic UK/US or international advice.
- If the job is in a non-English-speaking country but the application is written in English, the research must explain how recruiters in `[TARGET COUNTRY]` typically evaluate an English-language `[DOCUMENT NAME]` in their own local hiring context.
- The output must clearly distinguish whether expectations follow:
  1. local recruiting norms,
  2. international corporate conventions,
  3. or a hybrid of both.
- `[DOCUMENT LANGUAGE]` is the language of all templates, model sentences, and document examples.
- The guide itself must be written in `[OUTPUT LANGUAGE]`.

**For Germany / Anschreiben:** the guide is already included in this workflow. Only run this prompt if you are changing country, document type, or document language. The existing guide already covers DACH recruiting standards for 2025–2026.

Do not modify the section structure, headings, or ordering under any circumstance — the Generator node expects a guide with fully consistent formatting across all sections.

---

## The prompt

Act as a senior recruiter and application-documents coach with expertise in the hiring market of [TARGET COUNTRY], focused on real and current recruiting standards rather than generic advice.

Your task is to conduct thorough, practical, and up-to-date research on:

"How to write an excellent [DOCUMENT NAME: e.g. cover letter / Anschreiben / letter of motivation] for jobs in [TARGET COUNTRY], according to real and current recruiting standards in that market."

## Final objective
Provide me with an actionable, concrete, and up-to-date guide to writing an excellent [DOCUMENT NAME] for applications in [TARGET COUNTRY], based on actual hiring practices in that country.

## Important context
- The guide must reflect the recruiting reality of [TARGET COUNTRY], not generic UK/US or international advice.
- The job may be advertised in [DOCUMENT LANGUAGE], including English.
- If the application language is English but the job is located in a non-English-speaking country, explain how recruiters in [TARGET COUNTRY] typically evaluate an English-language [DOCUMENT NAME] in their own hiring context.
- Explicitly distinguish whether expectations follow:
  1. local recruiting norms,
  2. international corporate conventions,
  3. or a hybrid of both.

## Research instructions
- Prioritize recent and reliable sources from [TARGET COUNTRY].
- Give priority to:
  1. official employment bodies or public agencies,
  2. recognized universities or career services in [TARGET COUNTRY],
  3. major job portals used in [TARGET COUNTRY],
  4. well-established recruiting or HR firms in [TARGET COUNTRY],
  5. corporate career guides from relevant employers, especially those hiring for [DOCUMENT LANGUAGE]-language roles if applicable.
- Clearly distinguish between:
  - common recruiting practice in [TARGET COUNTRY],
  - preferences for international or English-speaking roles if relevant,
  - sector-specific differences,
  - contextual recommendations,
  - formal or legal requirements if they truly exist.
- Do not invent rules.
- If something depends on industry, seniority, company type, language of the application, or whether the employer is local vs international, state it explicitly.
- If the practice is changing, explain that clearly.
- Cite the sources supporting the most important claims.
- Avoid vague advice such as "show motivation" or "highlight your skills" unless you explain concretely how this is done in practice.
- Be explicit about what is common, what is optional, and what is outdated.

## Organize the response exactly like this:

### 1. What it is and what HR expects from the [DOCUMENT NAME] in [TARGET COUNTRY]
- What it is used for today
- When it truly adds value and when it is optional
- Whether recruiters in [TARGET COUNTRY] actually read it in practice
- What signals HR is looking for (fit, concrete motivation, evidence, professionalism, communication, etc.)
- What mistakes make it lose value
- What differs depending on:
  - local-language applications vs English-language applications
  - local employer vs multinational employer
  - junior vs senior roles

### 2. Recommended structure (section by section)
Give me a clear structure for a [DOCUMENT NAME] used in [TARGET COUNTRY], with:
- Header
- Subject line (if appropriate in that market)
- Greeting
- Opening paragraph / hook
- Body 1: concrete motivation for the company and role
- Body 2: evidence and achievements aligned with requirements
- Body 3: way of working, cultural fit, and soft skills with examples
- Closing
- Signature / attachments if applicable in that market

For each section include:
- Objective of the section
- What a recruiter in [TARGET COUNTRY] expects to read
- 2–3 model sentences in [DOCUMENT LANGUAGE] that sound natural, current, and professional
- Common mistakes to avoid
- Variations if it changes by sector, seniority, employer type, or level of formality
- Notes if [DOCUMENT LANGUAGE]-language applications in [TARGET COUNTRY] tend to be more direct, shorter, or less formal than local-language ones

### 3. Concrete style rules for the [DOCUMENT NAME] in [TARGET COUNTRY]
- Ideal length (lines, words, or pages)
- Tone and level of formality
- Whether the style should sound more local, more international, or hybrid
- How direct or traditional it should sound
- Use of pronouns and forms of address if relevant
- Verbs and formulations that work well
- How to avoid filler and sound specific
- Which expressions are overused or sound empty
- Whether salary expectations, notice period, work authorization, relocation, or visa sponsorship are commonly mentioned
- How the style changes depending on:
  - startup vs corporate
  - private vs public / semi-public sector
  - local company vs multinational
  - junior vs senior
  - local-language role vs English-language role in the same country

### 4. Adapting it to the job posting: step-by-step method
Explain a practical method to adapt the [DOCUMENT NAME] to a specific vacancy in [TARGET COUNTRY]:
- How to extract key requirements from the job ad
- How to distinguish must-haves from nice-to-haves
- How to turn requirements into evidence
- How to choose the top 2–3 achievements
- How to write them using STAR / CAR / PAR
- How to include keywords for ATS without keyword stuffing
- How to adapt the document when the posting is in English but the employer is based in a non-English-speaking country

Include a table with this format:

| Job ad requirement | Evidence I can use | Result/impact | How I turn it into a sentence |
|---|---|---|---|

### 5. Special cases
Give specific recommendations for:
- If I do not meet all the requirements
- Career change / transition into a new field
- Employment or academic gaps
- Limited experience
- International profile / foreign applicant
- Need for visa sponsorship or work authorization clarification
- Applications in English within [TARGET COUNTRY]
- Applying to a company whose internal working language is English but local HR is based in [TARGET COUNTRY]
- Speculative / unsolicited application, if applicable

### 6. Final quality checklist
- Verification list before sending
- Red flags that lead to fast rejection
- What to review in content, tone, format, personalization, and consistency with the CV / resume
- What makes the document sound imported from another market instead of fitting [TARGET COUNTRY]

### 7. Practical deliverables
Include:
- one complete [DOCUMENT NAME] template in [DOCUMENT LANGUAGE] with placeholders [like this]
- one "classic formal" version
- one "modern direct" version
- one ultra-short mini template for quick-apply fields or application portals, if that makes sense in [TARGET COUNTRY]

### 8. Executive conclusion
Close with:
- 5 non-negotiable principles for an excellent [DOCUMENT NAME] in [TARGET COUNTRY]
- 5 mistakes that are most heavily penalized
- one final recommendation on when it is worth investing time in this document and when it is not

## Conditions
- Do not invent data or practices.
- Base the guide on the recruiting reality of [TARGET COUNTRY], not generic foreign advice.
- Use real professional language, not translated-sounding wording.
- Be specific and actionable.
- If you mention “rules,” support them with real common practices or reliable sources.
- If there are differences by industry, company type, language environment, or local culture, clarify them.
- The response must be useful for someone who genuinely wants to apply, not just understand the theory.
- Write the guide in [OUTPUT LANGUAGE], but all document examples must be in [DOCUMENT LANGUAGE].

---

## After you receive the output

Send the guide back through `POST /profile-setup` in `utility-extract-profile.json`:

- use `guide_text_de` for the German-language guide
- use `guide_text_en` for the English-language guide
- include `profile_id` when updating an existing profile

Then run the profile setup workflow so the updated guide is written back to `candidate_context`.

Updating the guide does not regenerate `candidate_profile` or `role_type_scores` unless other source fields also require recomputation; it refreshes the guide text stored for runtime use by the Generator node. Changes take effect on the next job posting after the profile update runs.

See `config/candidate_context_template.md` for the `guide_text_de` and `guide_text_en` sections for details on what the Generator expects from these documents.

---

## When to regenerate

Run this prompt again when any of these conditions are true:
- You change target country or language (e.g. Germany → UK, German → English)
- Recruiting standards in your target market change significantly
- The Generator consistently produces Anschreiben that violate formatting rules — this may indicate the guide is outdated
- You find a substantially better or more current source for the country's standards
