import { useState } from 'react'

export default function TokenGate({ onSave }: { onSave: (t: string) => void }) {
  const [value, setValue] = useState('')
  return (
    <div className="fixed inset-0 grid place-items-center bg-zinc-950 p-6">
      <form
        className="w-full max-w-sm space-y-4"
        onSubmit={(e) => { e.preventDefault(); if (value.trim()) onSave(value.trim()) }}
      >
        <div className="flex items-center gap-3">
          <i className="fa-solid fa-lock text-xl text-violet-400" />
          <span className="font-sans text-lg font-bold text-zinc-100">Token de acesso</span>
        </div>
        <p className="text-zinc-500">Cole o <code>API_TOKEN</code> do seu <code>.env</code>. Ele fica só neste navegador.</p>
        <input
          type="password" autoFocus value={value} onChange={(e) => setValue(e.target.value)}
          className="w-full rounded-md border border-zinc-700 bg-zinc-900 px-3 py-2 text-zinc-100 outline-none focus:border-violet-500"
          placeholder="API_TOKEN"
        />
        <button className="rounded-md bg-violet-600 px-4 py-2 font-semibold text-white disabled:opacity-30" disabled={!value.trim()}>
          Entrar
        </button>
      </form>
    </div>
  )
}
