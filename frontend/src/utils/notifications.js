// Where clicking a notification should go: the Collaborations page opens the tab
// containing that request and highlights it
export function notificationTarget(n) {
  return n.request_id ? `/collaborations?request=${n.request_id}` : '/collaborations'
}
