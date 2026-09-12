import { formatMoney } from "@/api"
import type { Price } from "@/types"

type Props = {
  price: Price
  size?: "sm" | "lg"
}

export function PriceTag({ price, size = "sm" }: Props) {
  const onSale = price.compare_at_price !== null && price.compare_at_price > price.price
  const text = size === "lg" ? "text-[13px]" : "text-[11px]"
  return (
    <span className={`flex flex-wrap items-baseline gap-x-2 ${text}`}>
      {onSale && <span className="line-through">{formatMoney(price.compare_at_price!, price.currency)}</span>}
      <span className={onSale ? "text-red-600" : ""}>{formatMoney(price.price, price.currency)}</span>
      {onSale && (
        <span className="text-red-600">-{Math.round((1 - price.price / price.compare_at_price!) * 100)}%</span>
      )}
    </span>
  )
}
