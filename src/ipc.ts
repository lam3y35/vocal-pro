// Typed Tauri v2 IPC bridge (N4, N6).
// Invokes native Rust commands via window.__TAURI_INTERNALS__.invoke when running
// inside the Tauri desktop shell, and falls back gracefully in headless browser tests.

declare global {
  interface Window {
    __TAURI_INTERNALS__?: {
      invoke: <T>(cmd: string, args?: Record<string, unknown>) => Promise<T>;
    };
  }
}

export function isTauriRuntime(): boolean {
  return typeof window !== "undefined" && typeof window.__TAURI_INTERNALS__?.invoke === "function";
}

export async function invokeCommand<T>(
  cmd: string,
  args: Record<string, unknown> = {}
): Promise<T | null> {
  if (isTauriRuntime() && window.__TAURI_INTERNALS__) {
    return window.__TAURI_INTERNALS__.invoke<T>(cmd, args);
  }
  return null;
}
