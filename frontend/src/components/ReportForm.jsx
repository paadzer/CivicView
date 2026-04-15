// Import React hooks for state management and side effects
import { useState, useEffect } from "react";

import { validateIrelandLocation } from "../lib/locationValidation.js";

const initialState = {
  title: "",
  description: "",
  category: "",
  latitude: "",
  longitude: "",
};

// ReportForm component: Form for submitting new civic issue reports
// Props:
//   - onSubmit: Callback function called when form is submitted
//   - loading: Boolean indicating if form submission is in progress
//   - selectedLocation: Object with lat/lng from map click (or null)
//   - onLocationChange: Callback to clear selected location
//   - categories: Optional array of category names for dropdown
function ReportForm({ onSubmit, loading, selectedLocation, onLocationChange, categories = [] }) {
  const [values, setValues] = useState(initialState);
  const [locationError, setLocationError] = useState(null);

  // Update form coordinates when user clicks on map
  // Automatically populates latitude/longitude fields from map selection
  useEffect(() => {
    if (selectedLocation) {
      setValues((prev) => ({
        ...prev,
        // Format coordinates to 6 decimal places (~10cm precision)
        latitude: selectedLocation.lat.toFixed(6),
        longitude: selectedLocation.lng.toFixed(6),
      }));
    }
  }, [selectedLocation]);

  // Handler for input field changes
  const handleChange = (event) => {
    const { name, value } = event.target;
    setValues((prev) => {
      const updated = { ...prev, [name]: value };
      // If user manually edits coordinates, clear the map selection
      // This prevents confusion if coordinates don't match the blue marker
      if ((name === "latitude" || name === "longitude") && onLocationChange) {
        onLocationChange(null);
      }
      return updated;
    });
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    setLocationError(null);
    const lat = parseFloat(values.latitude);
    const lon = parseFloat(values.longitude);
    const err = validateIrelandLocation(values.latitude, values.longitude);
    if (err) {
      setLocationError(err);
      return;
    }
    await onSubmit({
      ...values,
      latitude: lat,
      longitude: lon,
    });
    setValues(initialState);
  };

  return (
    <form onSubmit={handleSubmit}>
      <label>
        Title
        <input
          name="title"
          value={values.title}
          onChange={handleChange}
          required
        />
      </label>
      <label>
        Description
        <textarea
          name="description"
          value={values.description}
          onChange={handleChange}
          required
        />
      </label>
      <label>
        Category
        <select
          name="category"
          value={values.category}
          onChange={handleChange}
          required
        >
          <option value="">Select a category</option>
          {(categories.length ? categories : ["Other"]).map((cat) => (
            <option key={cat} value={cat}>
              {cat}
            </option>
          ))}
        </select>
      </label>
      <label>
        Latitude
        <input
          name="latitude"
          type="number"
          step="any"
          value={values.latitude}
          onChange={handleChange}
          required
        />
        {selectedLocation && (
          <small style={{ 
            color: "#059669", 
            display: "block", 
            marginTop: "0.25rem",
            padding: "0.5rem",
            background: "#d1fae5",
            borderRadius: "6px",
            fontWeight: 500,
            fontSize: "0.8rem"
          }}>
            ✓ Coordinates set from map click
          </small>
        )}
      </label>
      <label>
        Longitude
        <input
          name="longitude"
          type="number"
          step="any"
          value={values.longitude}
          onChange={handleChange}
          required
        />
      </label>
      {locationError && (
        <div style={{ 
          color: "#dc2626", 
          fontSize: "0.875rem", 
          padding: "0.75rem",
          background: "#fee2e2",
          borderRadius: "8px",
          border: "1px solid #fecaca",
          marginTop: "0.25rem"
        }}>
          {locationError}
        </div>
      )}
      <div style={{ 
        fontSize: "0.875rem", 
        color: "#475569", 
        padding: "0.75rem",
        background: "#f1f5f9",
        borderRadius: "8px",
        border: "1px solid #e2e8f0",
        marginTop: "0.5rem"
      }}>
        💡 <strong>Tip:</strong> Click anywhere on the map to automatically set coordinates
      </div>
      <button type="submit" disabled={loading}>
        {loading ? "Saving..." : "Submit Report"}
      </button>
    </form>
  );
}

export default ReportForm;

