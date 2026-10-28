import type { ReactNode } from 'react'

export const pct = (x: number | null | undefined) => (x == null ? '–' : `${Math.round(x * 100)}%`)

export function Skeleton({ className = '' }: { className?: string }) {
  return <div className={`animate-pulse rounded-lg bg-gray-500/20 ${className}`} aria-busy="true" />
}

export function Panel({ title, children, className = '' }: { title: string; children: ReactNode; className?: string }) {
  return (
    <section className={`rounded-lg border border-zinc-800 bg-zinc-900/60 p-4 ${className}`}>
      <div className="mb-2 text-[11px] uppercase tracking-wider text-zinc-500">{title}</div>
      {children}
    </section>
  )
}

export function ErrorBox({ error, retry }: { error: Error; retry?: () => void }) {
  return (
    <div className="m-4 rounded-lg border border-rose-900 bg-rose-950/40 p-4 text-rose-300">
      <i className="fa-solid fa-triangle-exclamation mr-2" />{error.message}
      {retry && <button onClick={retry} className="ml-3 underline">tentar de novo</button>}
    </div>
  )
}
