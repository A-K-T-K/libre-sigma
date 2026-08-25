import { AnalysisResult, ColumnDef, PluginManifestItem, SampleDatasetMeta } from '../types';

let cachedPort: number | null = null;
let heartbeatInterval: any = null;

/**
 * Detects if running inside the Tauri native desktop shell.
 */
export function isTauriEnvironment(): boolean {
  return typeof window !== 'undefined' && ('__TAURI__' in window || '__TAURI_IPC__' in window);
}

// Proactively listen for the backend-ready event from Tauri
if (isTauriEnvironment()) {
  import('@tauri-apps/api/event')
    .then(({ listen }) => {
      listen<number>('backend-ready', (event) => {
        if (event.payload && typeof event.payload === 'number') {
          cachedPort = event.payload;
        }
      });
    })
    .catch(() => {});
}

/**
 * Resolves the active backend API base URL with dynamic port binding.
 * If in Tauri mode and port isn't ready yet, polls get_backend_port for up to timeoutMs.
 */
export async function getApiBaseUrl(timeoutMs: number = 15000): Promise<string> {
  if (cachedPort) {
    return `http://127.0.0.1:${cachedPort}/api/v1`;
  }

  if (isTauriEnvironment()) {
    const startTime = Date.now();
    while (Date.now() - startTime < timeoutMs) {
      try {
        const { invoke } = await import('@tauri-apps/api/tauri');
        const port = await invoke<number>('get_backend_port');
        if (port && typeof port === 'number' && port > 0) {
          cachedPort = port;
          return `http://127.0.0.1:${cachedPort}/api/v1`;
        }
      } catch {
        // Backend port still initializing
      }
      await new Promise((r) => setTimeout(r, 100));
    }
  }

  // Web development fallback (Vite proxy or default port 8000)
  return '/api/v1';
}

/**
 * Heartbeat monitor: pings the backend every 2.5 seconds to keep the process alive.
 */
export function startHeartbeatMonitor(intervalMs: number = 2500): () => void {
  if (heartbeatInterval) {
    clearInterval(heartbeatInterval);
  }

  const ping = async () => {
    try {
      const baseUrl = await getApiBaseUrl(500);
      await fetch(`${baseUrl}/heartbeat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      });
    } catch {
      // Ignore transient network errors during startup
    }
  };

  // Immediate first ping
  ping();
  heartbeatInterval = setInterval(ping, intervalMs);

  return () => {
    if (heartbeatInterval) {
      clearInterval(heartbeatInterval);
      heartbeatInterval = null;
    }
  };
}

/**
 * Executes a fetch request against the dynamic backend URL with retry support.
 */
async function apiFetch(endpoint: string, options: RequestInit = {}, retries: number = 5): Promise<Response> {
  let lastError: any = null;
  for (let attempt = 0; attempt < retries; attempt++) {
    try {
      const baseUrl = await getApiBaseUrl();
      const cleanEndpoint = endpoint.startsWith('/') ? endpoint : `/${endpoint}`;
      const url = `${baseUrl}${cleanEndpoint}`;

      const res = await fetch(url, options);
      return res;
    } catch (err) {
      lastError = err;
      if (attempt < retries - 1) {
        await new Promise((r) => setTimeout(r, 300));
      }
    }
  }
  throw lastError || new Error(`Network request failed for ${endpoint}`);
}

export async function fetchManifest(): Promise<PluginManifestItem[]> {
  const res = await apiFetch('/plugins/manifest');
  if (!res.ok) {
    throw new Error(`Failed to load plugin manifest (${res.status}): ${res.statusText}`);
  }
  return res.json();
}

export async function computeAnalysis(
  pluginId: string,
  data: Record<string, any>[],
  columns: ColumnDef[],
  params: Record<string, any>
): Promise<AnalysisResult> {
  const res = await apiFetch(`/compute/${pluginId}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      data,
      columns,
      params,
    }),
  });

  if (!res.ok) {
    let errorDetail = res.statusText;
    try {
      const errorJson = await res.json();
      errorDetail = errorJson.detail || JSON.stringify(errorJson);
    } catch {
      // If parsing json fails, keep statusText
    }
    throw new Error(`Analysis failed (${res.status}): ${errorDetail}`);
  }

  return res.json();
}

export async function fetchSampleDatasets(): Promise<SampleDatasetMeta[]> {
  const res = await apiFetch('/sample-datasets');
  if (!res.ok) {
    throw new Error(`Failed to fetch sample datasets: ${res.statusText}`);
  }
  return res.json();
}

export async function loadSampleDataset(id: string): Promise<{
  id: string;
  name: string;
  description: string;
  columns: { id: string; name: string; type?: string }[];
  rows: Record<string, any>[];
}> {
  const res = await apiFetch(`/sample-datasets/${id}`);
  if (!res.ok) {
    throw new Error(`Failed to load sample dataset '${id}': ${res.statusText}`);
  }
  return res.json();
}

export const fetchSampleDataset = loadSampleDataset;

