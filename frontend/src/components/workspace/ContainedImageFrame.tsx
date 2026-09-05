import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type CSSProperties,
  type ReactNode,
} from "react";

export type ContainRect = {
  left: number;
  top: number;
  width: number;
  height: number;
};

/** object-fit:contain geometry for an image inside a box. */
export function computeContainRect(
  boxW: number,
  boxH: number,
  imageW: number,
  imageH: number,
): ContainRect {
  if (boxW <= 0 || boxH <= 0 || imageW <= 0 || imageH <= 0) {
    return { left: 0, top: 0, width: Math.max(0, boxW), height: Math.max(0, boxH) };
  }
  const scale = Math.min(boxW / imageW, boxH / imageH);
  const width = imageW * scale;
  const height = imageH * scale;
  return {
    left: (boxW - width) / 2,
    top: (boxH - height) / 2,
    width,
    height,
  };
}

/**
 * Positions children over the letterboxed image content (not the full canvas),
 * so markers stay on lunar features for horizontal vs vertical strips.
 */
export function ContainedImageFrame({
  imageUrl,
  transform,
  onImageError,
  children,
  className = "",
}: {
  imageUrl: string;
  transform?: string;
  onImageError?: () => void;
  children?: ReactNode;
  className?: string;
}) {
  const boxRef = useRef<HTMLDivElement>(null);
  const imgRef = useRef<HTMLImageElement>(null);
  const [natural, setNatural] = useState<{ w: number; h: number } | null>(null);
  const [box, setBox] = useState({ w: 0, h: 0 });

  const measureBox = useCallback(() => {
    const el = boxRef.current;
    if (!el) return;
    setBox({ w: el.clientWidth, h: el.clientHeight });
  }, []);

  const applyNatural = useCallback((img: HTMLImageElement) => {
    if (img.naturalWidth > 0 && img.naturalHeight > 0) {
      setNatural({ w: img.naturalWidth, h: img.naturalHeight });
    }
  }, []);

  useEffect(() => {
    measureBox();
    const el = boxRef.current;
    if (!el || typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver(() => measureBox());
    ro.observe(el);
    return () => ro.disconnect();
  }, [measureBox, imageUrl]);

  useEffect(() => {
    setNatural(null);
  }, [imageUrl]);

  useEffect(() => {
    const img = imgRef.current;
    if (img?.complete) applyNatural(img);
  }, [imageUrl, applyNatural]);

  const rect =
    natural && box.w > 0 && box.h > 0
      ? computeContainRect(box.w, box.h, natural.w, natural.h)
      : null;

  // Until natural size is known, fill the canvas so markers still render (tests + first paint).
  const frameStyle: CSSProperties = rect
    ? {
        left: rect.left,
        top: rect.top,
        width: rect.width,
        height: rect.height,
      }
    : {
        left: 0,
        top: 0,
        right: 0,
        bottom: 0,
        width: "100%",
        height: "100%",
      };

  return (
    <div ref={boxRef} className={`contained-image-box ${className}`.trim()}>
      <div
        className="contained-zoom-layer"
        style={transform ? { transform } : undefined}
      >
        <div className="contained-image-frame" style={frameStyle}>
          <img
            ref={imgRef}
            className={`contained-image${rect ? " is-fitted" : " is-contain"}`}
            src={imageUrl}
            alt=""
            draggable={false}
            onLoad={(e) => applyNatural(e.currentTarget)}
            onError={() => onImageError?.()}
          />
          <div className="point-layer contained-point-layer">{children}</div>
        </div>
      </div>
    </div>
  );
}
