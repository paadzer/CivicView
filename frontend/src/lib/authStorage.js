export const AUTH_TOKEN_KEY = "civicview_token";
export const AUTH_USER_KEY = "civicview_user";

export const getStoredToken = () => localStorage.getItem(AUTH_TOKEN_KEY);
export const getStoredUser = () => localStorage.getItem(AUTH_USER_KEY);

export const setAuthToken = (token, username = null) => {
  if (token) {
    localStorage.setItem(AUTH_TOKEN_KEY, token);
    if (username) localStorage.setItem(AUTH_USER_KEY, username);
  } else {
    localStorage.removeItem(AUTH_TOKEN_KEY);
    localStorage.removeItem(AUTH_USER_KEY);
  }
};
