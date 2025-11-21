// Monica Store Monitor - Background Service Worker
// Handles registration, heartbeats, and network monitoring

const HEARTBEAT_INTERVAL = 60; // seconds
const NETWORK_TEST_INTERVAL = 300; // seconds (5 minutes)

// State
let state = {
  configured: false,
  registered: false,
  monicaUrl: null,
  registrationCode: null, // One-time code, not persisted
  storeCode: null,
  deviceLabel: null,
  agentToken: null,
  deviceId: null,
  heartbeatCount: 0,
  lastLatency: null,
  lastSpeed: null,
  lastError: null,
  lastHeartbeat: null
};

// Initialize on install
chrome.runtime.onInstalled.addListener(async () => {
  console.log('[Monica] Extension installed');
  await loadState();
  setupAlarms();

  // If already configured, start monitoring
  if (state.configured) {
    await initialize();
  }
});

// Initialize on startup
chrome.runtime.onStartup.addListener(async () => {
  console.log('[Monica] Browser started');
  await loadState();

  if (state.configured) {
    await initialize();
  }
});

// Load state immediately when service worker starts
// (Service workers can be terminated and restarted frequently)
(async () => {
  console.log('[Monica] Service worker starting...');
  await loadState();
  setupAlarms();

  if (state.configured && state.registered) {
    console.log('[Monica] Already configured and registered, resuming monitoring');
  }
})();

// Load state from chrome.storage
async function loadState() {
  const stored = await chrome.storage.local.get([
    'monicaUrl',
    'storeCode',
    'deviceLabel',
    'agentToken',
    'deviceId',
    'heartbeatCount'
  ]);

  if (stored.monicaUrl) {
    //Check if we still have permission for the stored URL
    try {
      const urlObj = new URL(stored.monicaUrl);
      const origin = `${urlObj.protocol}//${urlObj.host}/*`;
      const hasPermission = await chrome.permissions.contains({
        origins: [origin]
      });

      if (!hasPermission) {
        console.log('[Monica] Permission missing for', origin, '- user needs to reconfigure');
        // Keep config but clear registration to trigger reconfiguration
        state.configured = true;
        state.monicaUrl = stored.monicaUrl;
        state.storeCode = stored.storeCode || null;
        state.deviceLabel = stored.deviceLabel || null;
        state.registered = false;
        state.agentToken = null;
        state.deviceId = null;
        return;
      }
    } catch (e) {
      console.log('[Monica] Error checking permissions:', e);
    }

    state.configured = true;
    state.monicaUrl = stored.monicaUrl;
    state.storeCode = stored.storeCode || null;
    state.deviceLabel = stored.deviceLabel || null;
    state.agentToken = stored.agentToken || null;
    state.deviceId = stored.deviceId || null;
    state.heartbeatCount = stored.heartbeatCount || 0;
    state.registered = !!(state.agentToken && state.deviceId);

    console.log('[Monica] State loaded:', {
      configured: state.configured,
      registered: state.registered,
      deviceId: state.deviceId,
      storeCode: state.storeCode,
      deviceLabel: state.deviceLabel,
      hasPermission: true
    });
  } else {
    console.log('[Monica] Not yet configured');
  }
}

// Save state to chrome.storage
async function saveState() {
  await chrome.storage.local.set({
    monicaUrl: state.monicaUrl,
    storeCode: state.storeCode,
    deviceLabel: state.deviceLabel,
    agentToken: state.agentToken,
    deviceId: state.deviceId,
    heartbeatCount: state.heartbeatCount
  });
}

// Setup periodic alarms
function setupAlarms() {
  // Heartbeat alarm - fire first alarm in 10 seconds, then every 60 seconds
  chrome.alarms.create('heartbeat', {
    when: Date.now() + 10000, // First fire in 10 seconds
    periodInMinutes: HEARTBEAT_INTERVAL / 60
  });

  // Network test alarm - fire first alarm in 30 seconds, then every 5 minutes
  chrome.alarms.create('networkTest', {
    when: Date.now() + 30000, // First fire in 30 seconds
    periodInMinutes: NETWORK_TEST_INTERVAL / 60
  });

  console.log('[Monica] Alarms configured');
}

// Handle alarms
chrome.alarms.onAlarm.addListener(async (alarm) => {
  if (!state.configured || !state.registered) {
    console.log('[Monica] Skipping alarm - not configured/registered');
    return;
  }

  if (alarm.name === 'heartbeat') {
    await sendHeartbeat();
  } else if (alarm.name === 'networkTest') {
    await runNetworkTest();
  }
});

// Initialize and register
async function initialize() {
  console.log('[Monica] Initializing...');

  if (!state.configured) {
    console.log('[Monica] Cannot initialize - not configured');
    return { success: false, error: 'Not configured' };
  }

  // Register if needed
  if (!state.registered) {
    const registered = await register();
    if (!registered) {
      return { success: false, error: state.lastError || 'Registration failed' };
    }
  }

  // Send immediate heartbeat and network test
  if (state.registered) {
    await runNetworkTest();
    await sendHeartbeat();
  }

  return { success: true };
}

