import type { Metadata } from "next";
import { Barlow_Condensed, Geist, Newsreader } from "next/font/google";
import { SiteFooter } from "@/components/SiteFooter";
import { SiteHeader } from "@/components/SiteHeader";
import { SelectedManagerProvider } from "@/lib/selected-manager";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const newsreader = Newsreader({
  variable: "--font-newsreader",
  subsets: ["latin"],
  style: ["normal", "italic"],
});

const barlow = Barlow_Condensed({
  variable: "--font-barlow",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
});

export const metadata: Metadata = {
  title: "Lofthus Road Open",
  description:
    "Fantasy Premier League-miniligaen Lofthus Road Open — live-tabell, rivaler og sportsjournalistikk.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="nb"
      className={`${geistSans.variable} ${newsreader.variable} ${barlow.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col bg-paper text-ink">
        <SelectedManagerProvider>
          <SiteHeader />
          {children}
          <SiteFooter />
        </SelectedManagerProvider>
      </body>
    </html>
  );
}
