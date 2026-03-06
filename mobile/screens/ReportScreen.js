import { useCallback, useEffect, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
  Image,
} from "react-native";
import { StatusBar } from "expo-status-bar";
import * as ImagePicker from "expo-image-picker";
import * as Location from "expo-location";
import {
  createReport,
  fetchCategories,
  uploadReportImages,
} from "../api";

const IRELAND_BOUNDS = { latMin: 51.4, latMax: 55.4, lonMin: -11, lonMax: -5 };

export default function ReportScreen({ onBack, onSuccess }) {
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [category, setCategory] = useState("");
  const [categories, setCategories] = useState([]);
  const [photos, setPhotos] = useState([]);
  const [location, setLocation] = useState(null);
  const [locationError, setLocationError] = useState("");
  const [loading, setLoading] = useState(false);
  const [loadingCategories, setLoadingCategories] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    fetchCategories()
      .then((list) => {
        setCategories(Array.isArray(list) ? list : []);
        if (list?.length && !category) setCategory(list[0]);
      })
      .catch(() => setCategories([]))
      .finally(() => setLoadingCategories(false));
  }, []);

  const requestLocation = useCallback(async () => {
    setLocationError("");
    const { status } = await Location.requestForegroundPermissionsAsync();
    if (status !== "granted") {
      setLocationError("Location permission is required to pin the report.");
      return;
    }
    try {
      const loc = await Location.getCurrentPositionAsync({
        accuracy: Location.Accuracy.Balanced,
      });
      const { latitude, longitude } = loc.coords;
      if (
        latitude >= IRELAND_BOUNDS.latMin &&
        latitude <= IRELAND_BOUNDS.latMax &&
        longitude >= IRELAND_BOUNDS.lonMin &&
        longitude <= IRELAND_BOUNDS.lonMax
      ) {
        setLocation({ latitude, longitude });
      } else {
        setLocationError("Location must be within Ireland.");
      }
    } catch (e) {
      setLocationError("Could not get location. Try again.");
    }
  }, []);

  const takePhoto = useCallback(async () => {
    const { status } = await ImagePicker.requestCameraPermissionsAsync();
    if (status !== "granted") {
      Alert.alert("Camera", "Camera permission is required to take a photo.");
      return;
    }
    const result = await ImagePicker.launchCameraAsync({
      mediaTypes: ImagePicker.MediaTypeOptions.Images,
      allowsEditing: false,
      quality: 0.8,
    });
    if (!result.canceled && result.assets?.[0]?.uri) {
      setPhotos((p) => [...p, result.assets[0].uri]);
    }
  }, []);

  const removePhoto = (index) => {
    setPhotos((p) => p.filter((_, i) => i !== index));
  };

  const submit = async () => {
    const t = title.trim();
    const d = description.trim();
    const c = category || categories[0];
    if (!t) {
      setError("Please enter a title.");
      return;
    }
    if (!d) {
      setError("Please enter a description.");
      return;
    }
    if (!location) {
      setError("Please allow location so we can pin the report on the map.");
      return;
    }
    setError("");
    setLoading(true);
    try {
      const report = await createReport({
        title: t,
        description: d,
        category: c || "Other",
        latitude: location.latitude,
        longitude: location.longitude,
      });
      const reportId = report?.id;
      if (reportId && photos.length > 0) {
        await uploadReportImages(reportId, photos);
      }
      onSuccess();
    } catch (err) {
      const msg =
        err?.detail ||
        err?.latitude?.[0] ||
        err?.longitude?.[0] ||
        (Array.isArray(err?.title) ? err.title.join(" ") : err?.title) ||
        "Failed to submit report.";
      setError(typeof msg === "string" ? msg : JSON.stringify(msg));
    } finally {
      setLoading(false);
    }
  };

  return (
    <KeyboardAvoidingView
      behavior={Platform.OS === "ios" ? "padding" : undefined}
      style={styles.container}
    >
      <StatusBar style="auto" />
      <View style={styles.header}>
        <Pressable onPress={onBack} style={styles.backBtn}>
          <Text style={styles.backText}>← Back</Text>
        </Pressable>
        <Text style={styles.headerTitle}>Report an issue</Text>
      </View>

      <ScrollView
        style={styles.scroll}
        contentContainerStyle={styles.scrollContent}
        keyboardShouldPersistTaps="handled"
      >
        {error ? (
          <View style={styles.errorBox}>
            <Text style={styles.errorText}>{error}</Text>
          </View>
        ) : null}

        <Text style={styles.label}>Title</Text>
        <TextInput
          style={styles.input}
          placeholder="e.g. Pothole on Main Street"
          value={title}
          onChangeText={setTitle}
          editable={!loading}
        />

        <Text style={styles.label}>Description</Text>
        <TextInput
          style={[styles.input, styles.textArea]}
          placeholder="Describe the issue..."
          value={description}
          onChangeText={setDescription}
          multiline
          numberOfLines={3}
          editable={!loading}
        />

        <Text style={styles.label}>Category</Text>
        {loadingCategories ? (
          <Text style={styles.hint}>Loading categories…</Text>
        ) : (
          <ScrollView
            horizontal
            showsHorizontalScrollIndicator={false}
            style={styles.categoryScroll}
          >
            {(categories.length ? categories : ["Other"]).map((cat) => (
              <Pressable
                key={cat}
                style={[
                  styles.chip,
                  category === cat && styles.chipSelected,
                ]}
                onPress={() => setCategory(cat)}
              >
                <Text
                  style={[
                    styles.chipText,
                    category === cat && styles.chipTextSelected,
                  ]}
                >
                  {cat}
                </Text>
              </Pressable>
            ))}
          </ScrollView>
        )}

        <Text style={styles.label}>Location</Text>
        <Pressable
          style={[styles.locationBtn, location && styles.locationBtnOk]}
          onPress={requestLocation}
          disabled={loading}
        >
          <Text style={styles.locationBtnText}>
            {location
              ? `✓ ${location.latitude.toFixed(4)}, ${location.longitude.toFixed(4)}`
              : "Use my location"}
          </Text>
        </Pressable>
        {locationError ? (
          <Text style={styles.locationError}>{locationError}</Text>
        ) : null}

        <Text style={styles.label}>Photo of the issue</Text>
        <Pressable style={styles.photoBtn} onPress={takePhoto} disabled={loading}>
          <Text style={styles.photoBtnText}>📷 Take photo</Text>
        </Pressable>
        {photos.length > 0 && (
          <View style={styles.photoList}>
            {photos.map((uri, i) => (
              <View key={i} style={styles.photoWrap}>
                <Image source={{ uri }} style={styles.thumb} />
                <Pressable
                  style={styles.removePhoto}
                  onPress={() => removePhoto(i)}
                >
                  <Text style={styles.removePhotoText}>✕</Text>
                </Pressable>
              </View>
            ))}
          </View>
        )}
        <Text style={styles.hint}>You can take multiple photos. At least one is recommended.</Text>

        <Pressable
          style={[styles.submitBtn, loading && styles.submitDisabled]}
          onPress={submit}
          disabled={loading}
        >
          {loading ? (
            <ActivityIndicator color="#fff" />
          ) : (
            <Text style={styles.submitBtnText}>Submit report</Text>
          )}
        </Pressable>
      </ScrollView>
    </KeyboardAvoidingView>
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
  headerTitle: { fontSize: 18, fontWeight: "600", color: "#0f172a" },
  scroll: { flex: 1 },
  scrollContent: { padding: 20, paddingBottom: 40 },
  errorBox: {
    backgroundColor: "#fee2e2",
    padding: 12,
    borderRadius: 8,
    marginBottom: 16,
    borderWidth: 1,
    borderColor: "#fecaca",
  },
  errorText: { color: "#b91c1c", fontSize: 14 },
  label: { fontSize: 14, fontWeight: "600", color: "#334155", marginBottom: 6 },
  input: {
    backgroundColor: "#fff",
    borderWidth: 1,
    borderColor: "#e2e8f0",
    borderRadius: 10,
    padding: 14,
    fontSize: 16,
    marginBottom: 16,
  },
  textArea: { minHeight: 88, textAlignVertical: "top" },
  hint: { fontSize: 12, color: "#64748b", marginBottom: 16 },
  categoryScroll: { marginBottom: 16 },
  chip: {
    paddingHorizontal: 14,
    paddingVertical: 10,
    borderRadius: 20,
    backgroundColor: "#e2e8f0",
    marginRight: 8,
  },
  chipSelected: { backgroundColor: "#667eea" },
  chipText: { fontSize: 14, color: "#475569" },
  chipTextSelected: { color: "#fff" },
  locationBtn: {
    backgroundColor: "#fff",
    borderWidth: 1,
    borderColor: "#e2e8f0",
    padding: 14,
    borderRadius: 10,
    marginBottom: 4,
  },
  locationBtnOk: { borderColor: "#16a34a", backgroundColor: "#f0fdf4" },
  locationBtnText: { fontSize: 15, color: "#0f172a" },
  locationError: { fontSize: 12, color: "#b91c1c", marginBottom: 16 },
  photoBtn: {
    backgroundColor: "#667eea",
    padding: 14,
    borderRadius: 10,
    alignItems: "center",
    marginBottom: 12,
  },
  photoBtnText: { color: "#fff", fontSize: 15, fontWeight: "600" },
  photoList: { flexDirection: "row", flexWrap: "wrap", marginBottom: 8 },
  photoWrap: { marginRight: 8, marginBottom: 8, position: "relative" },
  thumb: { width: 80, height: 80, borderRadius: 8 },
  removePhoto: {
    position: "absolute",
    top: 4,
    right: 4,
    width: 22,
    height: 22,
    borderRadius: 11,
    backgroundColor: "rgba(0,0,0,0.6)",
    justifyContent: "center",
    alignItems: "center",
  },
  removePhotoText: { color: "#fff", fontSize: 12 },
  submitBtn: {
    backgroundColor: "#667eea",
    padding: 16,
    borderRadius: 10,
    alignItems: "center",
    marginTop: 24,
  },
  submitDisabled: { opacity: 0.7 },
  submitBtnText: { color: "#fff", fontSize: 16, fontWeight: "600" },
});
