"use client";

import { useEffect, useState } from "react";
import { Save, UserPlus } from "lucide-react";
import TopBar from "@/components/layout/topbar";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  getSettings,
  updateSettings,
  getUsers,
  createUser,
  type WorkspaceSettings,
  type User,
} from "@/lib/api";

export default function SettingsPage() {
  const [wsSettings, setWsSettings] = useState<WorkspaceSettings | null>(null);
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  // Confidence thresholds
  const [autoThreshold, setAutoThreshold] = useState("0.85");
  const [softThreshold, setSoftThreshold] = useState("0.60");

  // New user form
  const [showNewUser, setShowNewUser] = useState(false);
  const [newUser, setNewUser] = useState({
    name: "",
    email: "",
    role: "agent",
    password: "",
  });
  const [creatingUser, setCreatingUser] = useState(false);

  useEffect(() => {
    Promise.all([getSettings(), getUsers()])
      .then(([s, u]) => {
        setWsSettings(s);
        setUsers(u);
        const settings = s.settings as Record<string, unknown>;
        if (settings.confidence_auto_threshold)
          setAutoThreshold(String(settings.confidence_auto_threshold));
        if (settings.confidence_soft_escalation_threshold)
          setSoftThreshold(String(settings.confidence_soft_escalation_threshold));
      })
      .catch(() => setError("تعذّر تحميل الإعدادات"))
      .finally(() => setLoading(false));
  }, []);

  async function handleSave() {
    setSaving(true);
    setError("");
    setSuccess("");
    try {
      await updateSettings({
        confidence_auto_threshold: parseFloat(autoThreshold),
        confidence_soft_escalation_threshold: parseFloat(softThreshold),
      });
      setSuccess("تم حفظ الإعدادات بنجاح");
    } catch {
      setError("تعذّر حفظ الإعدادات");
    } finally {
      setSaving(false);
    }
  }

  async function handleCreateUser(e: React.FormEvent) {
    e.preventDefault();
    setCreatingUser(true);
    setError("");
    try {
      const user = await createUser(newUser);
      setUsers((prev) => [...prev, user]);
      setNewUser({ name: "", email: "", role: "agent", password: "" });
      setShowNewUser(false);
      setSuccess("تم إنشاء المستخدم بنجاح");
    } catch {
      setError("تعذّر إنشاء المستخدم");
    } finally {
      setCreatingUser(false);
    }
  }

  const ROLE_LABELS: Record<string, string> = {
    owner: "مالك",
    admin: "مدير",
    agent: "موظف",
    reviewer: "مراجع",
  };

  if (loading) {
    return (
      <div className="flex flex-col h-full">
        <TopBar title="الإعدادات" />
        <div className="flex-1 flex items-center justify-center">
          <div className="w-10 h-10 rounded-full border-4 border-primary border-t-transparent animate-spin" />
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full overflow-hidden">
      <TopBar title="الإعدادات" subtitle={wsSettings?.name} />

      <div className="flex-1 overflow-y-auto p-6 space-y-6">
        {error && (
          <div className="text-sm text-destructive bg-destructive/10 px-4 py-3 rounded-lg">
            {error}
          </div>
        )}
        {success && (
          <div className="text-sm text-green-700 bg-green-50 px-4 py-3 rounded-lg border border-green-200">
            {success}
          </div>
        )}

        {/* Workspace info */}
        {wsSettings && (
          <Card>
            <CardHeader>
              <CardTitle className="text-base">معلومات المتجر</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 text-sm">
              <div className="grid grid-cols-2 gap-x-8 gap-y-2">
                <div>
                  <span className="text-muted-foreground">الاسم: </span>
                  <strong>{wsSettings.name}</strong>
                </div>
                <div>
                  <span className="text-muted-foreground">الرمز: </span>
                  <strong dir="ltr">{wsSettings.slug}</strong>
                </div>
                <div>
                  <span className="text-muted-foreground">الخطة: </span>
                  <Badge variant="default">{wsSettings.plan}</Badge>
                </div>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Confidence thresholds */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">عتبات الثقة</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="text-sm text-muted-foreground">
              تحدد هذه القيم متى يرد الذكاء الاصطناعي تلقائياً ومتى يحيل المحادثة لموظف.
            </p>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <label className="text-sm font-medium">
                  عتبة الرد التلقائي
                  <span className="text-muted-foreground"> (≥ هذه القيمة → رد مباشر)</span>
                </label>
                <Input
                  type="number"
                  min="0"
                  max="1"
                  step="0.05"
                  dir="ltr"
                  value={autoThreshold}
                  onChange={(e) => setAutoThreshold(e.target.value)}
                />
              </div>
              <div className="space-y-1.5">
                <label className="text-sm font-medium">
                  عتبة التصعيد الناعم
                  <span className="text-muted-foreground"> (أقل منها → تصعيد)</span>
                </label>
                <Input
                  type="number"
                  min="0"
                  max="1"
                  step="0.05"
                  dir="ltr"
                  value={softThreshold}
                  onChange={(e) => setSoftThreshold(e.target.value)}
                />
              </div>
            </div>
            <Button onClick={handleSave} disabled={saving}>
              <Save className="h-4 w-4 me-2" />
              {saving ? "جارٍ الحفظ..." : "حفظ الإعدادات"}
            </Button>
          </CardContent>
        </Card>

        {/* Users */}
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle className="text-base">إدارة المستخدمين</CardTitle>
              <Button size="sm" onClick={() => setShowNewUser((v) => !v)}>
                <UserPlus className="h-4 w-4 me-2" />
                مستخدم جديد
              </Button>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            {/* New user form */}
            {showNewUser && (
              <form
                onSubmit={handleCreateUser}
                className="grid grid-cols-1 sm:grid-cols-2 gap-3 p-4 bg-muted/50 rounded-lg"
              >
                <div className="space-y-1.5">
                  <label className="text-sm font-medium">الاسم</label>
                  <Input
                    required
                    value={newUser.name}
                    onChange={(e) => setNewUser((u) => ({ ...u, name: e.target.value }))}
                  />
                </div>
                <div className="space-y-1.5">
                  <label className="text-sm font-medium">البريد الإلكتروني</label>
                  <Input
                    required
                    type="email"
                    dir="ltr"
                    value={newUser.email}
                    onChange={(e) => setNewUser((u) => ({ ...u, email: e.target.value }))}
                  />
                </div>
                <div className="space-y-1.5">
                  <label className="text-sm font-medium">الصلاحية</label>
                  <select
                    className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                    value={newUser.role}
                    onChange={(e) => setNewUser((u) => ({ ...u, role: e.target.value }))}
                  >
                    <option value="agent">موظف</option>
                    <option value="reviewer">مراجع</option>
                    <option value="admin">مدير</option>
                  </select>
                </div>
                <div className="space-y-1.5">
                  <label className="text-sm font-medium">كلمة المرور</label>
                  <Input
                    required
                    type="password"
                    dir="ltr"
                    value={newUser.password}
                    onChange={(e) => setNewUser((u) => ({ ...u, password: e.target.value }))}
                  />
                </div>
                <div className="sm:col-span-2 flex gap-2 justify-end">
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => setShowNewUser(false)}
                  >
                    إلغاء
                  </Button>
                  <Button type="submit" disabled={creatingUser}>
                    {creatingUser ? "جارٍ الإنشاء..." : "إنشاء"}
                  </Button>
                </div>
              </form>
            )}

            {/* Users table */}
            <div className="space-y-2">
              {users.map((u) => (
                <div
                  key={u.id}
                  className="flex items-center gap-3 p-3 rounded-lg bg-muted/30 hover:bg-muted/50 transition-colors"
                >
                  <div className="h-9 w-9 rounded-full bg-primary/10 flex items-center justify-center shrink-0">
                    <span className="text-primary font-semibold text-sm">
                      {u.name[0]}
                    </span>
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium">{u.name}</p>
                    <p className="text-xs text-muted-foreground" dir="ltr">
                      {u.email}
                    </p>
                  </div>
                  <Badge variant={u.is_active ? "success" : "muted"}>
                    {ROLE_LABELS[u.role] || u.role}
                  </Badge>
                  {!u.is_active && (
                    <Badge variant="muted">غير نشط</Badge>
                  )}
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
