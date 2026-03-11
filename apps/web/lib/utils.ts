import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatArabicDate(iso: string): string {
  return new Date(iso).toLocaleString("ar-SA", {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function formatRelativeTime(iso: string): string {
  const diff = (Date.now() - new Date(iso).getTime()) / 1000;
  if (diff < 60) return "الآن";
  if (diff < 3600) return `منذ ${Math.floor(diff / 60)} دقيقة`;
  if (diff < 86400) return `منذ ${Math.floor(diff / 3600)} ساعة`;
  return `منذ ${Math.floor(diff / 86400)} يوم`;
}

export function confidenceColor(score: number): string {
  if (score >= 0.85) return "text-green-600";
  if (score >= 0.60) return "text-amber-600";
  return "text-red-600";
}

export function confidenceLabel(score: number): string {
  if (score >= 0.85) return "عالية";
  if (score >= 0.60) return "متوسطة";
  return "منخفضة";
}

export const INTENT_LABELS: Record<string, string> = {
  greeting: "تحية",
  order_status: "حالة الطلب",
  shipping: "الشحن",
  return_policy: "الإرجاع",
  store_hours: "مواعيد",
  other: "عام",
};

export const STATUS_LABELS: Record<string, string> = {
  active: "نشط",
  waiting_agent: "ينتظر موظف",
  resolved: "محلول",
  expired: "منتهي",
};

export const STATUS_COLORS: Record<string, string> = {
  active: "bg-green-100 text-green-800",
  waiting_agent: "bg-amber-100 text-amber-800",
  resolved: "bg-gray-100 text-gray-600",
  expired: "bg-red-100 text-red-600",
};
