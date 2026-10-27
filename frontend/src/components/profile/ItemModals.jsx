import { useState } from 'react'
import { Alert, Field, Modal } from '../ui'

const THIS_YEAR = new Date().getFullYear()

// Shared add/edit dialog plumbing: field errors from the backend land on the right input
function useItemForm(initial, onSave) {
  const [form, setForm] = useState(initial)
  const [errors, setErrors] = useState({})
  const [error, setError] = useState(null)
  const [saving, setSaving] = useState(false)

  const set = (name) => (e) => {
    setForm((f) => ({ ...f, [name]: e.target.value }))
    setErrors((x) => ({ ...x, [name]: undefined }))
  }

  async function save(payload, clientErrors) {
    setErrors(clientErrors)
    if (Object.keys(clientErrors).length) return
    setSaving(true)
    setError(null)
    try {
      await onSave(payload)
    } catch (err) {
      setErrors(err.fieldErrors ?? {})
      // Model-level errors (e.g. date rules) have no field; show them on top
      if (!Object.keys(err.fieldErrors ?? {}).length || err.fieldErrors.body) setError(err.message)
      setSaving(false)
    }
  }

  return { form, set, errors, error, saving, save }
}

export function PublicationModal({ initial, onSave, onClose }) {
  const editing = Boolean(initial?.id)
  const { form, set, errors, error, saving, save } = useItemForm(
    { title: initial?.title ?? '', venue: initial?.venue ?? '', year: initial?.year ?? '', doi_url: initial?.doi_url ?? '' },
    onSave,
  )

  function submit(e) {
    e.preventDefault()
    const errs = {}
    if (!form.title.trim()) errs.title = 'Title is required'
    if (!form.venue.trim()) errs.venue = 'Venue or journal is required'
    const year = Number(form.year)
    if (!form.year) errs.year = 'Year is required'
    else if (!Number.isInteger(year) || year < 1900) errs.year = 'Enter a valid year'
    else if (year > THIS_YEAR) errs.year = `Year can't be in the future` // BR-007
    save({ title: form.title, venue: form.venue, year, doi_url: form.doi_url.trim() || null }, errs)
  }

  return (
    <Modal
      open
      title={editing ? 'Edit publication' : 'Add publication'}
      onClose={onClose}
      footer={
        <>
          <button className="btn btn-ghost" onClick={onClose}>Cancel</button>
          <button className="btn btn-primary" form="pub-form" disabled={saving}>{saving ? 'Saving…' : 'Save'}</button>
        </>
      }
    >
      <form id="pub-form" className="form" onSubmit={submit} noValidate>
        <Alert>{error}</Alert>
        <Field label="Title" error={errors.title}>
          <input value={form.title} maxLength={300} onChange={set('title')} autoFocus />
        </Field>
        <div className="form-grid form-grid-2">
          <Field label="Venue / journal" error={errors.venue}>
            <input value={form.venue} maxLength={200} onChange={set('venue')} placeholder="e.g. IEEE TPAMI" />
          </Field>
          <Field label="Year" error={errors.year}>
            <input type="number" min="1900" max={THIS_YEAR} value={form.year} onChange={set('year')} />
          </Field>
        </div>
        <Field label="DOI or link" error={errors.doi_url} hint="Optional · e.g. 10.1145/3290605 or https://…">
          <input value={form.doi_url} maxLength={500} onChange={set('doi_url')} />
        </Field>
      </form>
    </Modal>
  )
}

export function ProjectModal({ initial, onSave, onClose }) {
  const editing = Boolean(initial?.id)
  const { form, set, errors, error, saving, save } = useItemForm(
    {
      title: initial?.title ?? '',
      description: initial?.description ?? '',
      status: initial?.status ?? 'ongoing',
      start_date: initial?.start_date ?? '',
      end_date: initial?.end_date ?? '',
    },
    onSave,
  )

  function submit(e) {
    e.preventDefault()
    const errs = {}
    if (!form.title.trim()) errs.title = 'Title is required'
    if (!form.start_date) errs.start_date = 'Start date is required'
    // BR-008
    if (form.status === 'past' && !form.end_date) errs.end_date = 'A past project needs an end date'
    else if (form.status === 'past' && form.start_date && form.end_date <= form.start_date)
      errs.end_date = 'End date must be after the start date'
    else if (form.end_date && form.start_date && form.end_date < form.start_date)
      errs.end_date = "End date can't be before the start date"
    save(
      {
        title: form.title,
        description: form.description.trim() || null,
        status: form.status,
        start_date: form.start_date,
        end_date: form.end_date || null,
      },
      errs,
    )
  }

  return (
    <Modal
      open
      title={editing ? 'Edit project' : 'Add project'}
      onClose={onClose}
      footer={
        <>
          <button className="btn btn-ghost" onClick={onClose}>Cancel</button>
          <button className="btn btn-primary" form="proj-form" disabled={saving}>{saving ? 'Saving…' : 'Save'}</button>
        </>
      }
    >
      <form id="proj-form" className="form" onSubmit={submit} noValidate>
        <Alert>{error}</Alert>
        <Field label="Title" error={errors.title}>
          <input value={form.title} maxLength={200} onChange={set('title')} autoFocus />
        </Field>
        <div className="segmented" role="radiogroup" aria-label="Status">
          {['ongoing', 'past'].map((s) => (
            <label key={s} className={form.status === s ? 'active' : ''}>
              <input type="radio" name="status" value={s} checked={form.status === s} onChange={set('status')} />
              {s === 'ongoing' ? 'Ongoing' : 'Past'}
            </label>
          ))}
        </div>
        <div className="form-grid form-grid-2">
          <Field label="Start date" error={errors.start_date}>
            <input type="date" value={form.start_date} onChange={set('start_date')} />
          </Field>
          <Field label={form.status === 'past' ? 'End date' : 'End date (optional)'} error={errors.end_date}>
            <input type="date" value={form.end_date} onChange={set('end_date')} />
          </Field>
        </div>
        <Field label="Description" error={errors.description} hint="Optional">
          <textarea rows={3} maxLength={2000} value={form.description} onChange={set('description')} />
        </Field>
      </form>
    </Modal>
  )
}
