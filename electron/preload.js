const { contextBridge } = require('electron');

const backendUrl = process.env.INCIDENT_BACKEND_URL || 'http://127.0.0.1:8000';

contextBridge.exposeInMainWorld('incidentAPI', {
  backendUrl,
});
