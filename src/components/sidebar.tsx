"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  PlusCircle,
  BarChart3,
  Settings,
  CreditCard,
  HelpCircle,
} from "lucide-react";
import { UnderwriteLogo } from "./underwrite-logo";
import { cn } from "@/lib/utils";

const navItems = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/new", label: "New Analysis", icon: PlusCircle },
  { href: "/reports", label: "My Reports", icon: BarChart3 },
];

const bottomNavItems = [
  { href: "/billing", label: "Billing", icon: CreditCard },
  { href: "/settings", label: "Settings", icon: Settings },
  { href: "/help", label: "Help", icon: HelpCircle },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="flex flex-col w-[232px] shrink-0 bg-[#111111] h-screen sticky top-0">
      {/* Logo */}
      <div className="px-5 pt-6 pb-2">
        <Link href="/dashboard">
          <UnderwriteLogo dark />
        </Link>
      </div>

      {/* Nav */}
      <nav className="flex-1 px-3 pt-6 flex flex-col gap-0.5">
        {navItems.map(({ href, label, icon: Icon }) => {
          const active = pathname === href || pathname.startsWith(href + "/");
          return (
            <Link
              key={href}
              href={href}
              className={cn(
                "flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors",
                active
                  ? "bg-[#1F1F1F] text-white"
                  : "text-[#6B6860] hover:text-white hover:bg-[#1A1A1A]"
              )}
            >
              <Icon size={16} strokeWidth={1.75} />
              {label}
            </Link>
          );
        })}
      </nav>

      {/* Bottom nav + user */}
      <div className="px-3 pb-4 flex flex-col gap-0.5">
        {bottomNavItems.map(({ href, label, icon: Icon }) => (
          <Link
            key={href}
            href={href}
            className="flex items-center gap-3 px-3 py-2 rounded-lg text-sm text-[#6B6860] hover:text-white hover:bg-[#1A1A1A] transition-colors"
          >
            <Icon size={16} strokeWidth={1.75} />
            {label}
          </Link>
        ))}

        {/* User avatar */}
        <div className="mt-3 pt-3 border-t border-[#1F1F1F] flex items-center gap-3 px-3 py-2">
          <div className="w-7 h-7 rounded-full bg-[#6357A0] flex items-center justify-center text-white text-xs font-semibold shrink-0">
            MZ
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-xs font-medium text-white truncate">Melad Zahedi</p>
            <p className="text-xs text-[#6B6860] truncate">Pro Plan</p>
          </div>
        </div>
      </div>
    </aside>
  );
}
