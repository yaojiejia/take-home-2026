import { useState } from "react"
import type { UIEvent } from "react"
import { FitImage } from "@/components/FitImage"

type Props = {
  images: string[]
  alt: string
}

export function Gallery({ images, alt }: Props) {
  const [current, setCurrent] = useState(0)

  function track(event: UIEvent<HTMLDivElement>) {
    const el = event.currentTarget
    setCurrent(Math.round(el.scrollLeft / el.clientWidth))
  }

  if (images.length === 0) {
    return (
      <div className="flex aspect-[3/4] items-center justify-center bg-neutral-100 text-[13px] uppercase text-neutral-400">
        No image
      </div>
    )
  }

  return (
    <div className="relative">
      <div
        onScroll={track}
        className="no-scrollbar flex snap-x snap-mandatory gap-[3px] overflow-x-auto lg:grid lg:grid-cols-2 lg:overflow-visible"
      >
        {images.map((url, i) => (
          <div
            key={`${url}-${i}`}
            className={`aspect-[3/4] w-full shrink-0 snap-start bg-white lg:w-auto ${i === 0 ? "lg:col-span-2" : ""}`}
          >
            <FitImage src={url} alt={i === 0 ? alt : ""} loading={i === 0 ? "eager" : "lazy"} />
          </div>
        ))}
      </div>
      {images.length > 1 && (
        <div className="pointer-events-none absolute right-3 bottom-3 bg-white/90 px-2 py-1 text-[12px] tabular-nums lg:hidden">
          {current + 1} / {images.length}
        </div>
      )}
    </div>
  )
}
