"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError } from "./api";

export interface AsyncState<T> {
  data: T | null;
  error: ApiError | null;
  loading: boolean;
  reload: () => void;
  setData: (d: T | null) => void;
}

/** GET a resource; re-fetches when `path` changes. Pass null to skip. */
export function useApi<T>(path: string | null): AsyncState<T> {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [loading, setLoading] = useState<boolean>(path !== null);
  const [tick, setTick] = useState(0);

  useEffect(() => {
    if (path === null) {
      setLoading(false);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    api
      .get<T>(path)
      .then((d) => !cancelled && setData(d))
      .catch((e: ApiError) => !cancelled && setError(e))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [path, tick]);

  const reload = useCallback(() => setTick((t) => t + 1), []);
  return { data, error, loading, reload, setData };
}

/** Reports real, visible learning time to the backend once a minute. */
export function useHeartbeat(enabled: boolean) {
  const last = useRef(Date.now());
  useEffect(() => {
    if (!enabled) return;
    last.current = Date.now();
    const id = window.setInterval(() => {
      const now = Date.now();
      const seconds = Math.min(60, Math.round((now - last.current) / 1000));
      last.current = now;
      if (document.visibilityState === "visible" && seconds > 0) {
        api.post("/me/heartbeat", { seconds }).catch(() => undefined);
      }
    }, 60_000);
    const onVis = () => {
      if (document.visibilityState === "visible") last.current = Date.now();
    };
    document.addEventListener("visibilitychange", onVis);
    return () => {
      window.clearInterval(id);
      document.removeEventListener("visibilitychange", onVis);
    };
  }, [enabled]);
}
