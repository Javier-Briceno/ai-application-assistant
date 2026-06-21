export interface ProfileSummary {
  id: number
  display_name: string
  first_name: string | null
  last_name: string | null
  avatar_data_url: string | null
  home_location: string | null
}

export interface ProfileDetail extends ProfileSummary {
  email: string | null
  phone: string | null
  cv_text: string | null
  linkedin_url: string | null
  market_research: string | null
  career_target: string | null
  home_location: string | null
}

export interface DimensionScore {
  score: number
  reasoning: string
}

export interface ScoringResult {
  total_score: number
  threshold: 'pass' | 'caution' | 'fail'
  technical: DimensionScore
  requirements: DimensionScore
  role_fit: DimensionScore
  location: DimensionScore
  strategic: DimensionScore
}

export interface CompanyResult {
  company_name: string
  search_name: string
  research_text: string
}

export interface TailoringResult {
  items_removed: number
  items_shortened: number
  cv_diff: string
  tailored_cv: string
}

export interface PipelineResult {
  profile_id: number
  company: CompanyResult
  scoring: ScoringResult
  tailoring: TailoringResult | null
  anschreiben_text: string | null
  gap_analysis: string | null
  job_application_id: number | null
}

export interface ScoringDetails {
  technical: DimensionScore
  requirements: DimensionScore
  role_fit: DimensionScore
  location: DimensionScore
  strategic: DimensionScore
}

export interface Application {
  id: number
  profile_id: number
  company: string
  role_title: string
  score: number
  threshold: 'pass' | 'caution' | 'fail'
  date_applied: string
  cv_diff: string | null
  anschreiben: string | null
  gaps: string | null
  scoring_details: ScoringDetails | null
}

export type StepEvent = { type: 'step'; message: string }
export type ResultEvent = { type: 'result'; data: PipelineResult }
export type ErrorEvent = { type: 'error'; message: string }
export type AnalyzeEvent = StepEvent | ResultEvent | ErrorEvent
