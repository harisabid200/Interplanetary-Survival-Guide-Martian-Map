// A frontend SPA fallback is HTML, even when it returns HTTP 200. Never parse
// that fallback as a successful routing response or enable mission planning.
export async function apiJson(response) {
  const contentType = response.headers.get('content-type') || '';
  if (!contentType.toLowerCase().includes('application/json')) {
    throw new Error('Routing connection returned a page instead of API data. Restart the frontend development server and keep the Python routing server running, then reconnect.');
  }
  try {
    return await response.json();
  } catch {
    throw new Error('Routing service returned unreadable data. Reconnect to the local routing server.');
  }
}
