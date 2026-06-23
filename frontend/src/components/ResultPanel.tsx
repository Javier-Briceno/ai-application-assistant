import { Download, FileText } from 'lucide-react'
import { ScorePanel } from './ScorePanel'
import { CvDiff } from './CvDiff'
import { Tabs, TabsList, Tab, TabPanel } from './ui/tabs'
import { api } from '@/lib/api'
import type { PipelineResult } from '@/types'

export function ResultPanel({ result }: { result: PipelineResult }) {
  const { scoring, company, tailoring, anschreiben_text, gap_analysis, job_application_id } = result
  const hasTailoring = tailoring !== null
  const appId = job_application_id

  return (
    <div className="space-y-4 p-5">
      <ScorePanel scoring={scoring} company={company.company_name} />

      {gap_analysis && (
        <div className="rounded-xl border border-yellow-500/20 bg-yellow-500/5 p-4">
          <p className="text-xs text-yellow-400 font-medium uppercase tracking-wider mb-2">Lückenanalyse</p>
          <p className="text-sm text-gray-300 leading-relaxed">{gap_analysis}</p>
        </div>
      )}

      {hasTailoring && (
        <Tabs defaultValue="diff">
          <TabsList>
            <Tab value="diff">
              Lebenslauf-Diff{' '}
              <span className="ml-1 text-xs opacity-60">
                ({tailoring.items_removed}↓ {tailoring.items_shortened}✂)
              </span>
            </Tab>
            {anschreiben_text && <Tab value="letter">Anschreiben</Tab>}
            {appId && <Tab value="download">Herunterladen</Tab>}
          </TabsList>

          <TabPanel value="diff">
            <CvDiff diff={tailoring.cv_diff} />
          </TabPanel>

          {anschreiben_text && (
            <TabPanel value="letter">
              <div className="rounded-xl border border-white/10 bg-black/20 p-5">
                <p className="text-sm text-gray-200 leading-7 whitespace-pre-wrap font-sans">
                  {anschreiben_text}
                </p>
              </div>
            </TabPanel>
          )}

          {appId && (
            <TabPanel value="download">
              <div className="flex flex-col gap-3 pt-2">
                <a
                  href={api.applications.cvDocxUrl(appId)}
                  download
                  className="inline-flex items-center justify-start gap-3 h-12 rounded-md border border-white/20 px-4 text-sm font-medium text-gray-300 hover:bg-white/10 transition-colors no-underline"
                >
                  <FileText size={16} className="text-blue-400" />
                  <span>Lebenslauf herunterladen (.docx)</span>
                  <Download size={14} className="ml-auto opacity-50" />
                </a>
                {anschreiben_text && (
                  <a
                    href={api.applications.anschreibenDocxUrl(appId)}
                    download
                    className="inline-flex items-center justify-start gap-3 h-12 rounded-md border border-white/20 px-4 text-sm font-medium text-gray-300 hover:bg-white/10 transition-colors no-underline"
                  >
                    <FileText size={16} className="text-green-400" />
                    <span>Anschreiben herunterladen (.docx)</span>
                    <Download size={14} className="ml-auto opacity-50" />
                  </a>
                )}
              </div>
            </TabPanel>
          )}
        </Tabs>
      )}
    </div>
  )
}
