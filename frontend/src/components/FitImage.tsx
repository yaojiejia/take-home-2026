import { useState } from "react"
import type { SyntheticEvent } from "react"

type Props = {
  src: string
  alt: string
  className?: string
  loading?: "lazy" | "eager"
}

export function FitImage({ src, alt, className = "", loading }: Props) {
  const [fit, setFit] = useState<"cover" | "contain">("contain")

  function measure(event: SyntheticEvent<HTMLImageElement>) {
    const img = event.currentTarget
    setFit(img.naturalHeight > img.naturalWidth ? "cover" : "contain")
  }

  return (
    <img
      src={src}
      alt={alt}
      onLoad={measure}
      loading={loading}
      className={`h-full w-full ${fit === "cover" ? "object-cover" : "object-contain"} ${className}`}
    />
  )
}
