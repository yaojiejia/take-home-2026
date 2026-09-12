import type { CatalogItem, ProductRecord } from "@/types"

export class ApiError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

const pending = new Map<string, Promise<unknown>>()
const resolved = new Map<string, unknown>()

function getJson<T>(url: string): Promise<T> {
  const cached = pending.get(url)
  if (cached) {
    return cached as Promise<T>
  }
  const request = fetch(url).then(async (response) => {
    if (!response.ok) {
      throw new ApiError(response.status, response.statusText)
    }
    const data = (await response.json()) as T
    resolved.set(url, data)
    return data
  })
  request.catch(() => pending.delete(url))
  pending.set(url, request)
  return request
}

function peek<T>(url: string): T | null {
  return (resolved.get(url) as T | undefined) ?? null
}

export function fetchCatalog(): Promise<CatalogItem[]> {
  return getJson("/api/products")
}

export function peekCatalog(): CatalogItem[] | null {
  return peek("/api/products")
}

export function fetchProduct(id: string): Promise<ProductRecord> {
  return getJson(`/api/products/${encodeURIComponent(id)}`)
}

export function peekProduct(id: string): ProductRecord | null {
  return peek(`/api/products/${encodeURIComponent(id)}`)
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
