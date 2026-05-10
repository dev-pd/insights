import type { Metadata } from "next"
import "./globals.css"
import { Geist } from "next/font/google"

import { cn } from "@/lib/utils"
import { common } from "@/locales/en/common"

const geist = Geist({ subsets: ["latin"], variable: "--font-sans" })

export const metadata: Metadata = {
  title: common.app.title,
  description: common.app.description,
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en" className={cn("font-sans", geist.variable)}>
      <body className="bg-gray-50 text-gray-900 min-h-screen">{children}</body>
    </html>
  )
}
