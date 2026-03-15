"use client";

import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import {
  Save, UserPlus, Eye, EyeOff, RefreshCw, Layers,
  Instagram, Code, Mic, MicOff, Smartphone, Copy, Check,
  Webhook, Globe, Store, ShoppingBag,
} from "lucide-react";
import TopBar from "@/components/layout/topbar";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import Link from "next/link";
import {
  getSettings,
  updateSettings,
  getUsers,
  createUser,
  getShadowMode,
  setShadowMode,
  triggerSallaSync,
  applyStarterPack,
  syncZidStore,
  setupInstagramChannel,
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

  // Shadow mode
  const [shadowMode, setShadowModeState] = useState(false);
  const [shadowLoading, setShadowLoading] = useState(false);

  // Salla Sync
  const [sallaToken, setSallaToken] = useState("");
  const [sallaSyncing, setSallaSyncing] = useState(false);
  const [sallaSyncMsg, setSallaSyncMsg] = useState("");

  // Zid Sync
  const [zidToken, setZidToken] = useState("");
  const [zidSyncing, setZidSyncing] = useState(false);
  const [zidSyncMsg, setZidSyncMsg] = useState("");

  // Instagram Setup
  const [igPageId, setIgPageId] = useState("");
  const [igToken, setIgToken] = useState("");
  const [igSetupMsg, setIgSetupMsg] = useState("");
  const [igSetupLoading, setIgSetupLoading] = useState(false);

  // Voice Understanding
  const [voiceEnabled, setVoiceEnabled] = useState(true);
  const [voiceLoading, setVoiceLoading] = useState(false);

  // Pipeline v2
  const [useIntentV2, setUseIntentV2] = useState(false);
  const [useVerifierV2, setUseVerifierV2] = useState(false);
  const [pipelineV2Loading, setPipelineV2Loading] = useState(false);

  // Store name
  const [storeName, setStoreName] = useState("متجرنا");

  // E-commerce Platform (Salla / Shopify)
  const [platform, setPlatform] = useState<"salla" | "shopify">("salla");
  const [sallaStoreId, setSallaStoreId] = useState("");
  const [sallaAccessToken, setSallaAccessToken] = useState("");
  const [shopifyDomain, setShopifyDomain] = useState("");
  const [shopifyAccessToken, setShopifyAccessToken] = useState("");
  const [platformSaving, setPlatformSaving] = useState(false);

  // Webhook URLs / copy state
  const [copiedKey, setCopiedKey] = useState<string | null>(null);

  // Starter Packs
  const [starterSector, setStarterSector] = useState("perfumes");
  const [starterApplying, setStarterApplying] = useState(false);
  const [starterMsg, setStarterMsg] = useState("");

  // New user form
  const [showNewUser, setShowNewUser] = useState(false);
  const [newUser, setNewUser] = useState({
    name: "",
    email: "",
    role: "agent",
    password: "",
  });
  const [creatingUser, setCreatingUser] = useState(false);

  const searchParams = useSearchParams();
  const tabFromUrl = searchParams.get("tab") || "general";

  // Scroll to section when ?tab= is in URL
  useEffect(() => {
    if (loading) return;
    if (tabFromUrl === "channels") {
      document.getElementById("settings-channels")?.scrollIntoView({ behavior: "smooth", block: "start" });
    } else if (tabFromUrl === "users") {
      document.getElementById("settings-users")?.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }, [tabFromUrl, loading]);

  useEffect(() => {
    Promise.all([getSettings(), getUsers(), getShadowMode()])
      .then(([s, u, sm]) => {
        setWsSettings(s);
        setUsers(u);
        setShadowModeState(sm.shadow_mode);
        const wsSettings = s.settings as Record<string, unknown>;
        if (wsSettings.confidence_auto_threshold)
          setAutoThreshold(String(wsSettings.confidence_auto_threshold));
        if (wsSettings.confidence_soft_escalation_threshold)
          setSoftThreshold(String(wsSettings.confidence_soft_escalation_threshold));
        if (typeof wsSettings.use_intent_v2 === "boolean")
          setUseIntentV2(wsSettings.use_intent_v2);
        if (typeof wsSettings.use_verifier_v2 === "boolean")
          setUseVerifierV2(wsSettings.use_verifier_v2);
        if (typeof wsSettings.voice_transcription_enabled === "boolean")
          setVoiceEnabled(wsSettings.voice_transcription_enabled);
        const p = String(wsSettings.platform || "salla").toLowerCase();
        if (p === "shopify" || p === "salla") setPlatform(p as "salla" | "shopify");
        if (wsSettings.salla_store_id) setSallaStoreId(String(wsSettings.salla_store_id));
        if (wsSettings.salla_access_token) setSallaAccessToken(String(wsSettings.salla_access_token));
        if (wsSettings.shopify_domain) setShopifyDomain(String(wsSettings.shopify_domain));
        if (wsSettings.shopify_access_token) setShopifyAccessToken(String(wsSettings.shopify_access_token));
        if (wsSettings.store_name) setStoreName(String(wsSettings.store_name));
      })
      .catch(() => setError("تعذّر تحميل الإعدادات"))
      .finally(() => setLoading(false));
  }, []);

  async function handleToggleShadowMode() {
    setShadowLoading(true);
    try {
      const res = await setShadowMode(!shadowMode);
      setShadowModeState(res.shadow_mode);
      setSuccess(res.shadow_mode ? "تم تفعيل وضع المراقبة — رَدّ لن يرسل ردوداً للعملاء" : "تم إيقاف وضع المراقبة — رَدّ يرد على العملاء الآن");
    } catch {
      setError("تعذّر تغيير وضع المراقبة");
    } finally {
      setShadowLoading(false);
    }
  }

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

  async function handleSallaSync() {
    if (!sallaToken.trim()) { setError("أدخل رمز Salla API أولاً"); return; }
    setSallaSyncing(true);
    setSallaSyncMsg("");
    setError("");
    try {
      const res = await triggerSallaSync(sallaToken);
      setSallaSyncMsg(`تمت المزامنة — ${res.products_synced} منتج، ${res.documents_created} مستند KB`);
    } catch {
      setError("تعذّر المزامنة مع Salla — تأكد من صحة الرمز");
    } finally {
      setSallaSyncing(false);
    }
  }

  async function handleApplyStarterPack() {
    setStarterApplying(true);
    setStarterMsg("");
    setError("");
    try {
      await applyStarterPack(starterSector);
      setStarterMsg(`تم تطبيق الباقة الجاهزة لقطاع "${SECTOR_LABELS[starterSector]}" بنجاح`);
    } catch {
      setError("تعذّر تطبيق الباقة الجاهزة");
    } finally {
      setStarterApplying(false);
    }
  }

  function copyToClipboard(text: string, key: string) {
    navigator.clipboard.writeText(text);
    setCopiedKey(key);
    setTimeout(() => setCopiedKey(null), 2000);
  }

  async function handleVoiceToggle() {
    setVoiceLoading(true);
    try {
      await updateSettings({ voice_transcription_enabled: !voiceEnabled });
      setVoiceEnabled(!voiceEnabled);
      setSuccess(voiceEnabled ? "تم إيقاف تفريغ الرسائل الصوتية" : "تم تفعيل تفريغ الرسائل الصوتية بـ Whisper");
    } catch {
      setError("تعذّر تحديث إعداد الصوت");
    } finally {
      setVoiceLoading(false);
    }
  }

  async function handleIntentV2Toggle() {
    setPipelineV2Loading(true);
    try {
      await updateSettings({ use_intent_v2: !useIntentV2 });
      setUseIntentV2(!useIntentV2);
      setSuccess(!useIntentV2 ? "تم تفعيل مصنف النوايا v2 (LLM)" : "تم إيقاف مصنف النوايا v2");
    } catch {
      setError("تعذّر تحديث إعداد Pipeline v2");
    } finally {
      setPipelineV2Loading(false);
    }
  }

  async function handleVerifierV2Toggle() {
    setPipelineV2Loading(true);
    try {
      await updateSettings({ use_verifier_v2: !useVerifierV2 });
      setUseVerifierV2(!useVerifierV2);
      setSuccess(!useVerifierV2 ? "تم تفعيل نظام التحقق v2 (NLI)" : "تم إيقاف نظام التحقق v2");
    } catch {
      setError("تعذّر تحديث إعداد Pipeline v2");
    } finally {
      setPipelineV2Loading(false);
    }
  }

  async function handleSavePlatform() {
    setPlatformSaving(true);
    setError("");
    setSuccess("");
    try {
      const payload: Record<string, unknown> = { platform, store_name: storeName || "متجرنا" };
      if (platform === "salla") {
        if (sallaStoreId) payload.salla_store_id = sallaStoreId;
        if (sallaAccessToken) payload.salla_access_token = sallaAccessToken;
      } else {
        if (shopifyDomain) payload.shopify_domain = shopifyDomain;
        if (shopifyAccessToken) payload.shopify_access_token = shopifyAccessToken;
      }
      await updateSettings(payload);
      setSuccess("تم حفظ إعدادات المتجر بنجاح");
    } catch {
      setError("تعذّر حفظ إعدادات المتجر");
    } finally {
      setPlatformSaving(false);
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

  const SECTOR_LABELS: Record<string, string> = {
    perfumes: "عطور",
    fashion: "أزياء",
    electronics: "إلكترونيات",
    food: "طعام",
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

  const TABS = [
    { id: "general", label: "عام", href: "/settings" },
    { id: "channels", label: "القنوات", href: "/settings?tab=channels" },
    { id: "users", label: "المستخدمون", href: "/settings?tab=users" },
  ] as const;

  return (
    <div className="flex flex-col h-full overflow-hidden">
      <TopBar title="الإعدادات" subtitle={wsSettings?.name} />

      {/* Tab bar */}
      <div className="flex gap-1 px-6 py-2 border-b border-border bg-muted/30 shrink-0">
        {TABS.map((t) => (
          <Link
            key={t.id}
            href={t.href}
            className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
              tabFromUrl === t.id
                ? "bg-background text-foreground shadow-sm border border-border"
                : "text-muted-foreground hover:text-foreground hover:bg-muted/50"
            }`}
          >
            {t.label}
          </Link>
        ))}
      </div>

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

        {/* E-commerce Platform — Salla / Shopify */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <Store className="h-4 w-4 text-primary" />
              ربط المتجر — منصة التجارة الإلكترونية
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-1.5">
              <label className="text-sm font-medium">اسم المتجر (يظهر في الردود)</label>
              <Input
                placeholder="متجرنا"
                value={storeName}
                onChange={(e) => setStoreName(e.target.value)}
              />
            </div>
            <p className="text-sm text-muted-foreground">
              اختر المنصة المستخدمة لمتجرك. رَدّ سيستعلم عن حالة الطلبات تلقائياً عند سؤال العميل.
            </p>
            <div className="space-y-1.5">
              <label className="text-sm font-medium">المنصة</label>
              <div className="flex gap-4">
                <button
                  type="button"
                  onClick={() => setPlatform("salla")}
                  className={`flex items-center gap-2 px-4 py-2.5 rounded-lg border transition-colors ${
                    platform === "salla" ? "border-primary bg-primary/5 text-primary" : "border-border hover:bg-muted/50"
                  }`}
                >
                  <ShoppingBag className="h-4 w-4" />
                  Salla — سلة
                </button>
                <button
                  type="button"
                  onClick={() => setPlatform("shopify")}
                  className={`flex items-center gap-2 px-4 py-2.5 rounded-lg border transition-colors ${
                    platform === "shopify" ? "border-primary bg-primary/5 text-primary" : "border-border hover:bg-muted/50"
                  }`}
                >
                  <Globe className="h-4 w-4" />
                  Shopify
                </button>
              </div>
            </div>

            {platform === "salla" && (
              <div className="space-y-3 pt-2 border-t">
                <div className="space-y-1.5">
                  <label className="text-sm font-medium">معرّف المتجر (اختياري)</label>
                  <Input
                    dir="ltr"
                    placeholder="Store ID"
                    value={sallaStoreId}
                    onChange={(e) => setSallaStoreId(e.target.value)}
                    className="font-mono text-sm"
                  />
                </div>
                <div className="space-y-1.5">
                  <label className="text-sm font-medium">Salla Access Token</label>
                  <Input
                    type="password"
                    dir="ltr"
                    placeholder="Bearer token من لوحة Salla"
                    value={sallaAccessToken}
                    onChange={(e) => setSallaAccessToken(e.target.value)}
                    className="font-mono text-sm"
                  />
                  <p className="text-xs text-muted-foreground">يُستخدم لاستعلام حالة الطلبات والشحن</p>
                </div>
              </div>
            )}

            {platform === "shopify" && (
              <div className="space-y-3 pt-2 border-t">
                <div className="space-y-1.5">
                  <label className="text-sm font-medium">Shopify Domain</label>
                  <Input
                    dir="ltr"
                    placeholder="mystore.myshopify.com"
                    value={shopifyDomain}
                    onChange={(e) => setShopifyDomain(e.target.value)}
                    className="font-mono text-sm"
                  />
                </div>
                <div className="space-y-1.5">
                  <label className="text-sm font-medium">Shopify Admin API Access Token</label>
                  <Input
                    type="password"
                    dir="ltr"
                    placeholder="shpat_xxxx..."
                    value={shopifyAccessToken}
                    onChange={(e) => setShopifyAccessToken(e.target.value)}
                    className="font-mono text-sm"
                  />
                  <p className="text-xs text-muted-foreground">Private App مع صلاحية read_orders</p>
                </div>
              </div>
            )}

            <Button onClick={handleSavePlatform} disabled={platformSaving}>
              <Save className="h-4 w-4 me-2" />
              {platformSaving ? "جارٍ الحفظ..." : "حفظ إعدادات المتجر"}
            </Button>
          </CardContent>
        </Card>

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

        {/* Pipeline v2 — Intent & Verifier */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <Code className="h-4 w-4 text-primary" />
              Pipeline v2 — مصنف النوايا والتحقق
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="text-sm text-muted-foreground">
              تفعيل الإصدارات المحسّنة من مصنف النوايا (LLM) ونظام التحقق (NLI) لتحسين دقة الردود.
            </p>
            <div className="space-y-3">
              <div className="flex items-center justify-between p-3 rounded-lg border bg-muted/30">
                <div>
                  <p className="text-sm font-medium">مصنف النوايا v2 (LLM)</p>
                  <p className="text-xs text-muted-foreground">استخدام نموذج لغوي كبير لتصنيف النوايا بدقة أعلى</p>
                </div>
                <Button
                  variant={useIntentV2 ? "default" : "outline"}
                  size="sm"
                  onClick={handleIntentV2Toggle}
                  disabled={pipelineV2Loading}
                >
                  {useIntentV2 ? "مفعّل" : "إيقاف"}
                </Button>
              </div>
              <div className="flex items-center justify-between p-3 rounded-lg border bg-muted/30">
                <div>
                  <p className="text-sm font-medium">نظام التحقق v2 (NLI)</p>
                  <p className="text-xs text-muted-foreground">التحقق من صحة الردود باستخدام Natural Language Inference</p>
                </div>
                <Button
                  variant={useVerifierV2 ? "default" : "outline"}
                  size="sm"
                  onClick={handleVerifierV2Toggle}
                  disabled={pipelineV2Loading}
                >
                  {useVerifierV2 ? "مفعّل" : "إيقاف"}
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Shadow Mode */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              {shadowMode ? <EyeOff className="h-4 w-4 text-amber-500" /> : <Eye className="h-4 w-4 text-green-600" />}
              وضع المراقبة (Shadow Mode)
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="text-sm text-muted-foreground">
              عند تفعيله، يعمل رَدّ بشكل طبيعي ويسجّل جميع الردود
              <strong className="text-foreground"> لكنه لا يرسلها للعملاء</strong>.
              مثالي لتجربة 48 ساعة قبل الإطلاق الرسمي.
            </p>
            <div className={`flex items-center gap-4 p-4 rounded-lg border ${shadowMode ? "bg-amber-50 border-amber-200" : "bg-green-50 border-green-200"}`}>
              <div className={`h-3 w-3 rounded-full ${shadowMode ? "bg-amber-400 animate-pulse" : "bg-green-500"}`} />
              <span className={`text-sm font-medium ${shadowMode ? "text-amber-700" : "text-green-700"}`}>
                {shadowMode ? "وضع المراقبة مفعّل — لا يُرسل ردود" : "النظام يعمل بشكل طبيعي"}
              </span>
              <Button
                variant={shadowMode ? "destructive" : "outline"}
                size="sm"
                className="ms-auto"
                onClick={handleToggleShadowMode}
                disabled={shadowLoading}
              >
                {shadowLoading ? "جارٍ التغيير..." : shadowMode ? "إيقاف وضع المراقبة" : "تفعيل وضع المراقبة"}
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* Salla Auto-Sync */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <RefreshCw className="h-4 w-4 text-primary" />
              مزامنة Salla التلقائية
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="text-sm text-muted-foreground">
              استورد منتجاتك وسياسات متجرك من Salla مباشرةً إلى قاعدة المعرفة.
            </p>
            <div className="flex gap-2">
              <Input
                type="password"
                dir="ltr"
                placeholder="Salla API Token"
                value={sallaToken}
                onChange={(e) => setSallaToken(e.target.value)}
                className="flex-1 font-mono text-xs"
              />
              <Button
                onClick={handleSallaSync}
                disabled={sallaSyncing || !sallaToken.trim()}
              >
                {sallaSyncing ? "جارٍ المزامنة..." : "مزامنة الآن"}
              </Button>
            </div>
            {sallaSyncMsg && (
              <div className="text-sm text-green-700 bg-green-50 px-3 py-2 rounded-lg">
                {sallaSyncMsg}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Zid Sync */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <RefreshCw className="h-4 w-4 text-primary" />
              مزامنة Zid — زد
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="text-sm text-muted-foreground">
              زامن المنتجات والسياسات من متجرك على Zid (زد) إلى قاعدة المعرفة تلقائياً.
            </p>
            <div className="flex gap-2">
              <Input
                type="password"
                dir="ltr"
                placeholder="Zid Manager Token"
                value={zidToken}
                onChange={(e) => setZidToken(e.target.value)}
                className="flex-1 font-mono text-xs"
              />
              <Button
                onClick={async () => {
                  if (!zidToken.trim()) return;
                  setZidSyncing(true);
                  try {
                    const res = await syncZidStore(zidToken);
                    setZidSyncMsg(`✅ تم مزامنة ${res.products_synced} منتج وإنشاء ${res.documents_created} وثيقة`);
                  } catch {
                    setZidSyncMsg("❌ فشل الاتصال بـ Zid — تحقق من الـ token");
                  } finally {
                    setZidSyncing(false);
                  }
                }}
                disabled={zidSyncing || !zidToken.trim()}
              >
                {zidSyncing ? "جارٍ المزامنة..." : "مزامنة الآن"}
              </Button>
            </div>
            {zidSyncMsg && (
              <div className={`text-sm px-3 py-2 rounded-lg ${zidSyncMsg.startsWith("✅") ? "text-green-700 bg-green-50" : "text-red-700 bg-red-50"}`}>
                {zidSyncMsg}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Instagram DM */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <Instagram className="h-4 w-4 text-pink-500" />
              Instagram DM
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="text-sm text-muted-foreground">
              فعّل الردود التلقائية على رسائل Instagram المباشرة.
            </p>
            <div className="grid grid-cols-2 gap-2">
              <Input
                dir="ltr"
                placeholder="Instagram Page ID"
                value={igPageId}
                onChange={(e) => setIgPageId(e.target.value)}
                className="font-mono text-xs"
              />
              <Input
                type="password"
                dir="ltr"
                placeholder="Page Access Token"
                value={igToken}
                onChange={(e) => setIgToken(e.target.value)}
                className="font-mono text-xs"
              />
            </div>
            <Button
              onClick={async () => {
                if (!igPageId.trim() || !igToken.trim()) return;
                setIgSetupLoading(true);
                try {
                  await setupInstagramChannel(igPageId, igToken);
                  setIgSetupMsg("✅ تم تفعيل Instagram DM بنجاح");
                } catch {
                  setIgSetupMsg("❌ فشل الإعداد — تحقق من الـ Page ID والـ Token");
                } finally {
                  setIgSetupLoading(false);
                }
              }}
              disabled={igSetupLoading || !igPageId.trim() || !igToken.trim()}
            >
              {igSetupLoading ? "جارٍ الإعداد..." : "تفعيل Instagram"}
            </Button>
            {igSetupMsg && (
              <div className={`text-sm px-3 py-2 rounded-lg ${igSetupMsg.startsWith("✅") ? "text-green-700 bg-green-50" : "text-red-700 bg-red-50"}`}>
                {igSetupMsg}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Voice Understanding Toggle */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              {voiceEnabled
                ? <Mic className="h-4 w-4 text-green-500" />
                : <MicOff className="h-4 w-4 text-muted-foreground" />
              }
              تفريغ الرسائل الصوتية (Whisper AI)
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-start justify-between gap-4">
              <div className="space-y-1 text-sm text-muted-foreground leading-relaxed">
                <p>
                  عندما يرسل العميل رسالة صوتية على WhatsApp، يُفرّغها رَدّ تلقائياً
                  بـ OpenAI Whisper ويُعالجها كنص عربي.
                </p>
                <p>
                  الحالة الحالية:{" "}
                  <span className={voiceEnabled ? "text-green-600 font-semibold" : "text-muted-foreground"}>
                    {voiceEnabled ? "✅ مفعّل" : "⏸ موقوف"}
                  </span>
                </p>
              </div>
              <Button
                variant={voiceEnabled ? "destructive" : "default"}
                size="sm"
                onClick={handleVoiceToggle}
                disabled={voiceLoading}
                className="shrink-0"
              >
                {voiceLoading
                  ? "جارٍ الحفظ..."
                  : voiceEnabled
                  ? "إيقاف"
                  : "تفعيل"}
              </Button>
            </div>
            {voiceEnabled && (
              <div className="text-xs text-muted-foreground bg-muted/50 rounded-lg p-3 space-y-1">
                <p>• يدعم: OGG, MP3, MP4, WebM, WAV</p>
                <p>• اللغة المبدئية: العربية (يكتشف اللهجة تلقائياً)</p>
                <p>• في حالة الفشل: يُرسل رسالة للعميل يطلب منه الكتابة</p>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Webhook URLs — tab=channels */}
        <Card id="settings-channels">
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <Webhook className="h-4 w-4 text-blue-500" />
              روابط Webhook — للإعداد في المنصات الخارجية
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="text-sm text-muted-foreground">
              استخدم هذه الروابط عند إعداد الـ Webhook في Meta (Instagram) أو Zid.
            </p>

            {/* WhatsApp */}
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-muted-foreground">WhatsApp Webhook URL</label>
              <div className="flex items-center gap-2">
                <code className="flex-1 text-xs bg-muted px-3 py-2 rounded-lg font-mono text-foreground overflow-x-auto" dir="ltr">
                  {typeof window !== "undefined" ? `${window.location.origin.replace("3000", "8000")}/api/v1/webhooks/whatsapp` : "https://api.radd.ai/api/v1/webhooks/whatsapp"}
                </code>
                <button
                  onClick={() => copyToClipboard("/api/v1/webhooks/whatsapp", "wa")}
                  className="p-2 hover:bg-muted rounded-lg transition-colors shrink-0"
                >
                  {copiedKey === "wa" ? <Check className="w-4 h-4 text-green-500" /> : <Copy className="w-4 h-4 text-muted-foreground" />}
                </button>
              </div>
            </div>

            {/* Instagram */}
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-muted-foreground">Instagram DM Webhook URL</label>
              <div className="flex items-center gap-2">
                <code className="flex-1 text-xs bg-muted px-3 py-2 rounded-lg font-mono text-foreground overflow-x-auto" dir="ltr">
                  {typeof window !== "undefined" ? `${window.location.origin.replace("3000", "8000")}/api/v1/webhooks/instagram` : "https://api.radd.ai/api/v1/webhooks/instagram"}
                </code>
                <button
                  onClick={() => copyToClipboard("/api/v1/webhooks/instagram", "ig")}
                  className="p-2 hover:bg-muted rounded-lg transition-colors shrink-0"
                >
                  {copiedKey === "ig" ? <Check className="w-4 h-4 text-green-500" /> : <Copy className="w-4 h-4 text-muted-foreground" />}
                </button>
              </div>
              <p className="text-xs text-muted-foreground">اذهب إلى Meta for Developers → Webhooks → Instagram → أضف هذا الرابط</p>
            </div>

            {/* Salla */}
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-muted-foreground">Salla Webhook URL</label>
              <div className="flex items-center gap-2">
                <code className="flex-1 text-xs bg-muted px-3 py-2 rounded-lg font-mono text-foreground overflow-x-auto" dir="ltr">
                  {typeof window !== "undefined" ? `${window.location.origin.replace("3000", "8000")}/api/v1/webhooks/salla` : "https://api.radd.ai/api/v1/webhooks/salla"}
                </code>
                <button
                  onClick={() => copyToClipboard("/api/v1/webhooks/salla", "salla")}
                  className="p-2 hover:bg-muted rounded-lg transition-colors shrink-0"
                >
                  {copiedKey === "salla" ? <Check className="w-4 h-4 text-green-500" /> : <Copy className="w-4 h-4 text-muted-foreground" />}
                </button>
              </div>
            </div>

            {/* Zid */}
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-muted-foreground">Zid Webhook URL</label>
              <div className="flex items-center gap-2">
                <code className="flex-1 text-xs bg-muted px-3 py-2 rounded-lg font-mono text-foreground overflow-x-auto" dir="ltr">
                  {typeof window !== "undefined" ? `${window.location.origin.replace("3000", "8000")}/api/v1/webhooks/zid` : "https://api.radd.ai/api/v1/webhooks/zid"}
                </code>
                <button
                  onClick={() => copyToClipboard("/api/v1/webhooks/zid", "zid")}
                  className="p-2 hover:bg-muted rounded-lg transition-colors shrink-0"
                >
                  {copiedKey === "zid" ? <Check className="w-4 h-4 text-green-500" /> : <Copy className="w-4 h-4 text-muted-foreground" />}
                </button>
              </div>
              <p className="text-xs text-muted-foreground">اذهب إلى لوحة Zid → الإعدادات → Webhooks → أضف هذا الرابط</p>
            </div>

            <div className="text-xs text-muted-foreground bg-muted/50 rounded-lg p-3">
              <strong>Verify Token:</strong>{" "}
              <code className="font-mono" dir="ltr">radd-webhook-verify</code>
              {" "}— استخدمه في خانة &quot;Verify Token&quot; عند إعداد Meta Webhooks
            </div>
          </CardContent>
        </Card>

        {/* Mobile App */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <Smartphone className="h-4 w-4 text-indigo-500" />
              تطبيق رَدّ للجوال
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="text-sm text-muted-foreground">
              تابع محادثاتك وردود العملاء وتنبيهات التصعيد في أي وقت من هاتفك.
            </p>
            <div className="grid grid-cols-2 gap-3">
              <div className="flex flex-col items-center gap-2 p-4 bg-muted/50 rounded-xl border border-border">
                <div className="text-3xl">🍎</div>
                <p className="text-sm font-medium">iOS (App Store)</p>
                <Badge variant="secondary" className="text-xs">قريباً</Badge>
              </div>
              <div className="flex flex-col items-center gap-2 p-4 bg-muted/50 rounded-xl border border-border">
                <div className="text-3xl">🤖</div>
                <p className="text-sm font-medium">Android (Play Store)</p>
                <Badge variant="secondary" className="text-xs">قريباً</Badge>
              </div>
            </div>
            <div className="text-xs text-muted-foreground bg-blue-50 text-blue-700 rounded-lg p-3 border border-blue-200">
              💡 للتطوير والاختبار: نفّذ{" "}
              <code className="font-mono bg-blue-100 px-1 rounded" dir="ltr">cd apps/mobile && npx expo start</code>
              {" "}لتشغيل التطبيق محلياً على هاتفك بتطبيق Expo Go.
            </div>
          </CardContent>
        </Card>

        {/* Starter Packs */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <Layers className="h-4 w-4 text-primary" />
              باقات البداية السريعة
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="text-sm text-muted-foreground">
              احصل على قاعدة معرفة جاهزة وكلمات مفتاحية مُعدّة خصيصاً لقطاعك.
            </p>
            <div className="flex gap-2">
              <select
                value={starterSector}
                onChange={(e) => setStarterSector(e.target.value)}
                className="flex-1 px-3 py-2 text-sm border rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-primary/30"
              >
                {Object.entries(SECTOR_LABELS).map(([v, l]) => (
                  <option key={v} value={v}>{l}</option>
                ))}
              </select>
              <Button
                onClick={handleApplyStarterPack}
                disabled={starterApplying}
              >
                {starterApplying ? "جارٍ التطبيق..." : "تطبيق الباقة"}
              </Button>
            </div>
            {starterMsg && (
              <div className="text-sm text-green-700 bg-green-50 px-3 py-2 rounded-lg">
                {starterMsg}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Users — tab=users */}
        <Card id="settings-users">
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
