import { Link } from "react-router-dom"
import { FitImage } from "@/components/FitImage"
import { PriceTag } from "@/components/PriceTag"
import type { CatalogItem } from "@/types"

export function ProductCard({ item }: { item: CatalogItem }) {
  return (
    <Link to={`/products/${encodeURIComponent(item.id)}`} className="group block">
      <div className="relative aspect-[3/4] overflow-hidden bg-white">
        {item.image_url ? (
          <>
            <FitImage src={item.image_url} alt={item.name} loading="lazy" />
            {item.hover_image_url && (
              <div className="absolute inset-0 bg-white opacity-0 transition-opacity duration-300 group-hover:opacity-100">
                <FitImage src={item.hover_image_url} alt="" loading="lazy" />
              </div>
            )}
          </>
        ) : (
          <div className="flex h-full items-center justify-center text-[11px] uppercase text-neutral-400">No image</div>
        )}
      </div>
      <div className="space-y-1 px-1 pt-2 pb-4">
        <div className="flex items-start justify-between gap-3">
          <div className="line-clamp-2 text-[11px] uppercase leading-snug">{item.name}</div>
          {item.color_count > 1 && <span className="shrink-0 text-[10px] text-neutral-500">+{item.color_count - 1}</span>}
        </div>
        <PriceTag price={item.price} />
      </div>
    </Link>
  )
}
