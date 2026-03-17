import { useCallback, useEffect, useState } from "react";
import {
  ActivityIndicator,
  FlatList,
  Image,
  Modal,
  Pressable,
  RefreshControl,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { StatusBar } from "expo-status-bar";
import { fetchReports, api } from "../api";

export default function HomeScreen({ user, onLogout, onReportIssue, onOpenMap }) {
  const [reports, setReports] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [selectedReport, setSelectedReport] = useState(null);

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
          <Pressable style={styles.mapButton} onPress={onOpenMap}>
            <Text style={styles.mapButtonText}>Map view</Text>
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
            <Pressable style={styles.card} onPress={() => setSelectedReport(item)}>
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
            </Pressable>
          )}
        />
      )}

      {/* Detail modal for a selected report */}
      <Modal
        visible={!!selectedReport}
        transparent
        animationType="slide"
        onRequestClose={() => setSelectedReport(null)}
      >
        <View style={styles.modalBackdrop}>
          <View style={styles.modalCard}>
            {selectedReport && (
              <>
                <Text style={styles.modalTitle}>{selectedReport.title}</Text>
                <Text style={styles.modalMeta}>
                  {selectedReport.category} •{" "}
                  {selectedReport.status_display || selectedReport.status || "Status unknown"}
                </Text>
                <Text style={styles.modalMeta}>
                  Reported by{" "}
                  {selectedReport.created_by_username || "Unknown"}{" "}
                  {selectedReport.created_at
                    ? `on ${new Date(selectedReport.created_at).toLocaleDateString()}`
                    : ""}
                </Text>
                <Text style={styles.modalDesc}>{selectedReport.description}</Text>
                {selectedReport.images && selectedReport.images.length > 0 && (
                  <View style={styles.modalImagesRow}>
                    {selectedReport.images.slice(0, 4).map((uri, idx) => (
                      <Image key={idx} source={{ uri }} style={styles.modalImage} />
                    ))}
                  </View>
                )}
                <Text style={styles.modalMeta}>
                  👍 {selectedReport.like_count || 0} likes
                </Text>
                <Pressable
                  style={styles.modalCloseBtn}
                  onPress={() => setSelectedReport(null)}
                >
                  <Text style={styles.modalCloseText}>Close</Text>
                </Pressable>
              </>
            )}
          </View>
        </View>
      </Modal>
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
  headerRow: { flexDirection: "row", marginTop: 16, gap: 12, alignItems: "center" },
  reportButton: {
    flex: 1,
    backgroundColor: "#667eea",
    padding: 14,
    borderRadius: 10,
    alignItems: "center",
  },
  mapButton: {
    paddingVertical: 12,
    paddingHorizontal: 14,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: "#e2e8f0",
    backgroundColor: "#f1f5f9",
  },
  mapButtonText: { color: "#0f172a", fontSize: 14, fontWeight: "500" },
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
  modalBackdrop: {
    flex: 1,
    backgroundColor: "rgba(15,23,42,0.55)",
    justifyContent: "center",
    alignItems: "center",
    padding: 20,
  },
  modalCard: {
    width: "100%",
    maxHeight: "80%",
    backgroundColor: "#fff",
    borderRadius: 16,
    padding: 20,
    borderWidth: 1,
    borderColor: "#e2e8f0",
  },
  modalTitle: { fontSize: 18, fontWeight: "700", color: "#0f172a", marginBottom: 4 },
  modalMeta: { fontSize: 12, color: "#64748b", marginBottom: 4 },
  modalDesc: { fontSize: 14, color: "#475569", marginVertical: 10 },
  modalImagesRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 8,
    marginBottom: 8,
  },
  modalImage: {
    width: 80,
    height: 80,
    borderRadius: 8,
    backgroundColor: "#e5e7eb",
  },
  modalCloseBtn: {
    alignSelf: "flex-end",
    marginTop: 12,
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 999,
    backgroundColor: "#111827",
  },
  modalCloseText: { color: "#f9fafb", fontSize: 13, fontWeight: "500" },
});
