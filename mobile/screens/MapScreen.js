import { useCallback, useEffect, useState } from "react";
import { ActivityIndicator, Modal, Pressable, StyleSheet, Text, View, Image } from "react-native";
import { StatusBar } from "expo-status-bar";
import * as Location from "expo-location";
import MapView, { Marker } from "react-native-maps";
import { fetchReports, api } from "../api";

export default function MapScreen({ user, onBack }) {
  const [region, setRegion] = useState(null);
  const [reports, setReports] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedReport, setSelectedReport] = useState(null);

  const loadReports = useCallback(async () => {
    try {
      const data = await fetchReports();
      setReports(Array.isArray(data) ? data : []);
    } catch {
      setReports([]);
    } finally {
      setLoading(false);
    }
  }, []);

  const initLocation = useCallback(async () => {
    const { status } = await Location.requestForegroundPermissionsAsync();
    if (status !== "granted") {
      // Default to a center on Ireland if permission denied
      setRegion({
        latitude: 53.35,
        longitude: -6.26,
        latitudeDelta: 2,
        longitudeDelta: 2,
      });
      return;
    }
    try {
      const loc = await Location.getCurrentPositionAsync({
        accuracy: Location.Accuracy.Balanced,
      });
      setRegion({
        latitude: loc.coords.latitude,
        longitude: loc.coords.longitude,
        latitudeDelta: 0.2,
        longitudeDelta: 0.2,
      });
    } catch {
      setRegion({
        latitude: 53.35,
        longitude: -6.26,
        latitudeDelta: 2,
        longitudeDelta: 2,
      });
    }
  }, []);

  useEffect(() => {
    initLocation();
    loadReports();
  }, [initLocation, loadReports]);

  const handleLike = async (report) => {
    try {
      const res = await api.post(`reports/${report.id}/like/`, {});
      setReports((prev) =>
        prev.map((r) =>
          r.id === report.id ? { ...r, like_count: res.like_count, liked_by_me: true } : r
        )
      );
      setSelectedReport((prev) =>
        prev && prev.id === report.id
          ? { ...prev, like_count: res.like_count, liked_by_me: true }
          : prev
      );
    } catch {
      // ignore like errors here
    }
  };

  return (
    <View style={styles.container}>
      <StatusBar style="auto" />
      <View style={styles.header}>
        <Pressable onPress={onBack} style={styles.backBtn}>
          <Text style={styles.backText}>← Back</Text>
        </Pressable>
        <View style={{ flex: 1 }}>
          <Text style={styles.title}>Reports map</Text>
          <Text style={styles.subtitle}>
            {user ? `Signed in as ${user}` : "Viewing public reports"}
          </Text>
        </View>
      </View>

      {region ? (
        <MapView style={styles.map} initialRegion={region}>
          {reports
            .filter((r) => r.geom && Array.isArray(r.geom.coordinates))
            .map((r) => {
              const [lon, lat] = r.geom.coordinates;
              if (typeof lat !== "number" || typeof lon !== "number") return null;
              return (
                <Marker
                  key={r.id}
                  coordinate={{ latitude: lat, longitude: lon }}
                  title={r.title}
                  description={r.category}
                  onPress={() => setSelectedReport(r)}
                />
              );
            })}
        </MapView>
      ) : (
        <View style={styles.centered}>
          <ActivityIndicator size="large" color="#667eea" />
          <Text style={styles.loadingText}>Loading map…</Text>
        </View>
      )}

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
                <Pressable
                  style={styles.likeBtn}
                  onPress={() => handleLike(selectedReport)}
                >
                  <Text style={styles.likeBtnText}>
                    {selectedReport.liked_by_me ? "👍 Liked" : "👍 Like"} (
                    {selectedReport.like_count || 0})
                  </Text>
                </Pressable>
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
    flexDirection: "row",
    alignItems: "center",
    paddingTop: 56,
    paddingHorizontal: 16,
    paddingBottom: 12,
    backgroundColor: "#fff",
    borderBottomWidth: 1,
    borderBottomColor: "#e2e8f0",
  },
  backBtn: { padding: 8, marginRight: 8 },
  backText: { fontSize: 16, color: "#667eea", fontWeight: "500" },
  title: { fontSize: 18, fontWeight: "600", color: "#0f172a" },
  subtitle: { fontSize: 12, color: "#64748b", marginTop: 2 },
  map: { flex: 1 },
  centered: { flex: 1, justifyContent: "center", alignItems: "center" },
  loadingText: { marginTop: 8, fontSize: 14, color: "#64748b" },
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
  likeBtn: {
    alignSelf: "flex-start",
    marginTop: 4,
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: 999,
    backgroundColor: "#e0e7ff",
  },
  likeBtnText: { fontSize: 13, color: "#3730a3", fontWeight: "500" },
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

