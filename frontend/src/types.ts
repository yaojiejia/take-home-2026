export type Price = {
  price: number
  currency: string
  compare_at_price: number | null
}

export type VariantOption = {
  name: string
  value: string
}

export type Variant = {
  sku: string | null
  title: string | null
  options: VariantOption[]
  price: Price | null
  available: boolean | null
  image_urls: string[]
}

export type Product = {
  name: string
  price: Price
  description: string
  key_features: string[]
  image_urls: string[]
  video_url: string | null
  category: { name: string }
  brand: string
  colors: string[]
  variants: Variant[]
}

export type CatalogItem = {
  id: string
  name: string
  brand: string
  price: Price
  image_url: string | null
  category: string
  color_count: number
  variant_count: number
}

export type ProductRecord = {
  id: string
  source_file: string
  source_url: string | null
  model: string
  product: Product
}
