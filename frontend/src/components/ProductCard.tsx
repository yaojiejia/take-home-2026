import { Link } from "react-router-dom"
import { categoryLeaf } from "@/api"
import { PriceTag } from "@/components/PriceTag"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent } from "@/components/ui/card"
import type { CatalogItem } from "@/types"

export function ProductCard({ item }: { item: CatalogItem }) {
  const details = [
    item.color_count > 1 ? `${item.color_count} colours` : null,
    item.variant_count > 1 ? `${item.variant_count} variants` : null,
  ].filter(Boolean)
  return (
    <Link to={`/products/${encodeURIComponent(item.id)}`} className="group block">
      <Card className="h-full overflow-hidden py-0 transition-shadow group-hover:shadow-md">
        <div className="aspect-square bg-muted">
          {item.image_url ? (
            <img
              src={item.image_url}
              alt={item.name}
              className="h-full w-full object-contain transition-transform duration-300 group-hover:scale-[1.03]"
              loading="lazy"
            />
          ) : (
            <div className="flex h-full items-center justify-center text-sm text-muted-foreground">No image</div>
          )}
        </div>
        <CardContent className="space-y-2 px-4 pb-4 pt-3">
          <div className="text-xs uppercase tracking-wide text-muted-foreground">{item.brand}</div>
          <div className="line-clamp-2 text-sm font-medium leading-snug">{item.name}</div>
          <PriceTag price={item.price} />
          <div className="flex flex-wrap items-center gap-1.5 pt-1">
            <Badge variant="secondary">{categoryLeaf(item.category)}</Badge>
            {details.length > 0 && <span className="text-xs text-muted-foreground">{details.join(" · ")}</span>}
          </div>
        </CardContent>
      </Card>
    </Link>
  )
}
