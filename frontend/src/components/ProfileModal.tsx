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
  email: z.string().email('Ungültige E-Mail').or(z.literal('')),
  phone: z.string().optional(),
  linkedin_url: z.string().url('Ungültige URL').or(z.literal('')),
  home_location: z.string().optional(),
  career_target: z.string().optional(),
  market_research: z.string().optional(),
  cv_text: z.string().min(50, 'Lebenslauf muss mindestens 50 Zeichen haben'),
})
type FormValues = z.infer<typeof schema>

interface Props {
  open: boolean
  onClose: () => void
  onSaved: (id: number) => void
  existing?: ProfileDetail
}

function Field({
  label,
  error,
  children,
}: {
  label: string
  error?: string
  children: React.ReactNode
}) {
  return (
    <div className="space-y-1.5">
      <label className="text-xs font-medium text-gray-400 uppercase tracking-wide">{label}</label>
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
      phone: existing?.phone ?? '',
      linkedin_url: existing?.linkedin_url ?? '',
      home_location: existing?.home_location ?? '',
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
        phone: existing?.phone ?? '',
        linkedin_url: existing?.linkedin_url ?? '',
        home_location: existing?.home_location ?? '',
        career_target: existing?.career_target ?? '',
        market_research: existing?.market_research ?? '',
        cv_text: existing?.cv_text ?? '',
      })
      setAvatarPreview(existing?.avatar_data_url ?? null)
      setSteps([])
    }
  }, [open, existing, reset])

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
            className="w-16 h-16 rounded-full bg-white/10 border border-white/20 overflow-hidden cursor-pointer flex items-center justify-center"
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

        {/* Name */}
        <div className="grid grid-cols-2 gap-3">
          <Field label="Vorname" error={errors.first_name?.message}>
            <input {...register('first_name')} className={inputClass} placeholder="Max" />
          </Field>
          <Field label="Nachname" error={errors.last_name?.message}>
            <input {...register('last_name')} className={inputClass} placeholder="Mustermann" />
          </Field>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <Field label="E-Mail" error={errors.email?.message}>
            <input {...register('email')} className={inputClass} placeholder="max@example.com" />
          </Field>
          <Field label="Telefon" error={errors.phone?.message}>
            <input {...register('phone')} className={inputClass} placeholder="+49 151 …" />
          </Field>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <Field label="Heimatort" error={errors.home_location?.message}>
            <input {...register('home_location')} className={inputClass} placeholder="Berlin, Deutschland" />
          </Field>
          <Field label="Karriereziel" error={errors.career_target?.message}>
            <input {...register('career_target')} className={inputClass} placeholder="Product Manager" />
          </Field>
        </div>

        <Field label="LinkedIn URL" error={errors.linkedin_url?.message}>
          <input {...register('linkedin_url')} className={inputClass} placeholder="https://linkedin.com/in/…" />
        </Field>

        <Field label="Marktrecherche" error={errors.market_research?.message}>
          <textarea
            {...register('market_research')}
            className={cn(inputClass, 'min-h-24 resize-y')}
            placeholder="Ergebnisse der Marktrecherche (optional)…"
          />
        </Field>

        <Field label="Lebenslauf (Volltext)" error={errors.cv_text?.message}>
          <textarea
            {...register('cv_text')}
            className={cn(inputClass, 'min-h-48 resize-y font-mono text-xs')}
            placeholder="Lebenslauf hier einfügen…"
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
