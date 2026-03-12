"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  Globe,
  Building2,
  Users,
  Cpu,
  Activity,
  ClipboardList,
  LogOut,
  ShieldCheck,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { logout } from "@/lib/api";

const NAV_ITEMS = [
  { href: "/superadmin", label: "نظرة عامة", icon: Globe, exact: true },
  { href: "/superadmin/workspaces", label: "المتاجر", icon: Building2 },
  { href: "/superadmin/users", label: "المستخدمون", icon: Users },
  { href: "/superadmin/pipeline", label: "إعدادات NLP", icon: Cpu },
  { href: "/superadmin/system", label: "صحة النظام", icon: Activity },
  { href: "/superadmin/audit-log", label: "سجل العمليات", icon: ClipboardList },
];

export default function SASidebar() {
  const pathname = usePathname();
  const router = useRouter();

  async function handleLogout() {
    await logout();
    router.replace("/login");
  }

  function isActive(href: string, exact?: boolean) {
    if (exact) return pathname === href;
    return pathname.startsWith(href);
  }

  return (
    <aside className="flex flex-col w-64 h-screen bg-slate-900 border-s border-slate-700">
      {/* Logo */}
      <div className="flex items-center gap-3 px-6 py-5 border-b border-slate-700">
        <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-violet-600">
          <ShieldCheck className="h-5 w-5 text-white" />
        </div>
        <div>
          <p className="font-bold text-base text-white">رَدّ</p>
          <p className="text-xs text-slate-400">لوحة الإدارة العليا</p>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
        {NAV_ITEMS.map(({ href, label, icon: Icon, exact }) => (
          <Link
            key={href}
            href={href}
            className={cn(
              "flex items-center gap-3 px-3 py-2.5 rounded-md text-sm font-medium transition-colors",
              isActive(href, exact)
                ? "bg-violet-600/20 text-violet-400 font-semibold"
                : "text-slate-400 hover:bg-slate-800 hover:text-slate-100"
            )}
          >
            <Icon className="h-5 w-5 shrink-0" />
            {label}
          </Link>
        ))}
      </nav>

      {/* Footer */}
      <div className="px-3 py-4 border-t border-slate-700">
        <Link
          href="/dashboard"
          className="flex w-full items-center gap-3 px-3 py-2.5 rounded-md text-sm text-slate-400 hover:bg-slate-800 hover:text-slate-100 transition-colors mb-1"
        >
          <Globe className="h-5 w-5 shrink-0" />
          العودة للوحة المتجر
        </Link>
        <button
          onClick={handleLogout}
          className="flex w-full items-center gap-3 px-3 py-2.5 rounded-md text-sm text-slate-400 hover:bg-red-900/40 hover:text-red-400 transition-colors"
        >
          <LogOut className="h-5 w-5 shrink-0" />
          تسجيل الخروج
        </button>
      </div>
    </aside>
  );
}