// Register with Monica
async function register() {
  if (!state.configured) {
    state.lastError = 'Not configured';
    return false;
  }

  console.log('[Monica] Registering...');

  try {
    // Get extension version from manifest
    const manifest = chrome.runtime.getManifest();
    const version = manifest.version;

    const response = await fetch(`${state.monicaUrl}/api/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        registration_code: state.registrationCode,
        extension_version: version
      })
    });

    const data = await response.json();

    if (data.success) {
      state.agentToken = data.agent_token;
      state.deviceId = data.device_id;
      state.storeCode = data.store_code; // Get from server response
      state.deviceLabel = data.device_label; // Get from server response
      state.registered = true;
      state.lastError = null;

      await saveState();

      console.log('[Monica] Registration successful:', state.deviceId);
      return true;
    } else {
      throw new Error(data.error || 'Registration failed');
    }
  } catch (error) {
    console.error('[Monica] Registration failed:', error);
    state.lastError = `Registration failed: ${error.message}`;
    state.registered = false;
    return false;
  }
}

// Send heartbeat
async function sendHeartbeat() {
  if (!state.registered) {
    console.log('[Monica] Cannot send heartbeat - not registered');
    return;
  }

  try {
    const payload = {
      timestamp: new Date().toISOString()
    };

    // Include network metrics if available
    if (state.lastLatency !== null) {
      payload.latency_ms = state.lastLatency;
    }
    if (state.lastSpeed !== null) {
      payload.download_mbps = state.lastSpeed;
    }

    const response = await fetch(`${state.monicaUrl}/api/heartbeat`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Agent-Token': state.agentToken
      },
      body: JSON.stringify(payload)
    });

    const data = await response.json();

    if (data.success) {
      state.heartbeatCount++;
      state.lastHeartbeat = new Date().toISOString();
      state.lastError = null;

      await saveState();

      console.log('[Monica] Heartbeat sent:', state.heartbeatCount);
    } else {
      throw new Error(data.error || 'Heartbeat failed');
    }
  } catch (error) {
    console.error('[Monica] Heartbeat failed:', error);
    state.lastError = `Heartbeat failed: ${error.message}`;
  }
}

// Run network test
async function runNetworkTest() {
  if (!state.configured) {
    return;
  }

  console.log('[Monica] Running network test...');

  // Latency test
  try {
    const start = performance.now();
    const response = await fetch(`${state.monicaUrl}/health`, {
      cache: 'no-store'
    });
    const end = performance.now();

    if (response.ok) {
      state.lastLatency = Math.round(end - start);
      console.log('[Monica] Latency:', state.lastLatency, 'ms');
    }
  } catch (error) {
    console.error('[Monica] Latency test failed:', error);
    state.lastLatency = null;
  }

  // Speed test - simplified for extension
  // We'll download the health endpoint multiple times to estimate speed
  try {
    const testSize = 100000; // 100KB test
    const start = performance.now();

    // Perform multiple small requests
    const promises = [];
    for (let i = 0; i < 10; i++) {
      promises.push(fetch(`${state.monicaUrl}/health?t=${Date.now()}_${i}`, {
        cache: 'no-store'
      }));
    }

    await Promise.all(promises);
    const end = performance.now();

    const durationSeconds = (end - start) / 1000;
    const sizeMb = (testSize * 10) / (1024 * 1024);
    state.lastSpeed = parseFloat((sizeMb / durationSeconds).toFixed(2));

    console.log('[Monica] Download speed:', state.lastSpeed, 'Mbps');
  } catch (error) {
    console.error('[Monica] Speed test failed:', error);
    state.lastSpeed = null;
  }
}

// Listen for messages from popup
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.action === 'getState') {
    // Always verify state is in sync with storage before sending
    chrome.storage.local.get(['monicaUrl']).then((stored) => {
      if (stored.monicaUrl && stored.monicaUrl !== state.monicaUrl) {
        console.log('[Monica] State out of sync! Reloading from storage...');
        loadState().then(() => sendResponse(state));
      } else {
        sendResponse(state);
      }
    });
    return true; // Keep channel open for async response
  } else if (message.action === 'configure') {
    // Handle reconfiguration: revoke old permissions if URL is changing
    const oldUrl = state.monicaUrl;
    const newUrl = message.monicaUrl.replace(/\/$/, ''); // Remove trailing slash

    // If URL is changing, revoke old permissions
    if (oldUrl && oldUrl !== newUrl) {
      try {
        const oldUrlObj = new URL(oldUrl);
        const oldOrigin = `${oldUrlObj.protocol}//${oldUrlObj.host}/*`;
        chrome.permissions.remove({
          origins: [oldOrigin]
        });
        console.log('[Monica] Revoked permissions for old URL:', oldOrigin);
      } catch (e) {
        console.log('[Monica] Error revoking old permissions:', e);
      }
    }

    // Update configuration
    state.monicaUrl = newUrl;
    state.registrationCode = message.registrationCode; // One-time code for registration (includes store/device info)
    state.configured = true;
    state.registered = false;
    state.agentToken = null;
    state.deviceId = null;
    state.storeCode = null; // Will be populated from registration response
    state.deviceLabel = null; // Will be populated from registration response
    state.heartbeatCount = 0;
    state.lastError = null;

    // Save state and wait for completion before proceeding
    saveState().then(async () => {
      // Verify the save by reading back
      const verification = await chrome.storage.local.get(['monicaUrl']);
      console.log('[Monica] Configuration saved. Verified monicaUrl:', verification.monicaUrl);

      initialize().then((result) => {
        // Clear registration code after use (not persisted)
        state.registrationCode = null;
        if (result.success) {
          sendResponse({ success: true, state: state });
        } else {
          sendResponse({ success: false, error: result.error, state: state });
        }
      });
    });

    return true; // Keep channel open for async response
  } else if (message.action === 'testConnection') {
    // Test connection to Monica server
    fetch(`${message.monicaUrl}/health`)
      .then(response => {
        if (response.ok) {
          sendResponse({ success: true });
        } else {
          sendResponse({ success: false, error: `Server returned ${response.status}` });
        }
      })
      .catch(error => {
        sendResponse({ success: false, error: error.message });
      });

    return true; // Keep channel open for async response
  }
});

// Export state for debugging
console.log('[Monica] Background service worker loaded');
