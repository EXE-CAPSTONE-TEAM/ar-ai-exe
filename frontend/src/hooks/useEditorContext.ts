import { useCallback, useEffect, useState } from "react";

import { api } from "../api/client";
import { EditorApiError, editorClient } from "../api/editorClient";
import type { EditorContext, User } from "../types";

// Matches DEMO_PROJECT_ID in backend/app/scripts/seed_desktop_demo_project.py.
export const DESKTOP_DEMO_PROJECT_ID = "proj_desktop_demo";

export type EditorContextState =
  | "idle"
  | "AUTH_CHECKING"
  | "UNAUTHENTICATED"
  | "PROJECT_LOADING"
  | "PROJECT_NOT_FOUND"
  | "MODEL_PROCESSING"
  | "EDITOR_READY";

export function useEditorContext(projectId: string | null) {
  const [state, setState] = useState<EditorContextState>(projectId ? "AUTH_CHECKING" : "idle");
  const [user, setUser] = useState<User | null>(null);
  const [context, setContext] = useState<EditorContext | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [reloadToken, setReloadToken] = useState(0);

  const reload = useCallback(() => {
    setReloadToken((current) => current + 1);
  }, []);

  useEffect(() => {
    if (!projectId) {
      return;
    }

    let cancelled = false;
    const activeProjectId = projectId;

    async function load() {
      setState("AUTH_CHECKING");
      setErrorMessage(null);
      let currentUser: User | null = null;
      try {
        currentUser = await editorClient.getMe();
      } catch (error) {
        // The desktop demo project lives in the local sidecar and belongs to its demo account.
        if (activeProjectId === DESKTOP_DEMO_PROJECT_ID) {
          currentUser = await api.demoLogin().catch(() => null);
        }
        if (!currentUser) {
          if (cancelled) return;
          setState("UNAUTHENTICATED");
          if (!(error instanceof EditorApiError && error.status === 401)) {
            setErrorMessage(error instanceof Error ? error.message : "Authentication failed.");
          }
          return;
        }
      }
      if (cancelled) return;
      setUser(currentUser);

      setState("PROJECT_LOADING");
      try {
        const loadedContext = await editorClient.getEditorContext(activeProjectId);
        if (cancelled) return;
        setContext(loadedContext);
        const isReadyForEditor =
          loadedContext.modelStatus === "raw" ||
          loadedContext.modelAsset?.status === "ready" ||
          loadedContext.modelAsset?.status === "raw";
        setState(isReadyForEditor ? "EDITOR_READY" : "MODEL_PROCESSING");
      } catch (error) {
        if (cancelled) return;
        if (error instanceof EditorApiError && error.code === "PROJECT_NOT_FOUND") {
          setState("PROJECT_NOT_FOUND");
        } else {
          setState("PROJECT_LOADING");
        }
        setErrorMessage(error instanceof Error ? error.message : "Project load failed.");
      }
    }

    void load();

    return () => {
      cancelled = true;
    };
  }, [projectId, reloadToken]);

  return { state, user, context, errorMessage, reload };
}
