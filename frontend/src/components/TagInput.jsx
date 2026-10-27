import { useId, useState } from 'react'

// Chips input: Enter or comma adds, Backspace on empty input removes the last chip.
// Duplicates are ignored case-insensitively, matching the backend.
export function TagInput({ value, onChange, placeholder, max = 20, maxLength = 100, invalid }) {
  const [draft, setDraft] = useState('')
  const inputId = useId()

  function add(raw) {
    const tag = raw.replace(/\s+/g, ' ').trim()
    if (!tag) return
    if (value.some((t) => t.toLowerCase() === tag.toLowerCase())) {
      setDraft('')
      return
    }
    if (value.length >= max) return
    onChange([...value, tag.slice(0, maxLength)])
    setDraft('')
  }

  function onKeyDown(e) {
    if (e.key === 'Enter' || e.key === ',') {
      e.preventDefault()
      add(draft)
    } else if (e.key === 'Backspace' && !draft && value.length) {
      onChange(value.slice(0, -1))
    }
  }

  return (
    <div className={`tag-input ${invalid ? 'is-invalid' : ''}`} onClick={() => document.getElementById(inputId)?.focus()}>
      {value.map((tag) => (
        <span key={tag} className="chip chip-removable">
          {tag}
          <button
            type="button"
            aria-label={`Remove ${tag}`}
            onClick={(e) => {
              e.stopPropagation()
              onChange(value.filter((t) => t !== tag))
            }}
          >
            ×
          </button>
        </span>
      ))}
      <input
        id={inputId}
        value={draft}
        maxLength={maxLength}
        onChange={(e) => setDraft(e.target.value)}
        onKeyDown={onKeyDown}
        onBlur={() => add(draft)}
        placeholder={value.length >= max ? `Maximum ${max}` : placeholder}
        disabled={value.length >= max}
      />
    </div>
  )
}
