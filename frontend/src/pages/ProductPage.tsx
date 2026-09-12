import { useEffect, useState } from "react"
import { Link, useParams } from "react-router-dom"
import { fetchProduct } from "@/api"
import { Gallery } from "@/components/Gallery"
import { PriceTag } from "@/components/PriceTag"
import { VariantPicker } from "@/components/VariantPicker"
import { Badge } from "@/components/ui/badge"
import { buttonVariants } from "@/components/ui/button"
import { Separator } from "@/components/ui/separator"
import type { ProductRecord, Variant } from "@/types"

function groupByAxes(variants: Variant[]): Variant[][] {
  const groups = new Map<string, Variant[]>()
  for (const variant of variants) {
    const key = variant.options.map((o) => o.name).join("|")
    const group = groups.get(key) ?? []
    group.push(variant)
    groups.set(key, group)
  }
  return [...groups.values()]
}

export function ProductPage() {
  const { id } = useParams()
  const [record, setRecord] = useState<ProductRecord | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [variant, setVariant] = useState<Variant | null>(null)

  useEffect(() => {
    if (!id) return
    setRecord(null)
    setVariant(null)
    fetchProduct(id).then(setRecord).catch((e: Error) => setError(e.message))
  }, [id])

  if (error) {
    return <p className="text-destructive">Could not load this product: {error}</p>
  }
  if (record === null) {
    return <p className="text-muted-foreground">Loading…</p>
  }

  const product = record.product
  const images = variant && variant.image_urls.length > 0 ? variant.image_urls : product.image_urls
  const price = variant?.price ?? product.price
  const crumbs = product.category.name.split(" > ")
  const paragraphs = product.description.split(/\n+/).filter((p) => p.trim())
  const variantGroups = groupByAxes(product.variants)

  return (
    <div className="space-y-8">
      <Link to="/" className={buttonVariants({ variant: "ghost", size: "sm", className: "-ml-2" })}>
        ← Back to catalog
      </Link>

      <div className="grid grid-cols-1 gap-10 lg:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)]">
        <Gallery images={images} alt={product.name} />

        <div className="space-y-6">
          <div className="space-y-2">
            <div className="text-sm uppercase tracking-wide text-muted-foreground">{product.brand}</div>
            <h1 className="text-3xl font-semibold leading-tight tracking-tight">{product.name}</h1>
            <PriceTag price={price} size="lg" />
          </div>

          <div className="flex flex-wrap gap-1.5">
            {crumbs.map((crumb, i) => (
              <Badge key={i} variant={i === crumbs.length - 1 ? "default" : "outline"}>
                {crumb}
              </Badge>
            ))}
          </div>

          {product.colors.length > 0 && (
            <section className="space-y-2">
              <h2 className="text-sm font-medium">Colours</h2>
              <div className="flex flex-wrap gap-2">
                {product.colors.map((color) => (
                  <Badge key={color} variant="secondary">
                    {color}
                  </Badge>
                ))}
              </div>
            </section>
          )}

          {variantGroups.map((group, i) => (
            <section key={i} className="space-y-2">
              {group[0].options.length === 0 && (
                <h2 className="text-sm font-medium">{group.length > 1 ? "Variants" : "Availability"}</h2>
              )}
              <VariantPicker variants={group} onSelect={setVariant} />
            </section>
          ))}

          {product.video_url && (
            <section className="space-y-2">
              <h2 className="text-sm font-medium">Video</h2>
              <video src={product.video_url} controls className="w-full rounded-lg bg-black" />
            </section>
          )}
        </div>
      </div>

      <Separator />

      <div className="grid grid-cols-1 gap-10 lg:grid-cols-2">
        <section className="space-y-3">
          <h2 className="text-lg font-semibold">Description</h2>
          {paragraphs.map((text, i) => (
            <p key={i} className="text-sm leading-relaxed text-muted-foreground">
              {text}
            </p>
          ))}
        </section>

        {product.key_features.length > 0 && (
          <section className="space-y-3">
            <h2 className="text-lg font-semibold">Details</h2>
            <ul className="list-disc space-y-1.5 pl-5 text-sm text-muted-foreground">
              {product.key_features.map((feature, i) => (
                <li key={i}>{feature}</li>
              ))}
            </ul>
          </section>
        )}
      </div>

      <Separator />

      <footer className="flex flex-wrap gap-x-6 gap-y-1 text-xs text-muted-foreground">
        {record.source_url && (
          <a href={record.source_url} target="_blank" rel="noreferrer" className="underline-offset-2 hover:underline">
            Original page
          </a>
        )}
        <span>Extracted from {record.source_file}</span>
        <span>Model {record.model}</span>
      </footer>
    </div>
  )
}
