# CivicView Mobile

React Native (Expo) app for reporting civic issues with **photo and location**. Uses the same Django API as the web app.

## Features

- **Login / Register** – Token auth against the CivicView API
- **Recent reports** – List of reports (pull to refresh)
- **Report an issue** – Title, description, category, **location** (Use my location), and **photos** (take with camera)
- Photos are uploaded after the report is created and attached to the report

## Setup

1. **Install dependencies**

   ```bash
   cd mobile
   npm install
   ```

2. **API base URL**

   The app defaults to `http://127.0.0.1:8000/api`. For a physical device or emulator:

   - **Android emulator:** use `http://10.0.2.2:8000/api` (or set in code)
   - **iOS simulator:** `http://127.0.0.1:8000/api` is fine
   - **Physical device:** use your computer’s LAN IP, e.g. `http://192.168.1.x:8000/api`

   To change it, edit `api.js` and set `getBaseUrl()` to return your API URL (no trailing slash; the path is `/api`).

3. **Backend**

   - Run Django with `python manage.py runserver`
   - Run migrations so `ReportImage` exists: `python manage.py migrate`
   - Ensure CORS allows your Expo/device origin if needed (e.g. add your IP to `CORS_ALLOWED_ORIGINS` or allow all in dev)

4. **Assets (optional)**

   If you see missing asset errors, add under `assets/`:

   - `icon.png` (1024×1024)
   - `splash-icon.png`
   - `adaptive-icon.png` (Android)

   Or remove/comment the `icon` and `splash` entries in `app.json` to use Expo defaults.

## Run

```bash
npx expo start
```

Then scan the QR code with Expo Go (Android/iOS) or press `a` for Android emulator / `i` for iOS simulator.

## Permissions

- **Camera** – To take photos of the issue
- **Location** – To pin the report on the map (must be within Ireland for the API)

These are requested when you tap “Use my location” and “Take photo” in the Report screen.
