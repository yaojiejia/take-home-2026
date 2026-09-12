import { useMemo, useState } from "react"
import { formatMoney } from "@/api"
import { Badge } from "@/components/ui/badge"
import type { Variant } from "@/types"

type Props = {
  variants: Variant[]
  onSelect: (variant: Variant | null) => void
}

type Selection = Record<string, string>

function matches(variant: Variant, selection: Selection): boolean {
  return Object.entries(selection).every(([name, value]) =>
    variant.options.some((o) => o.name === name && o.value === value),
  )
}

function optionAxes(variants: Variant[]): { name: string; values: string[] }[] {
  const axes: { name: string; values: string[] }[] = []
  for (const variant of variants) {
    for (const option of variant.options) {
      let axis = axes.find((a) => a.name === option.name)
      if (!axis) {
        axis = { name: option.name, values: [] }
        axes.push(axis)
      }
      if (!axis.values.includes(option.value)) {
        axis.values.push(option.value)
      }
    }
  }
  return axes
}

export function VariantPicker({ variants, onSelect }: Props) {
  const [selection, setSelection] = useState<Selection>({})
  const axes = useMemo(() => optionAxes(variants), [variants])
  const candidates = variants.filter((v) => matches(v, selection))
  const chosen = candidates.length === 1 ? candidates[0] : null

  function pick(name: string, value: string) {
    const next = { ...selection }
    if (next[name] === value) {
      delete next[name]
    } else {
      next[name] = value
    }
    setSelection(next)
    const remaining = variants.filter((v) => matches(v, next))
    onSelect(remaining.length === 1 ? remaining[0] : remaining.find((v) => v.image_urls.length > 0) ?? null)
  }

  if (axes.length === 0) {
    return <VariantList variants={variants} />
  }

  return (
    <div className="space-y-4">
      {axes.map((axis) => (
        <div key={axis.name} className="space-y-2">
          <div className="text-sm font-medium">
            {axis.name}
            {selection[axis.name] && <span className="ml-2 font-normal text-muted-foreground">{selection[axis.name]}</span>}
          </div>
          <div className="flex flex-wrap gap-2">
            {axis.values.map((value) => {
              const others = { ...selection }
              delete others[axis.name]
              const pool = variants.filter((v) => matches(v, others) && matches(v, { [axis.name]: value }))
              const offered = pool.length > 0
              const inStock = pool.some((v) => v.available !== false)
              const active = selection[axis.name] === value
              return (
                <button
                  key={value}
                  type="button"
                  disabled={!offered}
                  onClick={() => pick(axis.name, value)}
                  className={[
                    "rounded-md border px-3 py-1.5 text-sm transition-colors",
                    active ? "border-foreground bg-foreground text-background" : "hover:border-foreground",
                    !offered ? "cursor-not-allowed opacity-30" : "",
                    offered && !inStock ? "text-muted-foreground line-through" : "",
                  ].join(" ")}
                >
                  {value}
                </button>
              )
            })}
          </div>
        </div>
      ))}
      <div className="text-sm text-muted-foreground">
        {chosen ? (
          <span className="flex flex-wrap items-center gap-2">
            {chosen.sku && <span>SKU {chosen.sku}</span>}
            {chosen.price && <span>{formatMoney(chosen.price.price, chosen.price.currency)}</span>}
            <Availability available={chosen.available} />
          </span>
        ) : (
          <span>
            {candidates.length} of {variants.length} variants match
          </span>
        )}
      </div>
    </div>
  )
}

function VariantList({ variants }: { variants: Variant[] }) {
  if (variants.length === 1) {
    const only = variants[0]
    return (
      <div className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
        {only.sku && <span>SKU {only.sku}</span>}
        {only.price && <span>{formatMoney(only.price.price, only.price.currency)}</span>}
        <Availability available={only.available} />
      </div>
    )
  }
  return (
    <ul className="divide-y rounded-md border text-sm">
      {variants.map((variant, i) => (
        <li key={`${variant.sku ?? ""}-${i}`} className="flex items-center justify-between gap-3 px-3 py-2">
          <span className="truncate">{variant.title ?? variant.sku ?? `Variant ${i + 1}`}</span>
          <span className="flex shrink-0 items-center gap-2 text-muted-foreground">
            {variant.sku && variant.title && <span className="text-xs">{variant.sku}</span>}
            {variant.price && <span>{formatMoney(variant.price.price, variant.price.currency)}</span>}
            <Availability available={variant.available} />
          </span>
        </li>
      ))}
    </ul>
  )
}

function Availability({ available }: { available: boolean | null }) {
  if (available === null) {
    return null
  }
  return <Badge variant={available ? "secondary" : "outline"}>{available ? "In stock" : "Sold out"}</Badge>
}
