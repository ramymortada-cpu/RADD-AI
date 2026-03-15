"use client";

/**
 * Onboarding Wizard — RTL Arabic-first
 * Shows when user has no WhatsApp channel connected.
 * Hides permanently when all steps complete or user dismisses (localStorage).
 */
import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import {
  MessageCircle,
  BookOpen,
  Users,
  Settings,
  CheckCircle,
  X,
} from "lucide-react";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { apiFetch, getDocuments, getSettings, getUsers } from "@/lib/api";
import { cn } from "@/lib/utils";

const STORAGE_KEY = "radd_onboarding_hidden";

interface Channel {
  id: string;
  type: string;
  is_active: boolean;
}

interface OnboardingData {
  hasWhatsApp: boolean;
  approvedDocCount: number;
  userCount: number;
  storeNameSet: boolean;
  storeName: string;
}

async function fetchOnboardingData(): Promise<OnboardingData> {
  const [channelsRes, docsRes, usersRes, settingsRes] = await Promise.allSettled([
    apiFetch<{ channels: Channel[] }>("/admin/channels"),
    getDocuments("approved"),
    getUsers(),
    getSettings(),
  ]);

  const channels = channelsRes.status === "fulfilled" ? channelsRes.value.channels : [];
  const hasWhatsApp = channels.some((c) => c.type === "whatsapp" && c.is_active);

  const docs = docsRes.status === "fulfilled" ? docsRes.value : { items: [], total: 0 };
  const approvedDocCount = docs.total ?? docs.items?.length ?? 0;

  const users = usersRes.status === "fulfilled" ? usersRes.value : [];
  const userCount = Array.isArray(users) ? users.length : 0;

  const settings = settingsRes.status === "fulfilled" ? settingsRes.value : null;
  const wsSettings = (settings?.settings as Record<string, unknown>) || {};
  const storeName = String(wsSettings.store_name || settings?.name || "متجرك");
  const storeNameSet = Boolean(wsSettings.store_name);

  return {
    hasWhatsApp,
    approvedDocCount,
    userCount,
    storeNameSet,
    storeName,
  };
}

const STEPS = [
  {
    id: "whatsapp",
    icon: MessageCircle,
    iconColor: "text-green-600",
    iconBg: "bg-green-100 dark:bg-green-900/30",
    title: "ربط واتساب",
    description: "اربط رقم واتساب متجرك لتبدأ استقبال الرسائل",
    actionLabel: "ربط الآن",
    href: "/settings?tab=channels",
    isComplete: (d: OnboardingData) => d.hasWhatsApp,
  },
  {
    id: "kb",
    icon: BookOpen,
    iconColor: "text-blue-600",
    iconBg: "bg-blue-100 dark:bg-blue-900/30",
    title: "أضف محتوى متجرك",
    description: "ارفع سياسة الإرجاع أو الأسئلة الشائعة",
    actionLabel: "إضافة وثيقة",
    href: "/knowledge",
    isComplete: (d: OnboardingData) => d.approvedDocCount >= 1,
  },
  {
    id: "team",
    icon: Users,
    iconColor: "text-purple-600",
    iconBg: "bg-purple-100 dark:bg-purple-900/30",
    title: "أضف فريقك",
    description: "أضف موظفي خدمة العملاء للرد على التصعيدات",
    actionLabel: "دعوة موظف",
    href: "/settings?tab=users",
    isComplete: (d: OnboardingData) => d.userCount >= 2,
  },
  {
    id: "settings",
    icon: Settings,
    iconColor: "text-orange-600",
    iconBg: "bg-orange-100 dark:bg-orange-900/30",
    title: "اضبط إعدادات متجرك",
    description: "حدد مواعيد العمل وعتبات الثقة",
    actionLabel: "فتح الإعدادات",
    href: "/settings",
    isComplete: (d: OnboardingData) => d.storeNameSet,
  },
] as const;

function getStoredHidden(): boolean {
  if (typeof window === "undefined") return false;
  try {
    return localStorage.getItem(STORAGE_KEY) === "true";
  } catch {
    return false;
  }
}

