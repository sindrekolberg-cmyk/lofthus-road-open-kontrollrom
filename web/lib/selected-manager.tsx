"use client";

import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

const STORAGE_KEY = "lro-selected-manager";

type Ctx = {
  entryId: number;
  setEntryId: (id: number) => void;
};

const SelectedManagerContext = createContext<Ctx>({
  entryId: 0,
  setEntryId: () => {},
});

export function SelectedManagerProvider({ children }: { children: ReactNode }) {
  const [entryId, setEntryIdState] = useState(0);

  useEffect(() => {
    try {
      const raw = window.localStorage.getItem(STORAGE_KEY);
      const parsed = raw ? Number.parseInt(raw, 10) : 0;
      if (parsed) setEntryIdState(parsed);
    } catch {
      /* ignore */
    }
  }, []);

  const setEntryId = (id: number) => {
    setEntryIdState(id);
    try {
      if (id) window.localStorage.setItem(STORAGE_KEY, String(id));
      else window.localStorage.removeItem(STORAGE_KEY);
    } catch {
      /* ignore */
    }
  };

  const value = useMemo(() => ({ entryId, setEntryId }), [entryId]);
  return (
    <SelectedManagerContext.Provider value={value}>
      {children}
    </SelectedManagerContext.Provider>
  );
}

export function useSelectedManager() {
  return useContext(SelectedManagerContext);
}
