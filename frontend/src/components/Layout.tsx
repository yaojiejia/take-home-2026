import { Link, Outlet, ScrollRestoration } from "react-router-dom"

export function Layout() {
  return (
    <div className="min-h-screen bg-white text-black">
      <ScrollRestoration />
      <header className="px-4 pt-5 pb-3 md:px-8">
        <div className="flex items-start justify-between">
          <Link to="/" viewTransition className="text-[40px] font-black leading-none tracking-[-0.06em] md:text-[56px]">
            CHANNEL3
          </Link>
          <nav className="pt-2 text-[13px] uppercase tracking-wide">
            <Link to="/" viewTransition className="hover:underline">
              All products
            </Link>
          </nav>
        </div>
      </header>
      <main className="px-4 pb-16 md:px-8">
        <Outlet />
      </main>
    </div>
  )
}
