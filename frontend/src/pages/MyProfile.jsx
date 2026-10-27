import { useEffect, useRef, useState } from 'react'
import { departmentsApi, profilesApi } from '../api/endpoints'
import { useAuth } from '../auth/AuthContext'
import { PublicationModal, ProjectModal } from '../components/profile/ItemModals'
import {
  KeywordSections,
  ProfileHeader,
  ProjectsSection,
  PublicationsSection,
} from '../components/profile/ProfileDisplay'
import { ProfileForm } from '../components/profile/ProfileForm'
import { Alert, Modal, Spinner } from '../components/ui'

export default function MyProfile() {
  const { user } = useAuth()
  const [profile, setProfile] = useState(undefined) // undefined = loading, null = not created yet
  const [departments, setDepartments] = useState([])
  const [designations, setDesignations] = useState([])
  const [loadError, setLoadError] = useState(null)
  const [editing, setEditing] = useState(false)
  const [notice, setNotice] = useState(null)

  const [pubModal, setPubModal] = useState(null) // null | {} (new) | publication
  const [projModal, setProjModal] = useState(null)
  const [confirmDelete, setConfirmDelete] = useState(null) // { kind, item }
  const [deleting, setDeleting] = useState(false)
  const flashTimer = useRef(null)

  useEffect(() => {
    Promise.all([
      profilesApi.getMine().catch((err) => (err.status === 404 ? null : Promise.reject(err))),
      departmentsApi.list(),
      profilesApi.designations(),
    ])
      .then(([p, depts, desigs]) => {
        setProfile(p)
        setDepartments(depts)
        setDesignations(desigs)
      })
      .catch((err) => setLoadError(err.message))
  }, [])

  const flash = (text) => {
    setNotice(text)
    window.clearTimeout(flashTimer.current)
    flashTimer.current = window.setTimeout(() => setNotice(null), 3500)
  }

  useEffect(() => () => window.clearTimeout(flashTimer.current), [])

  // Item changes come back as single rows; re-fetch so ordering and updated_at stay right
  const reload = async () => setProfile(await profilesApi.getMine())

  if (loadError) return <Alert>Couldn't load your profile: {loadError}</Alert>
  if (profile === undefined) return <Spinner />

  // ---------- Create (UC-004) ----------
  if (profile === null) {
    return (
      <div className="stack-lg">
        <section className="page-header">
          <div>
            <h1>Create your profile</h1>
            <p className="muted">
              Colleagues find you by your expertise and research interests. Name, department, designation and at
              least one expertise keyword are required for you to appear in search.
            </p>
          </div>
        </section>
        <div className="card rise">
          <ProfileForm
            initial={{ full_name: user.full_name }}
            departments={departments}
            designations={designations}
            submitLabel="Create profile"
            onSubmit={async (data) => {
              setProfile(await profilesApi.createMine(data))
              window.scrollTo({ top: 0, behavior: 'smooth' })
              flash('Profile created.')
            }}
          />
        </div>
      </div>
    )
  }

  // ---------- View / edit ----------
  async function doDelete() {
    setDeleting(true)
    try {
      const { kind, item } = confirmDelete
      if (kind === 'publication') await profilesApi.deletePublication(item.id)
      else await profilesApi.deleteProject(item.id)
      await reload()
      flash(`Deleted “${item.title}”.`)
      setConfirmDelete(null)
    } catch (err) {
      flash(err.message)
    } finally {
      setDeleting(false)
    }
  }

  return (
    <div className="stack-lg">
      {notice && <Alert kind="success">{notice}</Alert>}

      {!profile.is_discoverable && (
        <Alert kind="warning">
          You won't appear in search yet. Missing: {profile.missing_for_discovery.join(', ')}.
        </Alert>
      )}

      {editing ? (
        <section className="card rise">
          <h2 className="card-title">Edit profile</h2>
          <ProfileForm
            initial={profile}
            departments={departments}
            designations={designations}
            submitLabel="Save changes"
            onCancel={() => setEditing(false)}
            onSubmit={async (data) => {
              setProfile(await profilesApi.updateMine(data))
              setEditing(false)
              window.scrollTo({ top: 0, behavior: 'smooth' })
              flash('Profile saved.')
            }}
          />
        </section>
      ) : (
        <>
          <ProfileHeader profile={profile} onEdit={() => setEditing(true)} />
          <KeywordSections profile={profile} />
        </>
      )}

      <PublicationsSection
        publications={profile.publications}
        onAdd={() => setPubModal({})}
        onEdit={(p) => setPubModal(p)}
        onDelete={(p) => setConfirmDelete({ kind: 'publication', item: p })}
      />
      <ProjectsSection
        projects={profile.projects}
        onAdd={() => setProjModal({})}
        onEdit={(p) => setProjModal(p)}
        onDelete={(p) => setConfirmDelete({ kind: 'project', item: p })}
      />

      {pubModal && (
        <PublicationModal
          initial={pubModal}
          onClose={() => setPubModal(null)}
          onSave={async (data) => {
            if (pubModal.id) await profilesApi.updatePublication(pubModal.id, data)
            else await profilesApi.addPublication(data)
            await reload()
            setPubModal(null)
            flash(pubModal.id ? 'Publication updated.' : 'Publication added.')
          }}
        />
      )}
      {projModal && (
        <ProjectModal
          initial={projModal}
          onClose={() => setProjModal(null)}
          onSave={async (data) => {
            if (projModal.id) await profilesApi.updateProject(projModal.id, data)
            else await profilesApi.addProject(data)
            await reload()
            setProjModal(null)
            flash(projModal.id ? 'Project updated.' : 'Project added.')
          }}
        />
      )}

      <Modal
        open={confirmDelete !== null}
        title={`Delete this ${confirmDelete?.kind ?? ''}?`}
        onClose={() => setConfirmDelete(null)}
        footer={
          <>
            <button className="btn btn-ghost" onClick={() => setConfirmDelete(null)}>Cancel</button>
            <button className="btn btn-danger" disabled={deleting} onClick={doDelete}>
              {deleting ? 'Deleting…' : 'Delete'}
            </button>
          </>
        }
      >
        <p className="muted">“{confirmDelete?.item.title}” will be removed from your profile.</p>
      </Modal>
    </div>
  )
}
