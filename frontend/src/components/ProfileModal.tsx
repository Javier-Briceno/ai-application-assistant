import { useEffect, useRef, useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Loader2, Upload } from 'lucide-react'
import { Dialog } from './ui/dialog'
import { Button } from './ui/button'
import { api } from '@/lib/api'
import { cn } from '@/lib/utils'
import type { ProfileDetail } from '@/types'

const schema = z.object({
  first_name: z.string().min(1, 'Pflichtfeld'),
  last_name: z.string().min(1, 'Pflichtfeld'),
  email: z.string().min(1, 'Pflichtfeld').email('Ungültige E-Mail'),
  phone_country_code: z.string().optional(),
  phone_number: z.string().min(1, 'Pflichtfeld'),
  street_address: z.string().min(1, 'Pflichtfeld'),
  postal_code: z.string().min(1, 'Pflichtfeld'),
  home_location: z.string().min(1, 'Pflichtfeld'),
  linkedin_url: z.string().url('Ungültige URL').or(z.literal('')),
  github_url: z.string().url('Ungültige URL').or(z.literal('')),
  website_url: z.string().url('Ungültige URL').or(z.literal('')),
  notes: z.string().optional(),
  career_target: z.string().min(1, 'Pflichtfeld'),
  market_research: z.string().min(1, 'Pflichtfeld'),
  cv_text: z.string().min(50, 'Lebenslauf muss mindestens 50 Zeichen haben'),
})
type FormValues = z.infer<typeof schema>

interface Props {
  open: boolean
  onClose: () => void
  onSaved: (id: number) => void
  existing?: ProfileDetail
}

function Field({ label, error, required, children }: { label: string; error?: string; required?: boolean; children: React.ReactNode }) {
  return (
    <div className="space-y-1.5">
      <label className="text-xs font-medium text-gray-400 uppercase tracking-wide">
        {label}{required && <span className="text-red-400 ml-0.5">*</span>}
      </label>
      {children}
      {error && <p className="text-xs text-red-400">{error}</p>}
    </div>
  )
}

const inputClass =
  'w-full rounded-lg bg-black/30 border border-white/10 px-3 py-2 text-sm text-gray-100 placeholder-gray-600 focus:outline-none focus:border-blue-500 transition-colors'

