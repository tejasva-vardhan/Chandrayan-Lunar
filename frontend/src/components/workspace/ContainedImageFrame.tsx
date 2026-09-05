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
 *
 * When rotate90Cw is set, the preview is shown as a 90° CW rotation so a
 * landscape strip can match a portrait partner (or vice versa).
 */
export function ContainedImageFrame({
  imageUrl,
  transform,
  onImageError,
  children,
  className = "",
  rotate90Cw = false,
  onNaturalSize,
}: {
  imageUrl: string;
  transform?: string;
  onImageError?: () => void;
  children?: ReactNode;
  className?: string;
  rotate90Cw?: boolean;
  onNaturalSize?: (size: { w: number; h: number }) => void;
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

  const applyNatural = useCallback(
    (img: HTMLImageElement) => {
      if (img.naturalWidth > 0 && img.naturalHeight > 0) {
        const size = { w: img.naturalWidth, h: img.naturalHeight };
        setNatural(size);
        onNaturalSize?.(size);
      }
    },
    [onNaturalSize],
  );

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

  const displayW = natural ? (rotate90Cw ? natural.h : natural.w) : 0;
  const displayH = natural ? (rotate90Cw ? natural.w : natural.h) : 0;

  const rect =
    natural && box.w > 0 && box.h > 0 && displayW > 0 && displayH > 0
      ? computeContainRect(box.w, box.h, displayW, displayH)
      : null;

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

  const rotImgStyle: CSSProperties | undefined =
    rotate90Cw && rect
      ? {
          position: "absolute",
          left: "50%",
          top: "50%",
          width: rect.height,
          height: rect.width,
          transform: "translate(-50%, -50%) rotate(90deg)",
          objectFit: "fill",
        }
      : undefined;

  return (
    <div ref={boxRef} className={`contained-image-box ${className}`.trim()}>
      <div
        className="contained-zoom-layer"
        style={transform ? { transform } : undefined}
      >
        <div
          className={`contained-image-frame${rotate90Cw ? " is-rot90" : ""}`}
          style={frameStyle}
        >
          <img
            ref={imgRef}
            className={`contained-image${rect ? (rotate90Cw ? "" : " is-fitted") : " is-contain"}`}
            src={imageUrl}
            alt=""
            draggable={false}
            style={rotImgStyle}
            onLoad={(e) => applyNatural(e.currentTarget)}
            onError={() => onImageError?.()}
          />
          <div className="point-layer contained-point-layer">{children}</div>
        </div>
      </div>
    </div>
  );
}
