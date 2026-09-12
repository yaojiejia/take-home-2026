import { useEffect, useState } from "react"
import { fetchCatalog } from "@/api"
import { ProductCard } from "@/components/ProductCard"
import type { CatalogItem } from "@/types"

const COLUMN_CHOICES = [2, 4, 6] as const
const COLUMN_CLASSES: Record<number, string> = {
  2: "grid-cols-2",
  4: "grid-cols-2 md:grid-cols-4",
  6: "grid-cols-3 md:grid-cols-6",
}

function storedColumns(): number {
  try {
    const value = Number(localStorage.getItem("catalog-columns"))
    return COLUMN_CHOICES.includes(value as (typeof COLUMN_CHOICES)[number]) ? value : 4
  } catch {
    return 4
  }
}

export function CatalogPage() {
  const [items, setItems] = useState<CatalogItem[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [columns, setColumns] = useState(storedColumns)

  useEffect(() => {
    fetchCatalog().then(setItems).catch((e: Error) => setError(e.message))
  }, [])

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
  return (
    <div>
      <div className="flex items-end justify-between border-b border-black pb-2 text-[11px] uppercase">
        <div className="flex items-baseline gap-3">
          <span className="font-semibold">All products</span>
          <span className="text-neutral-500">{items.length}</span>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-neutral-500">View</span>
          {COLUMN_CHOICES.map((value) => (
            <button
              key={value}
              type="button"
              onClick={() => chooseColumns(value)}
              className={value === columns ? "underline underline-offset-4" : "text-neutral-500 hover:text-black"}
              aria-label={`${value} columns`}
            >
              {value}
            </button>
          ))}
        </div>
      </div>
      <div className={`grid gap-x-[3px] gap-y-6 pt-[3px] ${COLUMN_CLASSES[columns]}`}>
        {items.map((item) => (
          <ProductCard key={item.id} item={item} />
        ))}
      </div>
    </div>
  )
}
