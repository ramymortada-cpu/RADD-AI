"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  LayoutDashboard,
  MessageSquare,
  BookOpen,
  AlertTriangle,
  Settings,
  LogOut,
  Zap,
  Users,
  TrendingUp,
  Radar,
  Sliders,
  BarChart2,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { clearTokens } from "@/lib/auth";

const NAV_ITEMS = [
  { href: "/dashboard", label: "الرئيسية", icon: LayoutDashboard },
  { href: "/conversations", label: "المحادثات", icon: MessageSquare },
  { href: "/customers", label: "ذاكرة العملاء", icon: Users },
  { href: "/analytics", label: "تحليلات الأداء", icon: BarChart2 },
  { href: "/revenue", label: "العائد المالي", icon: TrendingUp },
  { href: "/radar", label: "الرادار التشغيلي", icon: Radar },
  { href: "/rules", label: "قواعد ذكية", icon: Sliders },
  { href: "/knowledge", label: "قاعدة المعرفة", icon: BookOpen },
  { href: "/escalations", label: "التصعيدات", icon: AlertTriangle },
  { href: "/settings", label: "الإعدادات", icon: Settings },
];

export default function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();

  function handleLogout() {
    clearTokens();
    router.replace("/login");
  }

  return (
    <aside className="flex flex-col w-64 h-screen bg-white border-s border-border shadow-sm">
      {/* Logo */}
      <div className="flex items-center gap-3 px-6 py-5 border-b border-border">
        <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary">
          <Zap className="h-5 w-5 text-white" />
        </div>
        <div>
          <p className="font-bold text-base text-foreground">رَدّ</p>
          <p className="text-xs text-muted-foreground">لوحة التحكم</p>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
        {NAV_ITEMS.map(({ href, label, icon: Icon }) => (
          <Link
            key={href}
            href={href}
            className={cn(
              "flex items-center gap-3 px-3 py-2.5 rounded-md text-sm font-medium transition-colors",
              pathname.startsWith(href)
                ? "bg-primary/10 text-primary font-semibold"
                : "text-muted-foreground hover:bg-muted hover:text-foreground"
            )}
          >
            <Icon className="h-5 w-5 shrink-0" />
            {label}
          </Link>
        ))}
      </nav>

      {/* Footer */}
      <div className="px-3 py-4 border-t border-border">
        <button
          onClick={handleLogout}
          className="flex w-full items-center gap-3 px-3 py-2.5 rounded-md text-sm text-muted-foreground hover:bg-red-50 hover:text-red-600 transition-colors"
        >
          <LogOut className="h-5 w-5 shrink-0" />
          تسجيل الخروج
        </button>
      </div>
    </aside>
  );
}
