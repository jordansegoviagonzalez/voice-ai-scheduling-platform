import { AlertTriangle, Inbox, LoaderCircle } from 'lucide-react';

export function LoadingState({ label = 'Loading data' }: { label?: string }) {
  return <div className="state-panel"><LoaderCircle className="spin" /><p>{label}…</p></div>;
}

export function EmptyState({ title, detail }: { title: string; detail: string }) {
  return <div className="state-panel"><Inbox /><h3>{title}</h3><p>{detail}</p></div>;
}

export function ErrorState({ message }: { message: string }) {
  return <div className="state-panel state-error"><AlertTriangle /><h3>Unable to load this view</h3><p>{message}</p></div>;
}
