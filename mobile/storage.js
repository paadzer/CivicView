import AsyncStorage from "@react-native-async-storage/async-storage";

const TOKEN_KEY = "civicview_token";
const USER_KEY = "civicview_user";

export const getToken = async () => {
  try {
    return await AsyncStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
};

export const setToken = async (token, username = null) => {
  try {
    if (token) {
      await AsyncStorage.setItem(TOKEN_KEY, token);
      if (username) await AsyncStorage.setItem(USER_KEY, username);
    } else {
      await AsyncStorage.multiRemove([TOKEN_KEY, USER_KEY]);
    }
  } catch (e) {
    console.warn("Storage setToken failed", e);
  }
};

export const getStoredUser = async () => {
  try {
    return await AsyncStorage.getItem(USER_KEY);
  } catch {
    return null;
  }
};
