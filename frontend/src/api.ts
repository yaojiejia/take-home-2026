import type { CatalogItem, ProductRecord } from "@/types"

async function getJson<T>(url: string): Promise<T> {
  const response = await fetch(url)
  if (!response.ok) {
    throw new Error(`${response.status} ${response.statusText}`)
  }
  return response.json()
}

export function fetchCatalog(): Promise<CatalogItem[]> {
  return getJson("/api/products")
}

export function fetchProduct(id: string): Promise<ProductRecord> {
  return getJson(`/api/products/${encodeURIComponent(id)}`)
}

export function formatMoney(amount: number, currency: string): string {
  try {
    return new Intl.NumberFormat(undefined, { style: "currency", currency }).format(amount)
  } catch {
    return `${amount.toFixed(2)} ${currency}`
  }
}

export function categoryLeaf(path: string): string {
  const parts = path.split(" > ")
  return parts[parts.length - 1]
}
