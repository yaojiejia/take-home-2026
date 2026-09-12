import { FitImage } from "@/components/FitImage"

type Props = {
  images: string[]
  alt: string
}

export function Gallery({ images, alt }: Props) {
  if (images.length === 0) {
    return <div className="flex aspect-[3/4] items-center justify-center bg-white text-[11px] uppercase text-neutral-400">No image</div>
  }
  const [first, ...rest] = images
  return (
    <div className="space-y-[3px]">
      <div className="aspect-[3/4] bg-white">
        <FitImage src={first} alt={alt} />
      </div>
      {rest.length > 0 && (
        <div className="grid grid-cols-2 gap-[3px]">
          {rest.map((url, i) => (
            <div key={`${url}-${i}`} className="aspect-[3/4] bg-white">
              <FitImage src={url} alt="" loading="lazy" />
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
