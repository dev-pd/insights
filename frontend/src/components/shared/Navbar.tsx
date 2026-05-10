"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"

import { HealthCheck } from "@/components/shared/HealthCheck"
import { cn } from "@/lib/utils"
import { common } from "@/locales/en/common"

const NAV_ITEMS = [
  { href: "/", label: common.nav.dashboard },
  { href: "/add", label: common.nav.addFeedback },
  { href: "/feedback", label: common.nav.feedback },
] as const

export function Navbar() {
  const pathname = usePathname()

  return (
    <nav className="border-b bg-background sticky top-0 z-10">
      <div className="container mx-auto max-w-5xl px-4 h-14 flex items-center justify-between">
        <div className="flex items-center gap-6">
          <Link href="/" className="font-semibold text-lg">
            {common.app.title}
          </Link>
          <ul className="flex items-center gap-1">
            {NAV_ITEMS.map((item) => {
              const isActive = pathname === item.href
              return (
                <li key={item.href}>
                  <Link
                    href={item.href}
                    aria-current={isActive ? "page" : undefined}
                    className={cn(
                      "px-3 py-1.5 rounded-md text-sm font-medium transition-colors",
                      isActive
                        ? "bg-secondary text-secondary-foreground"
                        : "text-muted-foreground hover:text-foreground hover:bg-secondary/50",
                    )}
                  >
                    {item.label}
                  </Link>
                </li>
              )
            })}
          </ul>
        </div>
        <HealthCheck />
      </div>
    </nav>
  )
}
