import { useEffect, useState } from "react";

import { EditorApiError, editorClient } from "../api/editorClient";
import type { EditorContext, User } from "../types";

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

  useEffect(() => {
    if (!projectId) {
      return;
    }

    let cancelled = false;
    const activeProjectId = projectId;

    async function load() {
      setState("AUTH_CHECKING");
      setErrorMessage(null);
      try {
        const currentUser = await editorClient.getMe();
        if (cancelled) return;
        setUser(currentUser);
      } catch (error) {
        if (cancelled) return;
        if (error instanceof EditorApiError && error.status === 401) {
          setState("UNAUTHENTICATED");
          return;
        }
        setState("UNAUTHENTICATED");
        setErrorMessage(error instanceof Error ? error.message : "Authentication failed.");
        return;
      }

      setState("PROJECT_LOADING");
      try {
        const loadedContext = await editorClient.getEditorContext(activeProjectId);
        if (cancelled) return;
        setContext(loadedContext);
        setState(loadedContext.modelAsset?.status === "ready" ? "EDITOR_READY" : "MODEL_PROCESSING");
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
  }, [projectId]);

  return { state, user, context, errorMessage };
}
