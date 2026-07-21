import type { ReactNode } from 'react';

export function DataTable({ headers, children, label }: { headers: string[]; children: ReactNode; label: string }) {
  return (
    <div className="table-wrap">
      <table aria-label={label}>
        <thead><tr>{headers.map((header) => <th key={header}>{header}</th>)}</tr></thead>
        <tbody>{children}</tbody>
      </table>
    </div>
  );
}
