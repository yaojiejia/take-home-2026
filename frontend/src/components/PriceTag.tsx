import { formatMoney } from "@/api"
import type { Price } from "@/types"

type Props = {
  price: Price
  size?: "sm" | "lg"
}

export function PriceTag({ price, size = "sm" }: Props) {
  const onSale = price.compare_at_price !== null && price.compare_at_price > price.price
  const current = size === "lg" ? "text-2xl font-semibold" : "text-sm font-medium"
  const previous = size === "lg" ? "text-base" : "text-xs"
  return (
    <span className="flex items-baseline gap-2">
      <span className={current}>{formatMoney(price.price, price.currency)}</span>
      {onSale && (
        <span className={`${previous} text-muted-foreground line-through`}>
          {formatMoney(price.compare_at_price!, price.currency)}
        </span>
      )}
    </span>
  )
}
