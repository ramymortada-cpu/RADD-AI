import { cn } from "@/lib/utils";
import { Card, CardContent } from "@/components/ui/card";
import type { LucideIcon } from "lucide-react";

interface KPICardProps {
  title: string;
  value: string | number;
  unit?: string;
  subtitle?: string;
  icon: LucideIcon;
  trend?: "up" | "down" | "neutral";
  trendValue?: string;
  colorClass?: string;
}

export default function KPICard({
  title,
  value,
  unit,
  subtitle,
  icon: Icon,
  trend,
  trendValue,
  colorClass = "text-primary",
}: KPICardProps) {
  return (
    <Card className="hover:shadow-md transition-shadow">
      <CardContent className="p-5">
        <div className="flex items-start justify-between">
          <div className="flex-1">
            <p className="text-sm font-medium text-muted-foreground">{title}</p>
            <div className="flex items-baseline gap-1 mt-1">
              <span className={cn("text-3xl font-bold", colorClass)}>{value}</span>
              {unit && <span className="text-sm text-muted-foreground">{unit}</span>}
            </div>
            {subtitle && (
              <p className="text-xs text-muted-foreground mt-1">{subtitle}</p>
            )}
            {trendValue && (
              <div
                className={cn(
                  "flex items-center gap-1 mt-2 text-xs font-medium",
                  trend === "up" ? "text-green-600" : trend === "down" ? "text-red-600" : "text-muted-foreground"
                )}
              >
                <span>{trendValue}</span>
              </div>
            )}
          </div>
          <div className={cn("p-2.5 rounded-lg bg-muted", colorClass)}>
            <Icon className="h-5 w-5" />
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
