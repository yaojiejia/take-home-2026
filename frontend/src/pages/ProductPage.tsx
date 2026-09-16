import { useEffect, useState } from "react"
import { Link, useParams } from "react-router-dom"
import { ApiError, fetchProduct, peekProduct } from "@/api"
import { Gallery } from "@/components/Gallery"
import { PriceTag } from "@/components/PriceTag"
import { Skeleton } from "@/components/Skeleton"
import { VariantPicker } from "@/components/VariantPicker"
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
  const [record, setRecord] = useState<ProductRecord | null>(() => (id ? peekProduct(id) : null))
  const [error, setError] = useState<Error | null>(null)
  const [variant, setVariant] = useState<Variant | null>(null)

  useEffect(() => {
    if (!id) return
    let active = true
    setRecord(peekProduct(id))
    setError(null)
    setVariant(null)
    fetchProduct(id)
      .then((result) => active && setRecord(result))
      .catch((e: Error) => active && setError(e))
    return () => {
      active = false
    }
  }, [id])

  useEffect(() => {
    document.title = record ? `${record.product.name} · Channel3` : "Channel3"
    return () => {
      document.title = "Channel3"
    }
  }, [record])

  if (error) {
    const missing = error instanceof ApiError && error.status === 404
    return (
      <div className="space-y-4 pt-16 text-center">
        <p className="text-[16px] uppercase">{missing ? "We couldn't find that product" : "Something went wrong"}</p>
        <p className="text-[13px] text-neutral-500">
          {missing ? "It may have been removed or the link is incomplete." : error.message}
        </p>
        <Link to="/" viewTransition className="inline-block border border-black px-6 py-3 text-[13px] uppercase hover:bg-black hover:text-white">
          Back to all products
        </Link>
      </div>
    )
  }
  if (record === null) {
    return <ProductSkeleton />
  }

  const product = record.product
  const images = variant && variant.image_urls.length > 0 ? variant.image_urls : product.image_urls
  const price = variant?.price ?? product.price
  const crumbs = product.category.name.split(" > ")
  const paragraphs = product.description.split(/\n+/).filter((p) => p.trim())
  const variantGroups = groupByAxes(product.variants)
  const colourIsSelectable = product.variants.some((v) => v.options.some((o) => /colou?r/i.test(o.name)))

  return (
    <div>
      <nav className="flex flex-wrap gap-x-2 border-b border-black pb-2 text-[13px] uppercase text-neutral-500">
        <Link to="/" viewTransition className="text-black hover:underline">
          All products
        </Link>
        {crumbs.map((crumb, i) => (
          <span key={crumb} className="flex gap-x-2">
            <span>/</span>
            <Link
              to={`/?category=${encodeURIComponent(crumbs.slice(0, i + 1).join(" > "))}`}
              viewTransition
              className="hover:text-black"
            >
              {crumb}
            </Link>
          </span>
        ))}
      </nav>

      <div className="grid grid-cols-1 gap-8 pt-[3px] lg:grid-cols-[minmax(0,7fr)_minmax(0,5fr)] lg:gap-12">
        <Gallery images={images} alt={product.name} />

        <div className="lg:sticky lg:top-6 lg:max-h-[calc(100vh-3rem)] lg:self-start lg:overflow-y-auto">
          <div className="space-y-6 lg:max-w-md">
            <div className="space-y-2">
              <div className="text-[13px] uppercase text-neutral-500">{product.brand}</div>
              <h1 className="text-[20px] uppercase leading-snug tracking-wide">{product.name}</h1>
              <PriceTag price={price} size="lg" />
            </div>

            {product.colors.length > 0 && !colourIsSelectable && (
              <section className="space-y-2">
                <h2 className="text-[13px] uppercase">
                  Colour <span className="ml-2 text-neutral-500">{product.colors.length}</span>
                </h2>
                <ul className="flex flex-wrap gap-x-3 gap-y-1 text-[13px] uppercase text-neutral-500">
                  {product.colors.map((color) => (
                    <li key={color}>{color}</li>
                  ))}
                </ul>
              </section>
            )}

            {variantGroups.map((group, i) => (
              <section key={i} className="space-y-2">
                {group[0].options.length === 0 && (
                  <h2 className="text-[13px] uppercase">{group.length > 1 ? "Variants" : "Availability"}</h2>
                )}
                <VariantPicker variants={group} onSelect={setVariant} />
              </section>
            ))}

            <section className="space-y-3 border-t border-neutral-200 pt-5">
              {paragraphs.map((text, i) => (
                <p key={i} className="text-[13px] leading-relaxed">
                  {text}
                </p>
              ))}
            </section>

            {product.key_features.length > 0 && (
              <section className="space-y-2 border-t border-neutral-200 pt-5">
                <h2 className="text-[13px] uppercase">Details</h2>
                <ul className="space-y-1 text-[13px] leading-relaxed text-neutral-600">
                  {product.key_features.map((feature, i) => (
                    <li key={i}>{feature}</li>
                  ))}
                </ul>
              </section>
            )}

            {product.video_url && (
              <section className="space-y-2 border-t border-neutral-200 pt-5">
                <h2 className="text-[13px] uppercase">Video</h2>
                <video src={product.video_url} controls className="w-full bg-black" />
              </section>
            )}

            <footer className="border-t border-neutral-200 pt-5 text-[12px] uppercase text-neutral-500">
              {record.source_url && (
                <a href={record.source_url} target="_blank" rel="noreferrer" className="hover:text-black hover:underline">
                  View on {new URL(record.source_url).hostname.replace(/^www\./, "")}
                </a>
              )}
            </footer>
          </div>
        </div>
      </div>
    </div>
  )
}

function ProductSkeleton() {
  return (
    <div>
      <div className="border-b border-black pb-2">
        <Skeleton className="h-4 w-64" />
      </div>
      <div className="grid grid-cols-1 gap-8 pt-[3px] lg:grid-cols-[minmax(0,7fr)_minmax(0,5fr)] lg:gap-12">
        <Skeleton className="aspect-[3/4] w-full" />
        <div className="space-y-6 lg:max-w-md">
          <div className="space-y-3">
            <Skeleton className="h-3 w-20" />
            <Skeleton className="h-6 w-4/5" />
            <Skeleton className="h-4 w-24" />
          </div>
          <div className="space-y-3">
            <Skeleton className="h-3 w-12" />
            <div className="flex gap-[3px]">
              <Skeleton className="h-10 w-12" />
              <Skeleton className="h-10 w-12" />
              <Skeleton className="h-10 w-12" />
              <Skeleton className="h-10 w-12" />
            </div>
          </div>
          <div className="space-y-2 pt-5">
            <Skeleton className="h-3 w-full" />
            <Skeleton className="h-3 w-full" />
            <Skeleton className="h-3 w-2/3" />
          </div>
        </div>
      </div>
    </div>
  )
}
