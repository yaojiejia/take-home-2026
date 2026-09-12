import { useEffect, useState } from "react"

type Props = {
  images: string[]
  alt: string
}

export function Gallery({ images, alt }: Props) {
  const [index, setIndex] = useState(0)

  useEffect(() => {
    setIndex(0)
  }, [images])

  if (images.length === 0) {
    return <div className="flex aspect-square items-center justify-center rounded-lg bg-muted text-muted-foreground">No image</div>
  }
  const current = images[Math.min(index, images.length - 1)]
  return (
    <div className="space-y-3">
      <div className="aspect-square overflow-hidden rounded-lg bg-muted">
        <img src={current} alt={alt} className="h-full w-full object-contain" />
      </div>
      {images.length > 1 && (
        <div className="flex gap-2 overflow-x-auto pb-1">
          {images.map((url, i) => (
            <button
              key={url}
              type="button"
              onClick={() => setIndex(i)}
              className={`h-16 w-16 shrink-0 overflow-hidden rounded-md border bg-muted ${i === index ? "border-foreground" : "border-transparent hover:border-muted-foreground"}`}
              aria-label={`Image ${i + 1}`}
            >
              <img src={url} alt="" className="h-full w-full object-contain" />
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
