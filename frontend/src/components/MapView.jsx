// Import React hooks for state management and side effects
import { useEffect, useState } from "react";
// Import React-Leaflet components for interactive map
import { MapContainer, Marker, Polygon, Popup, TileLayer, Tooltip, useMapEvents, useMap } from "react-leaflet";
// Import Leaflet CSS for map styling
import "leaflet/dist/leaflet.css";
// Import Leaflet library for icon configuration
import L from "leaflet";
import ReportDetailCard from "./ReportDetailCard";

// Default blue marker icon for displaying reports on the map
const markerIcon = new L.Icon({
  iconUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png",
  iconRetinaUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png",
  iconSize: [25, 41],
  iconAnchor: [12, 41],
});

// Additional colored marker icons for different report categories
const redMarkerIcon = new L.Icon({
  iconUrl: "https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-red.png",
  iconRetinaUrl: "https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-red.png",
  iconSize: [25, 41],
  iconAnchor: [12, 41],
});

const blueMarkerIcon = new L.Icon({
  iconUrl: "https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-blue.png",
  iconRetinaUrl: "https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-blue.png",
  iconSize: [25, 41],
  iconAnchor: [12, 41],
});

const orangeMarkerIcon = new L.Icon({
  iconUrl: "https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-orange.png",
  iconRetinaUrl: "https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-orange.png",
  iconSize: [25, 41],
  iconAnchor: [12, 41],
});

const yellowMarkerIcon = new L.Icon({
  iconUrl: "https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-yellow.png",
  iconRetinaUrl: "https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-yellow.png",
  iconSize: [25, 41],
  iconAnchor: [12, 41],
});

const violetMarkerIcon = new L.Icon({
  iconUrl: "https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-violet.png",
  iconRetinaUrl: "https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-violet.png",
  iconSize: [25, 41],
  iconAnchor: [12, 41],
});

// Blue marker icon for showing the selected location (when user clicks map)
const selectedMarkerIcon = new L.Icon({
  iconUrl: "https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-blue.png",
  iconRetinaUrl: "https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-blue.png",
  iconSize: [25, 41],
  iconAnchor: [12, 41],
});

// Map report categories to specific colored icons
function getReportIcon(category) {
  if (!category) {
    return markerIcon;
  }
  const key = category.toLowerCase();

  // Adjust these mappings to match the categories you actually use in your data
  if (key.includes("pothole") || key.includes("road")) {
    // Potholes / road damage: red
    return redMarkerIcon;
  }
  if (key.includes("graffiti")) {
    // Graffiti: blue
    return blueMarkerIcon;
  }
  if (key.includes("litter") || key.includes("waste") || key.includes("rubbish")) {
    // Litter and waste: orange
    return orangeMarkerIcon;
  }
  if (key.includes("light")) {
    // Street lighting issues: yellow
    return yellowMarkerIcon;
  }
  if (key.includes("footpath") || key.includes("pavement")) {
    // Footpath / pavement damage: violet
    return violetMarkerIcon;
  }

  // Fallback: default marker
  return markerIcon;
}

// Default map center: Ireland center coordinates (approximate center of the country)
const IRELAND_CENTER = [53.4129, -8.2439];
// Default zoom level: Shows entire country
const IRELAND_ZOOM = 7;

// Component to handle map clicks: Captures click events and passes coordinates to parent
// Uses useMapEvents hook to listen for click events on the map
function MapClickHandler({ onMapClick }) {
  useMapEvents({
    click: (e) => {
      // Extract latitude and longitude from click event and pass to parent component
      onMapClick(e.latlng.lat, e.latlng.lng);
    },
  });
  // This component doesn't render anything, it just handles events
  return null;
}

// Component to programmatically change map view (center and zoom)
// Used when user's geolocation is detected or map needs to be repositioned
function SetMapView({ center, zoom }) {
  // Get map instance from React-Leaflet context
  const map = useMap();
  
  // Update map view when center or zoom changes
  useEffect(() => {
    if (center) {
      // Smoothly animate to new center and zoom level
      map.setView(center, zoom, {
        animate: true,
        duration: 1.5  // Animation duration in seconds
      });
    }
  }, [center, zoom, map]);
  
  // This component doesn't render anything, it just updates map view
  return null;
}

