import { NavLink, Outlet } from 'react-router-dom'

const link = ({ isActive }: { isActive: boolean }) =>
  `grid h-11 w-11 place-items-center rounded-lg ${isActive ? 'bg-violet-600 text-white' : 'text-zinc-400 hover:bg-zinc-800'}`

export default function Layout({ onLogout }: { onLogout: () => void }) {
  return (
    <div className="min-h-screen bg-zinc-950 pb-[calc(3.5rem+env(safe-area-inset-bottom))] md:flex md:pb-0">
      <aside className="fixed inset-x-0 bottom-0 z-40 flex h-[calc(3.5rem+env(safe-area-inset-bottom))] items-center justify-around border-t border-zinc-800 bg-zinc-950 pb-[env(safe-area-inset-bottom)] md:sticky md:top-0 md:h-screen md:w-14 md:flex-col md:justify-start md:gap-2 md:border-r md:border-t-0 md:py-3 md:pb-3">
        <i className="fa-solid fa-graduation-cap hidden text-lg text-violet-400 md:mb-3 md:block" />
        <NavLink to="/" end className={link} title="Estudar"><i className="fa-solid fa-terminal" /></NavLink>
        <NavLink to="/dashboard" className={link} title="Dashboard"><i className="fa-solid fa-chart-simple" /></NavLink>
        <button onClick={onLogout} title="Sair" className="grid h-11 w-11 place-items-center rounded-lg text-zinc-500 hover:bg-zinc-800 md:mt-auto">
          <i className="fa-solid fa-right-from-bracket" />
        </button>
      </aside>
      <main className="min-w-0 flex-1"><Outlet /></main>
    </div>
  )
}
