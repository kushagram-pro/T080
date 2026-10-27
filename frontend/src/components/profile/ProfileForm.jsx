import { useState } from 'react'
import { Alert, Field } from '../ui'
import { TagInput } from '../TagInput'

// Used for both creating (UC-004) and editing (UC-005) a profile.
// Required: name, department, designation, at least one expertise keyword (BR-005 / AC-013).
export function ProfileForm({ initial, departments, designations, submitLabel, onSubmit, onCancel }) {
  const [form, setForm] = useState({
    full_name: initial.full_name ?? '',
    department_id: initial.department?.id ?? '',
    designation: initial.designation ?? '',
    bio: initial.bio ?? '',
    expertise_keywords: initial.expertise_keywords ?? [],
    research_interests: initial.research_interests ?? [],
  })
  const [errors, setErrors] = useState({})
  const [error, setError] = useState(null)
  const [saving, setSaving] = useState(false)

  const set = (name) => (v) => {
    setForm((f) => ({ ...f, [name]: v }))
    setErrors((e) => ({ ...e, [name]: undefined }))
  }

  function validate() {
    const e = {}
    if (!form.full_name.trim()) e.full_name = 'Full name is required'
    if (!form.department_id) e.department_id = 'Choose your department'
    if (!form.designation) e.designation = 'Choose your designation'
    if (!form.expertise_keywords.length) e.expertise_keywords = 'Add at least one expertise keyword'
    return e
  }

  async function submit(ev) {
    ev.preventDefault()
    const e = validate()
    setErrors(e)
    if (Object.keys(e).length) return // AC-018: highlight missing fields, don't submit
    setSaving(true)
    setError(null)
    try {
      await onSubmit({ ...form, department_id: Number(form.department_id), bio: form.bio.trim() || null })
    } catch (err) {
      setErrors(err.fieldErrors ?? {})
      if (!Object.keys(err.fieldErrors ?? {}).length) setError(err.message)
      setSaving(false)
    }
  }

  return (
    <form className="form profile-form" onSubmit={submit} noValidate>
      <Alert>{error}</Alert>

      <div className="form-grid">
        <Field label="Full name" error={errors.full_name}>
          <input value={form.full_name} maxLength={150} onChange={(e) => set('full_name')(e.target.value)} />
        </Field>
        <Field label="Designation" error={errors.designation}>
          <select value={form.designation} onChange={(e) => set('designation')(e.target.value)}>
            <option value="">Select…</option>
            {designations.map((d) => <option key={d} value={d}>{d}</option>)}
          </select>
        </Field>
        <Field
          label="Department"
          error={errors.department_id}
          hint={departments.length === 0 ? 'No departments yet. Ask an administrator to add yours.' : undefined}
        >
          <select value={form.department_id} onChange={(e) => set('department_id')(e.target.value)}>
            <option value="">Select…</option>
            {departments.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
          </select>
        </Field>
      </div>

      <Field
        label="Expertise"
        error={errors.expertise_keywords}
        hint="Press Enter after each keyword, e.g. Machine Learning, VLSI Design"
      >
        <TagInput
          value={form.expertise_keywords}
          onChange={set('expertise_keywords')}
          placeholder="Add expertise…"
          invalid={!!errors.expertise_keywords}
        />
      </Field>

      <Field label="Research interests" error={errors.research_interests} hint="Topics you'd like to collaborate on">
        <TagInput value={form.research_interests} onChange={set('research_interests')} placeholder="Add interest…" />
      </Field>

      <Field label="About" error={errors.bio} hint={`${form.bio.length}/2000 · optional`}>
        <textarea rows={4} maxLength={2000} value={form.bio} onChange={(e) => set('bio')(e.target.value)}
          placeholder="A short summary of your research." />
      </Field>

      <div className="form-actions">
        {onCancel && <button type="button" className="btn btn-ghost" onClick={onCancel}>Cancel</button>}
        <button className="btn btn-primary" disabled={saving}>{saving ? 'Saving…' : submitLabel}</button>
      </div>
    </form>
  )
}
