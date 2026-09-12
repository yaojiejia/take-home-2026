import type { CatalogItem } from "@/types"

const SEPARATOR = " > "

type Props = {
  items: CatalogItem[]
  category: string
  brand: string
  onCategory: (path: string) => void
  onBrand: (brand: string) => void
}

export function childrenOf(items: CatalogItem[], node: string): { path: string; label: string; count: number }[] {
  const prefix = node ? node + SEPARATOR : ""
  const counts = new Map<string, number>()
  for (const item of items) {
    if (!item.category.startsWith(prefix)) continue
    const rest = item.category.slice(prefix.length)
    if (!rest) continue
    const label = rest.split(SEPARATOR)[0]
    counts.set(label, (counts.get(label) ?? 0) + 1)
  }
  return [...counts.entries()]
    .sort((a, b) => a[0].localeCompare(b[0]))
    .map(([label, count]) => ({ path: prefix + label, label, count }))
}

export function inCategory(item: CatalogItem, node: string): boolean {
  return !node || item.category === node || item.category.startsWith(node + SEPARATOR)
}

function parentOf(node: string): string {
  return node.includes(SEPARATOR) ? node.slice(0, node.lastIndexOf(SEPARATOR)) : ""
}

export function CategoryMenu({ items, category, brand, onCategory, onBrand }: Props) {
  const own = childrenOf(items, category)
  const base = own.length === 0 && category ? parentOf(category) : category
  const entries = childrenOf(items, base)
  const ancestors = base ? base.split(SEPARATOR) : []
  const total = items.filter((item) => inCategory(item, base)).length
  const brands = new Map<string, number>()
  for (const item of items) {
    if (inCategory(item, category)) brands.set(item.brand, (brands.get(item.brand) ?? 0) + 1)
  }

  return (
    <div className="space-y-8 text-[11px] uppercase">
      {ancestors.length > 0 && (
        <nav className="flex flex-wrap gap-x-2 text-neutral-500">
          <button type="button" onClick={() => onCategory("")} className="uppercase hover:text-black">
            All
          </button>
          {ancestors.map((label, i) => {
            const path = ancestors.slice(0, i + 1).join(SEPARATOR)
            return (
              <span key={path} className="flex gap-x-2">
                <span>/</span>
                <button type="button" onClick={() => onCategory(path)} className="uppercase hover:text-black">
                  {label}
                </button>
              </span>
            )
          })}
        </nav>
      )}

      <ol className="space-y-3">
        <MenuRow index={1} label="View all" count={total} active={category === base} onClick={() => onCategory(base)} />
        {entries.map((entry, i) => (
          <MenuRow
            key={entry.path}
            index={i + 2}
            label={entry.label}
            count={entry.count}
            active={category === entry.path}
            onClick={() => onCategory(entry.path)}
          />
        ))}
      </ol>

      {brands.size > 1 && (
        <div className="space-y-3">
          <div className="text-neutral-500">Filters</div>
          <ul className="space-y-2">
            {[...brands.entries()].sort().map(([name, count]) => (
              <li key={name}>
                <button
                  type="button"
                  onClick={() => onBrand(brand === name ? "" : name)}
                  className={`uppercase ${brand === name ? "font-semibold" : "hover:underline"}`}
                >
                  {name} <span className="text-neutral-400">{count}</span>
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}

function MenuRow({ index, label, count, active, onClick }: { index: number; label: string; count: number; active: boolean; onClick: () => void }) {
  return (
    <li>
      <button type="button" onClick={onClick} className={`flex items-start gap-2 text-left uppercase ${active ? "font-semibold" : "hover:underline"}`}>
        <span className="shrink-0 tabular-nums tracking-wider">|{String(index).padStart(2, "0")}|</span>
        <span>
          {label} <span className="font-normal text-neutral-400">{count}</span>
        </span>
      </button>
    </li>
  )
}
