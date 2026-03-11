# Skill: Add a New Frontend Page

## When to Use
When you need to add a new page to the Next.js RTL Arabic dashboard.

## Complete Example: Adding a "Reports" page

### Step 1: Create the page file
```typescript
// apps/web/app/(dashboard)/reports/page.tsx
"use client";

import { useEffect, useState } from "react";
import TopBar from "@/components/layout/topbar";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { apiFetch } from "@/lib/api";  // use internal apiFetch

type ReportData = {
  week: string;
  messages: number;
  automation_rate: number;
};

export default function ReportsPage() {
  const [data, setData] = useState<ReportData[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Replace with your actual API call
    fetch("/api/v1/admin/analytics")
      .then(r => r.json())
      .then(d => {
        setData([]);  // transform as needed
        setLoading(false);
      })
      .catch(console.error);
  }, []);

  return (
    <div className="flex flex-col h-full overflow-hidden">
      <TopBar title="التقارير" subtitle="تحليل الأداء الأسبوعي" />
      
      <div className="flex-1 overflow-y-auto p-6 space-y-6">
        {loading ? (
          <div className="h-48 rounded-lg bg-muted animate-pulse" />
        ) : (
          <Card>
            <CardHeader>
              <CardTitle className="text-base">الأداء الأسبوعي</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-muted-foreground text-sm">
                سيتم إضافة التقارير قريباً
              </p>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}
```

### Step 2: Add to sidebar navigation
```typescript
// apps/web/components/layout/sidebar.tsx — ADD to NAV_ITEMS:
import { BarChart3 } from "lucide-react";

const NAV_ITEMS = [
  { href: "/dashboard", label: "الرئيسية", icon: LayoutDashboard },
  { href: "/conversations", label: "المحادثات", icon: MessageSquare },
  { href: "/knowledge", label: "قاعدة المعرفة", icon: BookOpen },
  { href: "/escalations", label: "التصعيدات", icon: AlertTriangle },
  { href: "/reports", label: "التقارير", icon: BarChart3 },  // ADD
  { href: "/settings", label: "الإعدادات", icon: Settings },
];
```

### Step 3: Add API function (if needed)
```typescript
// apps/web/lib/api.ts — ADD:
export type WeeklyReport = {
  week_start: string;
  messages: number;
  automation_rate: number;
  escalations: number;
};

export const getWeeklyReports = () =>
  apiFetch<WeeklyReport[]>("/admin/reports/weekly");
```

---

## RTL Component Patterns

### Arabic text in components
```tsx
// Always use dir="rtl" and arabic-text class for Arabic content
<p className="arabic-text">{arabicText}</p>

// Numbers: display LTR (phone numbers, IDs)
<span dir="ltr">{phoneNumber}</span>
```

### Chat bubble (already defined in globals.css)
```tsx
// Customer message (right-aligned)
<div className="bubble-customer p-3">
  <p className="arabic-text">{message.content}</p>
</div>

// System/AI message (left-aligned)
<div className="bubble-system p-3">
  <p className="arabic-text">{message.content}</p>
</div>

// Agent message (left-aligned, different color)
<div className="bubble-agent p-3">
  <p className="arabic-text">{message.content}</p>
</div>
```

### Status badges
```tsx
import { Badge } from "@/components/ui/badge";

// Use these variants: default, secondary, success, warning, muted, destructive
<Badge variant="success">معتمد</Badge>
<Badge variant="warning">قيد المراجعة</Badge>
<Badge variant="muted">مؤرشف</Badge>
```

### Loading skeleton
```tsx
{loading ? (
  <div className="space-y-3">
    {Array.from({ length: 5 }).map((_, i) => (
      <div key={i} className="h-20 rounded-lg bg-muted animate-pulse" />
    ))}
  </div>
) : (
  /* your content */
)}
```

### Error state
```tsx
{error && (
  <div className="text-sm text-destructive bg-destructive/10 px-4 py-3 rounded-lg">
    {error}
  </div>
)}
```

---

## Auth Guard (all dashboard pages already have this)
The `app/(dashboard)/layout.tsx` handles auth redirect automatically:
```tsx
// This is already in layout.tsx — no need to add to each page
useEffect(() => {
  if (!isAuthenticated()) router.replace("/login");
}, []);
```

---

## Available UI Components

| Component | Import | Usage |
|-----------|--------|-------|
| Button | `@/components/ui/button` | Actions |
| Card | `@/components/ui/card` | Content sections |
| Badge | `@/components/ui/badge` | Status labels |
| Input | `@/components/ui/input` | Form inputs |
| Textarea | `@/components/ui/textarea` | Multi-line input |
| TopBar | `@/components/layout/topbar` | Page header |
| KPICard | `@/components/dashboard/kpi-card` | Metric cards |

Icons: import from `lucide-react` — browse at lucide.dev
