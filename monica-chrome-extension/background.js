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
  lastHeartbeat: null,
  // Sleep/wake tracking
  lastActiveAt: null,  // Timestamp when system was last known to be active
  idleState: 'active', // 'active', 'idle', or 'locked'
  wasSleeping: false,  // Flag to indicate we just woke from sleep
  sleepDuration: null  // Duration of sleep in seconds (for reporting)
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
  setupIdleDetection();

  if (state.configured && state.registered) {
    console.log('[Monica] Already configured and registered, resuming monitoring');
  }
})();

// Idle detection threshold (seconds) - system is considered idle after this
const IDLE_DETECTION_THRESHOLD = 60;

// Sleep detection threshold (seconds) - if gap between activity exceeds this, assume sleep
const SLEEP_DETECTION_THRESHOLD = 180; // 3 minutes

// Setup idle state detection
function setupIdleDetection() {
  // Set the idle detection interval
  chrome.idle.setDetectionInterval(IDLE_DETECTION_THRESHOLD);

  // Listen for idle state changes
  chrome.idle.onStateChanged.addListener(handleIdleStateChange);

  // Get current idle state
  chrome.idle.queryState(IDLE_DETECTION_THRESHOLD, (idleState) => {
    state.idleState = idleState;
    if (idleState === 'active') {
      state.lastActiveAt = Date.now();
    }
    console.log('[Monica] Initial idle state:', idleState);
  });
}

// Handle idle state changes
function handleIdleStateChange(newState) {
  const previousState = state.idleState;
  state.idleState = newState;

  console.log('[Monica] Idle state changed:', previousState, '->', newState);

  if (newState === 'active') {
    // System became active - check if we were sleeping
    const now = Date.now();

    if (state.lastActiveAt) {
      const inactiveDuration = (now - state.lastActiveAt) / 1000; // seconds

      if (inactiveDuration > SLEEP_DETECTION_THRESHOLD) {
        // We were likely sleeping
        state.wasSleeping = true;
        state.sleepDuration = Math.round(inactiveDuration);
        console.log(`[Monica] Detected wake from sleep after ${state.sleepDuration}s`);

        // If registered, send an immediate heartbeat with wake info
        if (state.configured && state.registered) {
          sendWakeHeartbeat();
        }
      }
    }

    state.lastActiveAt = now;
  } else if (newState === 'idle' || newState === 'locked') {
    // System going idle or locked - record last active time
    if (previousState === 'active') {
      state.lastActiveAt = Date.now();
    }
  }
}

// Send a special heartbeat when waking from sleep
async function sendWakeHeartbeat() {
  if (!state.registered) {
    return;
  }

  console.log('[Monica] Sending wake heartbeat...');

  // First, run a quick network test to check connectivity
  let networkOk = false;
  try {
    const response = await fetch(`${state.monicaUrl}/health`, {
      cache: 'no-store'
    });
    networkOk = response.ok;
  } catch (error) {
    console.log('[Monica] Network check on wake failed:', error.message);
    networkOk = false;
  }

  try {
    const payload = {
      timestamp: new Date().toISOString(),
      wake_event: true,
      was_sleeping: true,
      sleep_duration_seconds: state.sleepDuration,
      network_ok_on_wake: networkOk
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

    // Check if device was deleted from server (401 = invalid token)
    if (response.status === 401) {
      await handleDeviceDeleted();
      return;
    }

    const data = await response.json();

    if (data.success) {
      state.heartbeatCount++;
      state.lastHeartbeat = new Date().toISOString();
      state.lastError = null;
      // Clear sleep flags after successful report
      state.wasSleeping = false;
      state.sleepDuration = null;

      await saveState();
      console.log('[Monica] Wake heartbeat sent successfully');
    } else {
      throw new Error(data.error || 'Wake heartbeat failed');
    }
  } catch (error) {
    console.error('[Monica] Wake heartbeat failed:', error);
    state.lastError = `Wake heartbeat failed: ${error.message}`;
  }
}

// Handle when device has been deleted from the server
async function handleDeviceDeleted() {
  console.log('[Monica] Device was deleted from server, resetting configuration');

  // Keep the server URL so user can easily reconfigure
  const serverUrl = state.monicaUrl;

  // Clear registration state
  state.registered = false;
  state.agentToken = null;
  state.deviceId = null;
  state.storeCode = null;
  state.deviceLabel = null;
  state.heartbeatCount = 0;
  state.lastLatency = null;
  state.lastSpeed = null;
  state.lastHeartbeat = null;
  state.lastError = 'Device was removed from the Monica server. Please reconfigure with a new registration code.';

  // Update storage - keep monicaUrl but clear device-specific data
  await chrome.storage.local.set({
    monicaUrl: serverUrl,
    storeCode: null,
    deviceLabel: null,
    agentToken: null,
    deviceId: null,
    heartbeatCount: 0
  });

  console.log('[Monica] Configuration cleared - device needs to be reconfigured');
}

// Load state from chrome.storage
async function loadState() {
  const stored = await chrome.storage.local.get([
    'monicaUrl',
    'storeCode',
    'deviceLabel',
    'agentToken',
    'deviceId',
    'heartbeatCount',
    'lastActiveAt'
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
    state.lastActiveAt = stored.lastActiveAt || Date.now();
    state.registered = !!(state.agentToken && state.deviceId);

    console.log('[Monica] State loaded:', {
      configured: state.configured,
      registered: state.registered,
      deviceId: state.deviceId,
      storeCode: state.storeCode,
      deviceLabel: state.deviceLabel,
      hasPermission: true,
      lastActiveAt: state.lastActiveAt
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
    heartbeatCount: state.heartbeatCount,
    lastActiveAt: state.lastActiveAt
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

    // Check if device was deleted from server (401 = invalid token)
    if (response.status === 401) {
      await handleDeviceDeleted();
      return;
    }

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
      const newLatency = Math.round(end - start);
      state.lastLatency = newLatency;
      console.log('[Monica] Latency:', state.lastLatency, 'ms');

      // Save state to persist latency across service worker restarts
      await saveState();
    } else {
      console.warn(`[Monica] Latency test returned ${response.status}: keeping last known value`);
      // Don't reset to null - keep last known good value
    }
  } catch (error) {
    console.error('[Monica] Latency test failed:', error.message || error);
    // Don't reset to null - keep last known good value
    // This prevents latency from disappearing due to transient network issues
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
    const newSpeed = parseFloat((sizeMb / durationSeconds).toFixed(2));
    state.lastSpeed = newSpeed;

    console.log('[Monica] Download speed:', state.lastSpeed, 'Mbps');

    // Save state to persist speed across service worker restarts
    await saveState();
  } catch (error) {
    console.error('[Monica] Speed test failed:', error.message || error);
    // Don't reset to null - keep last known good value
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
