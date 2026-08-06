/**
 * Clear seeded Explore-as-guest demo data; keep JWT / guest account.
 * Also clears local canvas caches so UI doesn't keep stale widgets.
 */
export async function removeGuestSampleData(authToken) {
  const resp = await fetch(`${process.env.REACT_APP_API_URL || ''}/auth/guest/clear-sample`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${authToken}`,
      'Content-Type': 'application/json',
    },
  });
  if (!resp.ok) {
    const data = await resp.json().catch(() => ({}));
    throw new Error(data.detail || 'Could not remove sample data');
  }
  try {
    localStorage.removeItem('canvas-layout-v2');
    localStorage.removeItem('canvas-states-v2');
    localStorage.removeItem('canvas-deliverables-v2');
    localStorage.removeItem('canvas-task-status-v1');
  } catch { /* ignore */ }
  return resp.json();
}
