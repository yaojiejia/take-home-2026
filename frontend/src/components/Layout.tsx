import { Link, Outlet } from "react-router-dom"

export function Layout() {
  return (
    <div className="min-h-screen bg-white text-black">
      <header className="px-4 pt-5 pb-3 md:px-8">
        <div className="flex items-start justify-between">
          <Link to="/" className="text-[40px] font-black leading-none tracking-[-0.06em] md:text-[56px]">
            CATALOG
          </Link>
          <nav className="flex gap-6 pt-2 text-[11px] uppercase tracking-wide">
            <Link to="/" className="hover:underline">
              All products
            </Link>
            <a href="/api/products" className="hover:underline" target="_blank" rel="noreferrer">
              API
            </a>
          </nav>
        </div>
      </header>
      <main className="px-4 pb-16 md:px-8">
        <Outlet />
      </main>
    </div>
  )
}