// MapView component: Displays interactive map with reports, hotspots, and user location
// Props:
//   - reports, hotspots, selectedLocation, onMapClick
//   - showReportsLayer, showHotspotsLayer: booleans (controlled from parent left panel)
function MapView({ reports, hotspots, selectedLocation, onMapClick, showReportsLayer = true, showHotspotsLayer = true }) {
  const [mapCenter, setMapCenter] = useState(IRELAND_CENTER);
  const [mapZoom, setMapZoom] = useState(IRELAND_ZOOM);
  const [userLocation, setUserLocation] = useState(null);
  const [locationError, setLocationError] = useState(null);
  const [selectedReport, setSelectedReport] = useState(null);

  // Get user's current location on component mount using browser geolocation API
  useEffect(() => {
    if (navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(
        // Success callback: User location retrieved successfully
        (position) => {
          const { latitude, longitude } = position.coords;
          const userPos = [latitude, longitude];
          setUserLocation(userPos);
          
          // Check if user is roughly in Ireland (bounding box check)
          // Ireland approximate bounds: lat 51.4-55.4, lon -11.0 to -5.0
          if (
            latitude >= 51.4 && latitude <= 55.4 &&
            longitude >= -11.0 && longitude <= -5.0
          ) {
            // User is in Ireland, zoom to their location for better UX
            setMapCenter(userPos);
            setMapZoom(11); // Closer zoom for local area
          } else {
            // User is outside Ireland, show Ireland but with a marker for their location
            setMapCenter(IRELAND_CENTER);
            setMapZoom(IRELAND_ZOOM);
          }
        },
        // Error callback: Location access denied or unavailable
        (error) => {
          setLocationError(error.message);
          // Default to Ireland view if geolocation fails
          setMapCenter(IRELAND_CENTER);
          setMapZoom(IRELAND_ZOOM);
        },
        // Geolocation options
        {
          enableHighAccuracy: true,  // Request high accuracy GPS if available
          timeout: 10000,  // Timeout after 10 seconds
          maximumAge: 0  // Don't use cached location, always get fresh data
        }
      );
    } else {
      // Geolocation not supported by browser
      setLocationError("Geolocation is not supported by your browser");
      setMapCenter(IRELAND_CENTER);
      setMapZoom(IRELAND_ZOOM);
    }
  }, []);

  return (
    <div className="map-container" style={{ position: "relative" }}>
      {/* Map Legend */}
      <div style={{
        position: "absolute",
        top: "10px",
        right: "10px",
        zIndex: 1000,
        background: "rgba(255, 255, 255, 0.95)",
        backdropFilter: "blur(10px)",
        padding: "1rem",
        borderRadius: "12px",
        boxShadow: "0 4px 20px rgba(0, 0, 0, 0.15)",
        border: "1px solid rgba(0, 0, 0, 0.1)",
        fontSize: "0.8rem",
        minWidth: "180px"
      }}>
        <div style={{ fontWeight: 600, marginBottom: "0.75rem", color: "#0f172a", fontSize: "0.9rem" }}>
          Report Categories
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
            <div style={{ width: "20px", height: "20px", backgroundImage: "url(https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-red.png)", backgroundSize: "contain", backgroundRepeat: "no-repeat" }}></div>
            <span style={{ color: "#475569" }}>Potholes / Road</span>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
            <div style={{ width: "20px", height: "20px", backgroundImage: "url(https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-blue.png)", backgroundSize: "contain", backgroundRepeat: "no-repeat" }}></div>
            <span style={{ color: "#475569" }}>Graffiti</span>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
            <div style={{ width: "20px", height: "20px", backgroundImage: "url(https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-orange.png)", backgroundSize: "contain", backgroundRepeat: "no-repeat" }}></div>
            <span style={{ color: "#475569" }}>Litter / Waste</span>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
            <div style={{ width: "20px", height: "20px", backgroundImage: "url(https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-yellow.png)", backgroundSize: "contain", backgroundRepeat: "no-repeat" }}></div>
            <span style={{ color: "#475569" }}>Lighting</span>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
            <div style={{ width: "20px", height: "20px", backgroundImage: "url(https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-violet.png)", backgroundSize: "contain", backgroundRepeat: "no-repeat" }}></div>
            <span style={{ color: "#475569" }}>Footpath</span>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginTop: "0.5rem", paddingTop: "0.5rem", borderTop: "1px solid #e2e8f0" }}>
            <div style={{ width: "20px", height: "20px", backgroundImage: "url(https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png)", backgroundSize: "contain", backgroundRepeat: "no-repeat" }}></div>
            <span style={{ color: "#475569" }}>Other</span>
          </div>
        </div>
      </div>

      <MapContainer
        center={mapCenter}
        zoom={mapZoom}
        scrollWheelZoom={true}
        style={{ height: "100%", width: "100%" }}
      >
        <SetMapView center={mapCenter} zoom={mapZoom} />
        <TileLayer
          attribution='&copy; <a href="http://osm.org/copyright">OpenStreetMap</a>'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        
        {/* Component that handles map click events */}
        <MapClickHandler onMapClick={onMapClick} />

        {/* User's current location marker (if available and outside Ireland) */}
        {/* Only show if user is outside Ireland bounds to avoid clutter */}
        {userLocation && 
         (userLocation[0] < 51.4 || userLocation[0] > 55.4 || 
          userLocation[1] < -11.0 || userLocation[1] > -5.0) && (
          <Marker
            position={userLocation}
            icon={new L.Icon({
              iconUrl: "https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-green.png",
              iconRetinaUrl: "https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-green.png",
              iconSize: [25, 41],
              iconAnchor: [12, 41],
            })}
          >
            <Popup>
              <strong>Your Location</strong>
            </Popup>
          </Marker>
        )}

        {/* Selected location marker: Blue marker showing where user clicked on map */}
        {selectedLocation && (
          <Marker
            position={[selectedLocation.lat, selectedLocation.lng]}
            icon={selectedMarkerIcon}
          >
            <Popup>
              <strong>Selected Location</strong>
              <br />
              Click on the map to change
            </Popup>
          </Marker>
        )}

        {/* Render all reports as category-colored markers on the map (toggleable layer) */}
        {showReportsLayer &&
          reports
            .filter((report) => report.geom)
            .map((report) => (
              <Marker
                key={report.id}
                position={[report.geom.coordinates[1], report.geom.coordinates[0]]}
                icon={getReportIcon(report.category)}
                eventHandlers={{
                  click: () => setSelectedReport(report),
                }}
              >
                <Tooltip direction="top" offset={[0, -20]} opacity={0.9}>
                  <div style={{ fontSize: "0.75rem" }}>
                    <strong>{report.title}</strong>
                    {report.category && (
                      <>
                        <br />
                        <em>{report.category}</em>
                      </>
                    )}
                  </div>
                </Tooltip>
              </Marker>
            ))}

        {/* Render all hotspots as orange polygons (toggleable layer) */}
        {showHotspotsLayer &&
          hotspots
            .filter((hotspot) => hotspot.geom)
            .map((hotspot) => (
            <Polygon
              key={hotspot.id}
              // Convert GeoJSON coordinates to Leaflet format
              // GeoJSON: [lng, lat], Leaflet: [lat, lng]
              // coordinates[0] is the outer ring of the polygon
              positions={hotspot.geom.coordinates[0].map((coord) => [
                coord[1],  // latitude
                coord[0],  // longitude
              ])}
              color="#ea580c"  // Orange color for hotspot polygons
            >
              <Tooltip sticky>
                Cluster {hotspot.cluster_id}
                {hotspot.count !== undefined && ` (${hotspot.count} reports)`}
              </Tooltip>
            </Polygon>
          ))}
      </MapContainer>
      {selectedReport && (
        <ReportDetailCard
          report={selectedReport}
          onClose={() => setSelectedReport(null)}
        />
      )}
    </div>
  );
}

export default MapView;