function setStoredHidden(value: boolean): void {
  if (typeof window === "undefined") return;
  try {
    localStorage.setItem(STORAGE_KEY, value ? "true" : "false");
  } catch {
    // ignore
  }
}

export default function OnboardingWizard() {
  const [data, setData] = useState<OnboardingData | null>(null);
  const [hidden, setHidden] = useState(true);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const d = await fetchOnboardingData();
      setData(d);
      const allComplete = STEPS.every((s) => s.isComplete(d));
      if (allComplete) {
        setStoredHidden(true);
      }
      setHidden(getStoredHidden());
    } catch {
      setHidden(true);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  // Refetch when user returns to tab (e.g. after completing a step in settings/knowledge)
  useEffect(() => {
    const onFocus = () => load();
    window.addEventListener("focus", onFocus);
    return () => window.removeEventListener("focus", onFocus);
  }, [load]);

  const handleDismiss = () => {
    setStoredHidden(true);
    setHidden(true);
  };

  if (loading || !data) return null;
  if (hidden) return null;
  if (data.hasWhatsApp) return null;

  const completedCount = STEPS.filter((s) => s.isComplete(data)).length;
  const currentStepIndex = STEPS.findIndex((s) => !s.isComplete(data));
  const currentStep = currentStepIndex >= 0 ? currentStepIndex : STEPS.length - 1;

  return (
    <Card className="rounded-xl border bg-white dark:bg-slate-900 shadow-sm" dir="rtl">
      <CardHeader className="pb-3 pt-5 px-6">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-100">
              أهلاً {data.storeName}! لنبدأ إعداد رَدّ
            </h2>
            <p className="text-sm text-muted-foreground mt-0.5">
              أكمل الخطوات التالية لتفعيل رَدّ في متجرك
            </p>
          </div>
          <Button
            variant="ghost"
            size="sm"
            className="text-muted-foreground hover:text-foreground shrink-0"
            onClick={handleDismiss}
            aria-label="إخفاء"
          >
            <X className="h-4 w-4" />
            <span className="mr-1">إخفاء هذا</span>
          </Button>
        </div>
        {/* Progress bar */}
        <div className="mt-4">
          <div className="flex items-center justify-between text-xs text-muted-foreground mb-1.5">
            <span>{completedCount} من 4 مكتمل</span>
          </div>
          <div className="h-2 w-full rounded-full bg-muted overflow-hidden">
            <div
              className="h-full rounded-full bg-primary transition-all duration-500"
              style={{ width: `${(completedCount / 4) * 100}%` }}
            />
          </div>
        </div>
      </CardHeader>
      <CardContent className="px-6 pb-6 pt-0">
        <div className="space-y-3">
          {STEPS.map((step, idx) => {
            const isComplete = step.isComplete(data);
            const isCurrent = idx === currentStep && !isComplete;
            const Icon = step.icon;

            return (
              <div
                key={step.id}
                className={cn(
                  "flex items-center gap-4 rounded-lg border p-4 transition-colors",
                  isComplete && "border-transparent bg-muted/30 opacity-80",
                  isCurrent && "border-primary/50 bg-primary/5 dark:bg-primary/10",
                  !isComplete && !isCurrent && "border-border"
                )}
              >
                <div
                  className={cn(
                    "flex h-10 w-10 shrink-0 items-center justify-center rounded-lg",
                    step.iconBg,
                    step.iconColor
                  )}
                >
                  {isComplete ? (
                    <CheckCircle className="h-5 w-5 text-green-600" />
                  ) : (
                    <Icon className={cn("h-5 w-5", step.iconColor)} />
                  )}
                </div>
                <div className="flex-1 min-w-0">
                  <h3 className="font-medium text-slate-900 dark:text-slate-100">
                    {step.title}
                  </h3>
                  <p className="text-sm text-muted-foreground mt-0.5">
                    {step.description}
                  </p>
                </div>
                <div className="shrink-0 flex items-center gap-2">
                  {isComplete ? (
                    <Badge variant="success" className="text-xs">
                      مكتمل
                    </Badge>
                  ) : (
                    <Button asChild size="sm" variant="default">
                      <Link href={step.href}>{step.actionLabel}</Link>
                    </Button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </CardContent>
    </Card>
  );
}
