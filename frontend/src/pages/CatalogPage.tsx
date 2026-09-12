import { useEffect, useState } from "react"
import { useSearchParams } from "react-router-dom"
import { fetchCatalog } from "@/api"
import { CategoryMenu, inCategory } from "@/components/CategoryMenu"
import { ProductCard } from "@/components/ProductCard"
import type { CatalogItem } from "@/types"

const COLUMN_CHOICES = [2, 3, 4] as const
const COLUMN_CLASSES: Record<number, string> = {
  2: "grid-cols-2",
  3: "grid-cols-2 md:grid-cols-3",
  4: "grid-cols-2 md:grid-cols-4",
}

function storedColumns(): number {
  try {
    const value = Number(localStorage.getItem("catalog-columns"))
    return COLUMN_CHOICES.includes(value as (typeof COLUMN_CHOICES)[number]) ? value : 3
  } catch {
    return 3
  }
}

export function CatalogPage() {
  const [items, setItems] = useState<CatalogItem[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [columns, setColumns] = useState(storedColumns)
  const [params, setParams] = useSearchParams()
  const category = params.get("category") ?? ""
  const brand = params.get("brand") ?? ""

  useEffect(() => {
    fetchCatalog().then(setItems).catch((e: Error) => setError(e.message))
  }, [])

  function setFilter(key: "category" | "brand", value: string) {
    const next = new URLSearchParams(params)
    if (value) {
      next.set(key, value)
    } else {
      next.delete(key)
    }
    if (key === "category") next.delete("brand")
    setParams(next)
  }

  function chooseColumns(value: number) {
    setColumns(value)
    try {
      localStorage.setItem("catalog-columns", String(value))
    } catch {
      return
    }
  }

  if (error) {
    return <p className="text-[11px] uppercase text-red-600">Could not load the catalog: {error}</p>
  }
  if (items === null) {
    return <p className="text-[11px] uppercase text-neutral-500">Loading</p>
  }

  const visible = items.filter((item) => inCategory(item, category) && (!brand || item.brand === brand))
  const heading = category ? category.split(" > ").pop() : "All products"

  return (
    <div className="grid grid-cols-1 gap-8 lg:grid-cols-[200px_minmax(0,1fr)] lg:gap-12">
      <aside className="lg:sticky lg:top-6 lg:flex lg:max-h-[calc(100vh-3rem)] lg:flex-col lg:justify-between lg:self-start lg:overflow-y-auto">
        <CategoryMenu
          items={items}
          category={category}
          brand={brand}
          onCategory={(path) => setFilter("category", path)}
          onBrand={(name) => setFilter("brand", name)}
        />
        <div className="hidden pt-10 text-[11px] uppercase lg:block">
          <div className="text-neutral-500">View</div>
          <div className="flex gap-4 pt-2">
            {COLUMN_CHOICES.map((value) => (
              <button
                key={value}
                type="button"
                onClick={() => chooseColumns(value)}
                className={value === columns ? "font-semibold" : "text-neutral-500 hover:text-black"}
                aria-label={`${value} columns`}
              >
                {value}
              </button>
            ))}
          </div>
        </div>
      </aside>

      <section>
        <div className="flex items-end justify-between border-b border-black pb-2 text-[11px] uppercase">
          <div className="flex items-baseline gap-3">
            <span className="font-semibold">{heading}</span>
            {brand && <span>{brand}</span>}
            <span className="text-neutral-500">{visible.length}</span>
          </div>
          <div className="flex items-center gap-3 lg:hidden">
            <span className="text-neutral-500">View</span>
            {COLUMN_CHOICES.map((value) => (
              <button
                key={value}
                type="button"
                onClick={() => chooseColumns(value)}
                className={value === columns ? "underline underline-offset-4" : "text-neutral-500 hover:text-black"}
              >
                {value}
              </button>
            ))}
          </div>
        </div>
        {visible.length === 0 ? (
          <p className="pt-6 text-[11px] uppercase text-neutral-500">No products here</p>
        ) : (
          <div className={`grid gap-x-[3px] gap-y-6 pt-[3px] ${COLUMN_CLASSES[columns]}`}>
            {visible.map((item) => (
              <ProductCard key={item.id} item={item} />
            ))}
          </div>
        )}
      </section>
    </div>
  )
}
