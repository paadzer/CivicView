import { useCallback, useEffect, useState } from "react";
import {
  ActivityIndicator,
  FlatList,
  Pressable,
  RefreshControl,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { StatusBar } from "expo-status-bar";
import { fetchReports, api } from "../api";

export default function HomeScreen({ user, onLogout, onReportIssue }) {
  const [reports, setReports] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async () => {
    try {
      const data = await fetchReports();
      setReports(Array.isArray(data) ? data : []);
    } catch {
      setReports([]);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const onRefresh = () => {
    setRefreshing(true);
    load();
  };

  return (
    <View style={styles.container}>
      <StatusBar style="auto" />
      <View style={styles.header}>
        <Text style={styles.title}>CivicView</Text>
        <Text style={styles.user}>{user ? `Hi, ${user}` : "Reports"}</Text>
        <View style={styles.headerRow}>
          <Pressable style={styles.reportButton} onPress={onReportIssue}>
            <Text style={styles.reportButtonText}>Report an issue</Text>
          </Pressable>
          <Pressable style={styles.logoutButton} onPress={onLogout}>
            <Text style={styles.logoutButtonText}>Log out</Text>
          </Pressable>
        </View>
      </View>

      <Text style={styles.sectionTitle}>Recent reports</Text>
      {loading ? (
        <View style={styles.centered}>
          <ActivityIndicator size="large" color="#667eea" />
        </View>
      ) : (
        <FlatList
          data={reports.slice(0, 50)}
          keyExtractor={(r) => String(r.id)}
          refreshControl={
            <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
          }
          ListEmptyComponent={
            <View style={styles.empty}>
              <Text style={styles.emptyText}>No reports yet. Tap "Report an issue" to add one.</Text>
            </View>
          }
          renderItem={({ item }) => (
            <View style={styles.card}>
              <Text style={styles.cardTitle} numberOfLines={1}>{item.title}</Text>
              <Text style={styles.cardCategory}>{item.category}</Text>
              <Text style={styles.cardDesc} numberOfLines={2}>{item.description}</Text>
              {item.images && item.images.length > 0 && (
                <Text style={styles.cardPhotos}>📷 {item.images.length} photo(s)</Text>
              )}
              <Pressable
                style={styles.likeButton}
                onPress={async () => {
                  try {
                    const res = await api.post(`reports/${item.id}/like/`, {});
                    setReports((prev) =>
                      prev.map((r) =>
                        r.id === item.id
                          ? { ...r, like_count: res.like_count, liked_by_me: true }
                          : r
                      )
                    );
                  } catch (e) {
                    // ignore like errors on mobile UI
                  }
                }}
              >
                <Text style={styles.likeText}>
                  {item.liked_by_me ? "👍 Liked" : "👍 Like"} ({item.like_count || 0})
                </Text>
              </Pressable>
            </View>
          )}
        />
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#f8fafc" },
  header: {
    padding: 20,
    paddingTop: 56,
    backgroundColor: "#fff",
    borderBottomWidth: 1,
    borderBottomColor: "#e2e8f0",
  },
  title: { fontSize: 22, fontWeight: "700", color: "#0f172a" },
  user: { fontSize: 14, color: "#64748b", marginTop: 4 },
  headerRow: { flexDirection: "row", marginTop: 16, gap: 12 },
  reportButton: {
    flex: 1,
    backgroundColor: "#667eea",
    padding: 14,
    borderRadius: 10,
    alignItems: "center",
  },
  reportButtonText: { color: "#fff", fontWeight: "600", fontSize: 15 },
  logoutButton: {
    paddingVertical: 14,
    paddingHorizontal: 16,
    justifyContent: "center",
  },
  logoutButtonText: { color: "#64748b", fontSize: 15 },
  sectionTitle: {
    fontSize: 18,
    fontWeight: "600",
    color: "#0f172a",
    paddingHorizontal: 20,
    paddingTop: 16,
    paddingBottom: 8,
  },
  centered: { flex: 1, justifyContent: "center", alignItems: "center" },
  empty: { padding: 32, alignItems: "center" },
  emptyText: { color: "#64748b", fontSize: 15 },
  card: {
    backgroundColor: "#fff",
    marginHorizontal: 20,
    marginBottom: 12,
    padding: 16,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: "#e2e8f0",
  },
  cardTitle: { fontSize: 16, fontWeight: "600", color: "#0f172a" },
  cardCategory: { fontSize: 12, color: "#667eea", marginTop: 4 },
  cardDesc: { fontSize: 14, color: "#475569", marginTop: 6 },
  cardPhotos: { fontSize: 12, color: "#64748b", marginTop: 6 },
  likeButton: {
    marginTop: 8,
    alignSelf: "flex-start",
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: 16,
    backgroundColor: "#e0e7ff",
  },
  likeText: { fontSize: 12, color: "#3730a3", fontWeight: "500" },
});
