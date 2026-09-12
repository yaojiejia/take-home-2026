import { useMemo, useState } from "react"
import { formatMoney } from "@/api"
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
    <div className="space-y-5">
      {axes.map((axis) => (
        <div key={axis.name} className="space-y-2">
          <div className="text-[11px] uppercase">
            {axis.name}
            {selection[axis.name] && <span className="ml-2 text-neutral-500">{selection[axis.name]}</span>}
          </div>
          <div className="flex flex-wrap gap-[3px]">
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
                    "min-w-10 border px-3 py-2 text-[11px] uppercase transition-colors",
                    active ? "border-black bg-black text-white" : "border-neutral-300 hover:border-black",
                    !offered ? "cursor-not-allowed text-neutral-300" : "",
                    offered && !inStock ? "text-neutral-400 line-through" : "",
                  ].join(" ")}
                >
                  {value}
                </button>
              )
            })}
          </div>
        </div>
      ))}
      <div className="text-[11px] uppercase text-neutral-500">
        {chosen ? (
          <span className="flex flex-wrap items-center gap-x-3">
            {chosen.sku && <span>Ref. {chosen.sku}</span>}
            {chosen.price && <span className="text-black">{formatMoney(chosen.price.price, chosen.price.currency)}</span>}
            <Availability available={chosen.available} />
          </span>
        ) : (
          <span>
            {candidates.length} of {variants.length} combinations
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
      <div className="flex flex-wrap items-center gap-x-3 text-[11px] uppercase text-neutral-500">
        {only.sku && <span>Ref. {only.sku}</span>}
        {only.price && <span className="text-black">{formatMoney(only.price.price, only.price.currency)}</span>}
        <Availability available={only.available} />
      </div>
    )
  }
  return (
    <ul className="divide-y divide-neutral-200 border-y border-neutral-200 text-[11px] uppercase">
      {variants.map((variant, i) => (
        <li key={`${variant.sku ?? ""}-${i}`} className="flex items-center justify-between gap-3 py-2">
          <span className="truncate">{variant.title ?? variant.sku ?? `Variant ${i + 1}`}</span>
          <span className="flex shrink-0 items-center gap-3 text-neutral-500">
            {variant.sku && variant.title && <span>Ref. {variant.sku}</span>}
            {variant.price && <span className="text-black">{formatMoney(variant.price.price, variant.price.currency)}</span>}
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
  return <span className={available ? "text-black" : "text-neutral-400"}>{available ? "In stock" : "Sold out"}</span>
}
