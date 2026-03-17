import { StatusBar } from "expo-status-bar";
import { useCallback, useEffect, useState } from "react";
import {
  ActivityIndicator,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { getToken, setToken as persistToken } from "./storage";
import { setApiToken } from "./api";
import LoginScreen from "./screens/LoginScreen";
import HomeScreen from "./screens/HomeScreen";
import ReportScreen from "./screens/ReportScreen";
import MapScreen from "./screens/MapScreen";

export default function App() {
  const [screen, setScreen] = useState("loading");
  const [token, setTokenState] = useState(null);
  const [user, setUser] = useState(null);

  const setToken = useCallback((t, username = null) => {
    setApiToken(t);
    setTokenState(t);
    if (username) setUser(username);
    persistToken(t, username);
  }, []);

  const logout = useCallback(() => {
    setApiToken(null);
    setTokenState(null);
    setUser(null);
    persistToken(null);
    setScreen("login");
  }, []);

  useEffect(() => {
    let mounted = true;
    getToken().then((t) => {
      if (!mounted) return;
      if (t) {
        setApiToken(t);
        setTokenState(t);
        setScreen("home");
      } else {
        setScreen("login");
      }
    });
    return () => { mounted = false; };
  }, []);

  if (screen === "loading") {
    return (
      <View style={styles.centered}>
        <ActivityIndicator size="large" color="#667eea" />
        <Text style={styles.loadingText}>Loading…</Text>
        <StatusBar style="auto" />
      </View>
    );
  }

  if (screen === "login") {
    return (
      <LoginScreen
        onLogin={(t, username) => {
          setToken(t, username);
          setScreen("home");
        }}
        onRegister={() => setScreen("register")}
      />
    );
  }

  if (screen === "register") {
    return (
      <LoginScreen
        isRegister
        onLogin={(t, username) => {
          setToken(t, username);
          setScreen("home");
        }}
        onRegister={() => setScreen("login")}
      />
    );
  }

  if (screen === "report") {
    return (
      <ReportScreen
        onBack={() => setScreen("home")}
        onSuccess={() => setScreen("home")}
      />
    );
  }

  if (screen === "map") {
    return (
      <MapScreen
        user={user}
        onBack={() => setScreen("home")}
      />
    );
  }

  return (
    <HomeScreen
      user={user}
      onLogout={logout}
      onReportIssue={() => setScreen("report")}
      onOpenMap={() => setScreen("map")}
    />
  );
}

const styles = StyleSheet.create({
  centered: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
    backgroundColor: "#f8fafc",
  },
  loadingText: {
    marginTop: 12,
    fontSize: 16,
    color: "#64748b",
  },
});
