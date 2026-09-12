import { useEffect, useState } from "react"
import { fetchCatalog } from "@/api"
import { ProductCard } from "@/components/ProductCard"
import type { CatalogItem } from "@/types"

export function CatalogPage() {
  const [items, setItems] = useState<CatalogItem[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetchCatalog().then(setItems).catch((e: Error) => setError(e.message))
  }, [])

  if (error) {
    return <p className="text-destructive">Could not load the catalog: {error}</p>
  }
  if (items === null) {
    return <p className="text-muted-foreground">Loading…</p>
  }
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">All products</h1>
        <p className="text-sm text-muted-foreground">{items.length} products</p>
      </div>
      <div className="grid grid-cols-2 gap-5 md:grid-cols-3 lg:grid-cols-4">
        {items.map((item) => (
          <ProductCard key={item.id} item={item} />
        ))}
      </div>
    </div>
  )
}
