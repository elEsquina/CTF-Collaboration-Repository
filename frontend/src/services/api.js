let csrfToken = '';
export function setCsrf(token) { csrfToken = token || ''; }
export async function api(path, options = {}) {
  const headers = {...options.headers};
  if (options.body && !(options.body instanceof FormData)) headers['Content-Type'] = 'application/json';
  if (options.method && options.method !== 'GET') headers['X-CSRF-Token'] = csrfToken;
  let response;
  try {
    response = await fetch(`/api${path}`, {credentials: 'same-origin', ...options, headers});
  } catch {
    throw new Error('Unable to reach the server. Please try again.');
  }
  if (response.status === 401 && path !== '/login') window.dispatchEvent(new Event('session-expired'));
  let body;
  try {
    body = await response.json();
  } catch {
    throw new Error('The server returned an unexpected response. Please try again.');
  }
  if (!response.ok) {
    throw new Error(body.error?.message || 'Something went wrong. Please try again.');
  }
  return body;
}
export const categories = [['web','Web'],['pwn','Pwn'],['reverse-engineering','Reverse Engineering'],['cryptography','Cryptography'],['forensics','Forensics'],['osint','OSINT'],['miscellaneous','Miscellaneous']];
export const categoryName = value => categories.find(c => c[0] === value)?.[1] || value;
export const date = value => new Date(value).toLocaleDateString(undefined, {month:'short', day:'numeric', year:'numeric'});
