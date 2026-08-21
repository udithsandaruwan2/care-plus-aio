import { create } from 'zustand';
import type { OutboxItem } from './idbOutbox';
import { outboxList } from './idbOutbox';

type OutboxState = {
  items: OutboxItem[];
  hydrated: boolean;
  setItems: (items: OutboxItem[]) => void;
  refresh: () => Promise<void>;
};

export const useOutboxStore = create<OutboxState>((set) => ({
  items: [],
  hydrated: false,
  setItems: (items) => set({ items, hydrated: true }),
  refresh: async () => {
    const items = await outboxList();
    set({ items, hydrated: true });
  },
}));

export function pendingOutboxCount(items: OutboxItem[]): number {
  return items.filter((i) => i.status === 'pending' || i.status === 'sending').length;
}
