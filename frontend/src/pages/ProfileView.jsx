import { useEffect, useState } from 'react'
import { Link, Navigate, useParams } from 'react-router-dom'
import { profilesApi } from '../api/endpoints'
import { useAuth } from '../auth/AuthContext'
import {
  KeywordSections,
  ProfileHeader,
  ProjectsSection,
  PublicationsSection,
} from '../components/profile/ProfileDisplay'
import { RequestActions } from '../components/collab/RequestActions'
import { Spinner } from '../components/ui'

// FR-017: any logged-in user can view an active faculty member's full profile
export default function ProfileView() {
  const { userId } = useParams()
  const { user } = useAuth()
  const [state, setState] = useState({ profile: null, error: null, loading: true })

  useEffect(() => {
    let cancelled = false
    profilesApi
      .get(userId)
      .then((profile) => !cancelled && setState({ profile, error: null, loading: false }))
      .catch((err) => !cancelled && setState({ profile: null, error: err, loading: false }))
    return () => {
      cancelled = true
    }
  }, [userId])

  // Your own profile has an editable page
  if (String(user.id) === userId && user.role === 'faculty') return <Navigate to="/profile" replace />

  if (state.loading) return <Spinner />
  if (state.error) {
    return (
      <div className="card empty-state">
        <h2>{state.error.status === 404 ? 'Profile not found' : 'Something went wrong'}</h2>
        <p className="muted">
          {state.error.status === 404
            ? "This faculty member doesn't have a profile, or their account is no longer active."
            : state.error.message}
        </p>
        <Link to="/" className="btn btn-primary">Back to dashboard</Link>
      </div>
    )
  }

  const { profile } = state
  return (
    <div className="stack-lg">
      <ProfileHeader profile={profile} />
      {user.role === 'faculty' && <RequestActions userId={profile.user_id} name={profile.full_name} />}
      <KeywordSections profile={profile} />
      <PublicationsSection publications={profile.publications} />
      <ProjectsSection projects={profile.projects} />
    </div>
  )
}