export function ProfileModal({ open, onClose, onSaved, existing }: Props) {
  const isEdit = !!existing
  const [saving, setSaving] = useState(false)
  const [avatarPreview, setAvatarPreview] = useState<string | null>(existing?.avatar_data_url ?? null)
  const avatarRef = useRef<HTMLInputElement>(null)
  const [steps, setSteps] = useState<string[]>([])

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      first_name: existing?.first_name ?? '',
      last_name: existing?.last_name ?? '',
      email: existing?.email ?? '',
      phone_country_code: existing?.phone_country_code ?? '+49',
      phone_number: existing?.phone_number ?? '',
      street_address: existing?.street_address ?? '',
      postal_code: existing?.postal_code ?? '',
      home_location: existing?.home_location ?? '',
      linkedin_url: existing?.linkedin_url ?? '',
      github_url: existing?.github_url ?? '',
      website_url: existing?.website_url ?? '',
      notes: existing?.notes ?? '',
      career_target: existing?.career_target ?? '',
      market_research: existing?.market_research ?? '',
      cv_text: existing?.cv_text ?? '',
    },
  })

  useEffect(() => {
    if (open) {
      reset({
        first_name: existing?.first_name ?? '',
        last_name: existing?.last_name ?? '',
        email: existing?.email ?? '',
        phone_country_code: existing?.phone_country_code ?? '+49',
        phone_number: existing?.phone_number ?? '',
        street_address: existing?.street_address ?? '',
        postal_code: existing?.postal_code ?? '',
        home_location: existing?.home_location ?? '',
        linkedin_url: existing?.linkedin_url ?? '',
        github_url: existing?.github_url ?? '',
        website_url: existing?.website_url ?? '',
        notes: existing?.notes ?? '',
        career_target: existing?.career_target ?? '',
        market_research: existing?.market_research ?? '',
        cv_text: existing?.cv_text ?? '',
      })
      setAvatarPreview(existing?.avatar_data_url ?? null)
      setSteps([])
    }
  }, [open, existing, reset])

  // Wraps register() with a character-strip filter applied on every change.
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const fil = <N extends keyof FormValues>(name: N, pattern: RegExp) => {
    const { onChange, ...rest } = register(name as any)
    return {
      ...rest,
      onChange: (e: React.ChangeEvent<HTMLInputElement>) => {
        e.target.value = e.target.value.replace(pattern, '')
        onChange(e)
      },
    }
  }

  const onAvatarChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    const reader = new FileReader()
    reader.onload = () => setAvatarPreview(reader.result as string)
    reader.readAsDataURL(file)
  }

  const onSubmit = async (values: FormValues) => {
    setSaving(true)
    setSteps(['Speichert Profil...'])
    try {
      const fd = new FormData()
      Object.entries(values).forEach(([k, v]) => fd.append(k, v ?? ''))
      const file = avatarRef.current?.files?.[0]
      if (file) fd.append('avatar', file)

      let id: number
      if (isEdit && existing) {
        const res = await api.profiles.update(existing.id, fd)
        id = res.id
      } else {
        const res = await api.profiles.create(fd)
        id = res.id
      }
      setSteps((s) => [...s, 'Profil gespeichert. KI-Extraktion läuft...'])
      onSaved(id)
      onClose()
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err)
      setSteps((s) => [...s, `Fehler: ${msg}`])
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title={isEdit ? 'Profil bearbeiten' : 'Neues Profil'}
      className="w-full max-w-2xl max-h-[90vh]"
    >
      <form onSubmit={handleSubmit(onSubmit)} className="space-y-5">

        {/* Avatar */}
        <div className="flex items-center gap-4">
          <div
            className="w-16 h-16 rounded-full bg-white/10 border border-white/20 overflow-hidden cursor-pointer flex items-center justify-center flex-shrink-0"
            onClick={() => avatarRef.current?.click()}
          >
            {avatarPreview ? (
              <img src={avatarPreview} alt="Avatar" className="w-full h-full object-cover" />
            ) : (
              <Upload size={20} className="text-gray-500" />
            )}
          </div>
          <input ref={avatarRef} type="file" accept="image/*" className="hidden" onChange={onAvatarChange} />
          <div className="text-xs text-gray-500">
            <p>Foto klicken zum Hochladen</p>
            <p>Max. 500 KB, JPEG/PNG</p>
          </div>
        </div>

        {/* Name — unicode letters, spaces, hyphens, apostrophes */}
        <div className="grid grid-cols-2 gap-3">
          <Field label="Vorname" required error={errors.first_name?.message}>
            <input {...fil('first_name', /[^\p{L}\s'-]/gu)} className={inputClass} placeholder="Max" />
          </Field>
          <Field label="Nachname" required error={errors.last_name?.message}>
            <input {...fil('last_name', /[^\p{L}\s'-]/gu)} className={inputClass} placeholder="Mustermann" />
          </Field>
        </div>

        {/* E-Mail — browser-native email validation via type */}
        <Field label="E-Mail" required error={errors.email?.message}>
          <input {...register('email')} type="email" inputMode="email" className={inputClass} placeholder="max@example.com" />
        </Field>

        {/* Phone: country code (+ and digits) + number (digits and spaces) */}
        <Field label="Telefon" required error={errors.phone_number?.message}>
          <div className="flex gap-2">
            <input
              {...fil('phone_country_code', /[^\d+]/g)}
              className={cn(inputClass, 'w-24 flex-shrink-0')}
              inputMode="tel"
              placeholder="+49"
            />
            <input
              {...fil('phone_number', /[^\d\s]/g)}
              className={inputClass}
              inputMode="numeric"
              placeholder="151 12345678"
            />
          </div>
        </Field>

        {/* Address — letters (with umlauts), digits, spaces, . , - */}
        <Field label="Straße und Hausnummer" required error={errors.street_address?.message}>
          <input {...fil('street_address', /[^\p{L}\d\s.,-]/gu)} className={inputClass} placeholder="Musterstraße 1" />
        </Field>

        <div className="grid grid-cols-3 gap-3">
          {/* PLZ — digits only, max 5 chars */}
          <Field label="PLZ" required error={errors.postal_code?.message}>
            <input {...fil('postal_code', /[^\d]/g)} className={inputClass} inputMode="numeric" maxLength={5} placeholder="12345" />
          </Field>
          <div className="col-span-2">
            {/* Stadt — unicode letters, spaces, hyphens, dots (e.g. St. Augustin) */}
            <Field label="Stadt" required error={errors.home_location?.message}>
              <input {...fil('home_location', /[^\p{L}\s.-]/gu)} className={inputClass} placeholder="Berlin" />
            </Field>
          </div>
        </div>

        {/* Links — type="url" gives browser-level hint; no char filter (URLs have many valid chars) */}
        <Field label="LinkedIn URL" error={errors.linkedin_url?.message}>
          <input {...register('linkedin_url')} type="url" className={inputClass} placeholder="https://linkedin.com/in/…" />
        </Field>

        <div className="grid grid-cols-2 gap-3">
          <Field label="GitHub URL" error={errors.github_url?.message}>
            <input {...register('github_url')} type="url" className={inputClass} placeholder="https://github.com/…" />
          </Field>
          <Field label="Webseite" error={errors.website_url?.message}>
            <input {...register('website_url')} type="url" className={inputClass} placeholder="https://…" />
          </Field>
        </div>

        {/* Career — free text (slashes, parentheses, dashes all valid: "Full-Stack (React/Node)") */}
        <Field label="Karriereziel" required error={errors.career_target?.message}>
          <input {...register('career_target')} className={inputClass} placeholder="Software Engineer, Product Manager…" />
        </Field>

        {/* Market research */}
        <Field label="Marktrecherche" required error={errors.market_research?.message}>
          <textarea
            {...register('market_research')}
            className={cn(inputClass, 'min-h-24 resize-y')}
            placeholder="Zielbranche, typische Anforderungen, Unternehmenskultur, Gehaltsrahmen… (beeinflusst KI-Analyse und Anschreiben)"
          />
        </Field>

        {/* CV text */}
        <Field label="Lebenslauf (Volltext)" required error={errors.cv_text?.message}>
          <textarea
            {...register('cv_text')}
            className={cn(inputClass, 'min-h-48 resize-y font-mono text-xs')}
            placeholder="Lebenslauf hier einfügen…"
          />
        </Field>

        {/* Notes */}
        <Field label="Notizen (intern)" error={errors.notes?.message}>
          <textarea
            {...register('notes')}
            className={cn(inputClass, 'min-h-16 resize-y')}
            placeholder="Interne Notizen zum Profil (werden nicht verwendet)…"
          />
        </Field>

        {steps.length > 0 && (
          <div className="text-xs text-gray-400 space-y-1 bg-black/30 rounded-lg p-3">
            {steps.map((s, i) => (
              <p key={i} className={i === steps.length - 1 ? 'text-blue-400' : 'opacity-50'}>
                {s}
              </p>
            ))}
          </div>
        )}

        <div className="flex justify-end gap-3 pt-2 border-t border-white/10">
          <Button type="button" variant="ghost" onClick={onClose} disabled={saving}>
            Abbrechen
          </Button>
          <Button type="submit" disabled={saving}>
            {saving ? (
              <>
                <Loader2 size={14} className="animate-spin" />
                Wird gespeichert…
              </>
            ) : isEdit ? (
              'Speichern'
            ) : (
              'Profil erstellen'
            )}
          </Button>
        </div>
      </form>
    </Dialog>
  )
}
