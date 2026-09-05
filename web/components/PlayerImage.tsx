"use client";

import Image from "next/image";
import { useState } from "react";

type PlayerImageProps = {
  src: string;
  alt: string;
  sizes?: string;
  priority?: boolean;
  objectPosition?: string;
  className?: string;
};

export function PlayerImage({
  src,
  alt,
  sizes = "100vw",
  priority = false,
  objectPosition = "center 20%",
  className = "",
}: PlayerImageProps) {
  const [failed, setFailed] = useState(false);

  if (failed) {
    return (
      <div
        className={`absolute inset-0 flex items-end bg-[#1c1c1c] ${className}`}
        role="img"
        aria-label={alt}
      >
        <div className="pointer-events-none absolute inset-0 opacity-40 [background-image:repeating-linear-gradient(90deg,transparent,transparent_31px,#2a2a2a_31px,#2a2a2a_32px)]" />
        <p className="relative p-5 font-serif text-3xl leading-none text-white/50">
          {alt}
        </p>
      </div>
    );
  }

  return (
    <Image
      src={src}
      alt={alt}
      fill
      sizes={sizes}
      priority={priority}
      className={`object-cover ${className}`}
      style={{ objectPosition }}
      onError={() => setFailed(true)}
    />
  );
}
