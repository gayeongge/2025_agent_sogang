const { app, BrowserWindow, dialog } = require('electron');
const fs = require('fs');
const path = require('path');
const { spawn } = require('child_process');
const http = require('http');

let backendProcess;
const PROJECT_ROOT = path.resolve(__dirname, '..');
const BACKEND_HOST = process.env.INCIDENT_BACKEND_HOST || '127.0.0.1';
// Electron 런처는 기본적으로 8000 포트에서 백엔드를 기동한다.
const BACKEND_PORT = process.env.INCIDENT_BACKEND_PORT || '8000';
const BACKEND_URL = `http://${BACKEND_HOST}:${BACKEND_PORT}`;
process.env.INCIDENT_BACKEND_URL = BACKEND_URL;

function resolvePythonExecutable() {
  if (process.env.PYTHON_EXE) {
    return process.env.PYTHON_EXE;
  }

  if (process.env.PYTHON && process.env.PYTHON.trim()) {
    return process.env.PYTHON.trim();
  }

  const candidates = [];
  if (process.platform === 'win32') {
    candidates.push(path.join(PROJECT_ROOT, '.venv', 'Scripts', 'python.exe'));
    candidates.push(path.join(PROJECT_ROOT, '.venv', 'Scripts', 'python'));
    candidates.push('python');
    candidates.push('python3');
  } else {
    candidates.push(path.join(PROJECT_ROOT, '.venv', 'bin', 'python'));
    candidates.push('python3');
    candidates.push('python');
  }

  for (const candidate of candidates) {
    if (candidate.includes(path.sep)) {
      if (fs.existsSync(candidate)) {
        return candidate;
      }
    } else {
      return candidate;
    }
  }

  return 'python';
}

function startBackend() {
  const python = resolvePythonExecutable();
  const env = {
    ...process.env,
    INCIDENT_BACKEND_HOST: BACKEND_HOST,
    INCIDENT_BACKEND_PORT: BACKEND_PORT,
    INCIDENT_BACKEND_RELOAD: '0',
    PYTHONIOENCODING: 'utf-8',
  };

  backendProcess = spawn(python, ['-m', 'src.backend.main'], {
    cwd: PROJECT_ROOT,
    env,
    stdio: ['ignore', 'pipe', 'pipe'],
  });
  console.log(`[backend] launching ${python}`);

  backendProcess.stdout.on('data', (data) => {
    console.log(`[backend] ${data.toString().trim()}`);
  });

  backendProcess.stderr.on('data', (data) => {
    console.error(`[backend err] ${data.toString().trim()}`);
  });

  backendProcess.on('exit', (code) => {
    console.log(`[backend] exited with code ${code}`);
    if (!app.isQuitting) {
      dialog.showErrorBox(
        'Backend exited',
        `The Python backend terminated unexpectedly (code ${code}).`
      );
      app.quit();
    }
  });
}

function waitForBackend(retries = 40, delayMs = 250) {
  return new Promise((resolve, reject) => {
    const attempt = (remaining) => {
      const req = http.get(`${BACKEND_URL}/health`, (res) => {
        if (res.statusCode === 200) {
          res.resume();
          resolve();
        } else {
          res.resume();
          retry(remaining - 1);
        }
      });
      req.on('error', () => retry(remaining - 1));
      req.setTimeout(200, () => {
        req.destroy();
        retry(remaining - 1);
      });
    };

    const retry = (remaining) => {
      if (remaining <= 0) {
        reject(new Error('Backend did not respond in time'));
        return;
      }
      setTimeout(() => attempt(remaining), delayMs);
    };

    attempt(retries);
  });
}

async function createWindow() {
  try {
    await waitForBackend();
  } catch (error) {
    dialog.showErrorBox('Backend error', error.message);
    app.quit();
    return;
  }

  const win = new BrowserWindow({
    width: 1280,
    height: 820,
    title: 'Incident Response Console',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      spellcheck: false,
    },
  });

  win.loadFile(path.join(__dirname, 'renderer', 'index.html'));
}

app.whenReady().then(() => {
  startBackend();
  createWindow();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('before-quit', () => {
  app.isQuitting = true;
  if (backendProcess && !backendProcess.killed) {
    backendProcess.kill();
  }
});

process.on('exit', () => {
  if (backendProcess && !backendProcess.killed) {
    backendProcess.kill();
  }
});

