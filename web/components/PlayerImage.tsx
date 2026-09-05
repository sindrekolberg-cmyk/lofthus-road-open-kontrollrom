"use client";

import Image from "next/image";
import { useState } from "react";

export type PlayerImageVariant = "hero" | "card" | "squad" | "avatar";

type PlayerImageProps = {
  src?: string | null;
  alt: string;
  variant?: PlayerImageVariant;
  sizes?: string;
  priority?: boolean;
  objectPosition?: string;
  className?: string;
  fill?: boolean;
};

const VARIANT_SIZES: Record<PlayerImageVariant, string> = {
  hero: "(min-width: 1024px) 66vw, 100vw",
  card: "(min-width: 768px) 25vw, 50vw",
  squad: "72px",
  avatar: "48px",
};

export function playerImageSrc(url?: string | null) {
  return (url || "").trim();
}

export function PlayerImage({
  src,
  alt,
  variant = "card",
  sizes,
  priority = false,
  objectPosition = "center 18%",
  className = "",
  fill = true,
}: PlayerImageProps) {
  const [failed, setFailed] = useState(false);
  const resolved = playerImageSrc(src);
  const unusable = failed || !resolved;

  if (unusable) {
    return (
      <div
        className={`flex items-end bg-[#1c1c1c] ${fill ? "absolute inset-0" : "relative h-full w-full"} ${className}`}
        role="img"
        aria-label={alt}
      >
        <div className="pointer-events-none absolute inset-0 opacity-40 [background-image:repeating-linear-gradient(90deg,transparent,transparent_31px,#2a2a2a_31px,#2a2a2a_32px)]" />
        <p className="relative p-3 font-serif text-lg leading-none text-white/50 sm:p-5 sm:text-3xl">
          {alt}
        </p>
      </div>
    );
  }

  return (
    <Image
      src={resolved}
      alt={alt}
      fill={fill}
      sizes={sizes || VARIANT_SIZES[variant]}
      priority={priority}
      className={`object-cover ${className}`}
      style={{ objectPosition }}
      onError={() => setFailed(true)}
      unoptimized={resolved.startsWith("http")}
    />
  );
}
