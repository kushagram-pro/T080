// Where clicking a notification should go. Request notifications open the tab holding that
// request and highlight it; message and "collaboration ended" notifications open the
// collaborators tab (with the conversation, for messages).
export function notificationTarget(n) {
  if (!n.request_id) return '/collaborations'
  if (n.type === 'message_received') return `/collaborations?tab=collaborators&chat=${n.request_id}`
  if (n.type === 'collaboration_ended') return '/collaborations?tab=collaborators'
  return `/collaborations?request=${n.request_id}`
}
