import { useEffect, useState } from 'react'
import { departmentsApi } from '../api/endpoints'
import { useAuth } from '../auth/AuthContext'
import { Alert, Field, Modal, Spinner } from '../components/ui'

const EMPTY = { name: '', institute: 'LNMIIT' }

function sortDepartments(list) {
  return [...list].sort((a, b) => a.institute.localeCompare(b.institute) || a.name.localeCompare(b.name))
}

export default function Departments() {
  const { user } = useAuth()
  const isAdmin = user.role === 'admin'

  const [departments, setDepartments] = useState(null)
  const [loadError, setLoadError] = useState(null)
  const [notice, setNotice] = useState(null)

  // Add / edit share one modal. editing = null (closed) | 'new' | department object
  const [editing, setEditing] = useState(null)
  const [form, setForm] = useState(EMPTY)
  const [formErrors, setFormErrors] = useState({})
  const [formError, setFormError] = useState(null)
  const [saving, setSaving] = useState(false)

  const [deleting, setDeleting] = useState(null)
  const [deleteError, setDeleteError] = useState(null)

  useEffect(() => {
    departmentsApi
      .list()
      .then((list) => setDepartments(sortDepartments(list)))
      .catch((err) => setLoadError(err.message))
  }, [])

  function openAdd() {
    setEditing('new')
    setForm(EMPTY)
    setFormErrors({})
    setFormError(null)
  }

  function openEdit(dept) {
    setEditing(dept)
    setForm({ name: dept.name, institute: dept.institute })
    setFormErrors({})
    setFormError(null)
  }

  async function save(e) {
    e.preventDefault()
    const errors = {}
    if (!form.name.trim()) errors.name = 'Name is required'
    if (!form.institute.trim()) errors.institute = 'Institute is required'
    setFormErrors(errors)
    if (Object.keys(errors).length) return

    setSaving(true)
    setFormError(null)
    try {
      if (editing === 'new') {
        const created = await departmentsApi.create(form)
        setDepartments((list) => sortDepartments([...list, created]))
        setNotice(`Added ${created.name}.`)
      } else {
        const updated = await departmentsApi.update(editing.id, form)
        setDepartments((list) => sortDepartments(list.map((d) => (d.id === updated.id ? updated : d))))
        setNotice(`Saved ${updated.name}.`)
      }
      setEditing(null)
    } catch (err) {
      setFormErrors(err.fieldErrors ?? {})
      if (!Object.keys(err.fieldErrors ?? {}).length) setFormError(err.message)
    } finally {
      setSaving(false)
    }
  }

  async function confirmDelete() {
    setSaving(true)
    setDeleteError(null)
    try {
      await departmentsApi.remove(deleting.id)
      setDepartments((list) => list.filter((d) => d.id !== deleting.id))
      setNotice(`Deleted ${deleting.name}.`)
      setDeleting(null)
    } catch (err) {
      setDeleteError(err.message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="stack-lg">
      <section className="page-header">
        <div>
          <h1>Departments</h1>
          <p className="muted">
            {isAdmin
              ? 'Faculty choose one of these departments on their profile.'
              : 'Departments faculty can belong to.'}
          </p>
        </div>
        {isAdmin && (
          <button className="btn btn-primary" onClick={openAdd}>+ Add department</button>
        )}
      </section>

      {notice && <Alert kind="success">{notice}</Alert>}
      <Alert>{loadError}</Alert>
      {departments === null && !loadError && <Spinner />}

      {departments?.length === 0 && (
        <div className="card empty-state">
          <h2>No departments yet</h2>
          <p className="muted">
            {isAdmin ? 'Add the first department so faculty can complete their profiles.' : 'An administrator hasn’t added any departments yet.'}
          </p>
          {isAdmin && <button className="btn btn-primary" onClick={openAdd}>Add department</button>}
        </div>
      )}

      {departments?.length > 0 && (
        <div className="card table-card">
          <table className="table">
            <thead>
              <tr>
                <th>Department</th>
                <th>Institute</th>
                <th className="num">Faculty</th>
                {isAdmin && <th className="col-actions"><span className="sr-only">Actions</span></th>}
              </tr>
            </thead>
            <tbody>
              {departments.map((d, i) => (
                <tr key={d.id} className="rise" style={{ '--i': i }}>
                  <td data-label="Department" className="strong">{d.name}</td>
                  <td data-label="Institute">{d.institute}</td>
                  <td data-label="Faculty" className="num">{d.faculty_count}</td>
                  {isAdmin && (
                    <td className="col-actions">
                      <div className="row-actions">
                        <button className="btn btn-ghost btn-sm" onClick={() => openEdit(d)}>Edit</button>
                        <button
                          className="btn btn-danger-ghost btn-sm"
                          onClick={() => {
                            setDeleting(d)
                            setDeleteError(null)
                          }}
                        >
                          Delete
                        </button>
                      </div>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <Modal
        open={editing !== null}
        title={editing === 'new' ? 'Add department' : 'Edit department'}
        onClose={() => setEditing(null)}
        footer={
          <>
            <button className="btn btn-ghost" onClick={() => setEditing(null)}>Cancel</button>
            <button className="btn btn-primary" type="submit" form="dept-form" disabled={saving}>
              {saving ? 'Saving…' : 'Save'}
            </button>
          </>
        }
      >
        <form id="dept-form" className="form" onSubmit={save} noValidate>
          <Alert>{formError}</Alert>
          <Field label="Department name" error={formErrors.name}>
            <input
              value={form.name}
              maxLength={255}
              onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
              placeholder="e.g. Computer Science and Engineering"
              autoFocus
            />
          </Field>
          <Field label="Institute" error={formErrors.institute}>
            <input
              value={form.institute}
              maxLength={255}
              onChange={(e) => setForm((f) => ({ ...f, institute: e.target.value }))}
            />
          </Field>
        </form>
      </Modal>

      <Modal
        open={deleting !== null}
        title={`Delete ${deleting?.name ?? ''}?`}
        onClose={() => setDeleting(null)}
        footer={
          <>
            <button className="btn btn-ghost" onClick={() => setDeleting(null)}>Cancel</button>
            <button className="btn btn-danger" disabled={saving || deleteError !== null} onClick={confirmDelete}>
              {saving ? 'Deleting…' : 'Delete'}
            </button>
          </>
        }
      >
        {deleteError ? (
          <Alert>{deleteError}</Alert>
        ) : (
          <p className="muted">This can't be undone. Departments with faculty assigned can't be deleted.</p>
        )}
      </Modal>
    </div>
  )
}
