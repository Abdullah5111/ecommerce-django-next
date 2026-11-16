"use client";

import Loading from "@/components/ui/Loading";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { api, type Me } from "@/lib/api";
import { auth } from "@/lib/auth";
import { useAuth } from "@/lib/useAuth";
import { useToast } from "@/lib/useToast";
import ChangePasswordForm from "@/components/ChangePasswordForm";
import ResendVerificationButton from "@/components/ResendVerificationButton";

function Badge({ ok, okText, badText }: { ok: boolean; okText: string; badText: string }) {
  return ok ? (
    <span className="text-xs px-2 py-0.5 rounded bg-green-100 text-green-800 border border-green-200">
      {okText}
    </span>
  ) : (
    <span className="text-xs px-2 py-0.5 rounded bg-amber-100 text-amber-800 border border-amber-200">
      {badText}
    </span>
  );
}

export default function SecurityPage() {
  const router = useRouter();
  const { user, loading } = useAuth();
  const [me, setMe] = useState<Me | null>(null);
  const [changingPassword, setChangingPassword] = useState(false);
  const { toast } = useToast();

  useEffect(() => {
    if (!loading && !user) router.push("/login?next=/account/security");
  }, [loading, user, router]);

  useEffect(() => {
    const token = auth.get();
    if (!user || !token) return;
    api.me(token).then(setMe).catch(() => {});
  }, [user]);

  if (loading || !user || !me) return <Loading />;

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Login &amp; security</h1>

      <div className="border rounded-lg divide-y">
        <Row label="Email" value={me.email}>
          <span className="flex items-center gap-2">
            <Badge ok={me.email_verified} okText="Verified" badText="Not verified" />
            {!me.email_verified && <ResendVerificationButton />}
          </span>
        </Row>
        <Row label="Phone" value={me.phone || "Not added"}>
          {me.phone ? (
            <Badge ok={me.phone_verified} okText="Verified" badText="Not verified" />
          ) : (
            <Link href="/account/profile" className="text-sm underline text-zinc-600">
              Add
            </Link>
          )}
        </Row>
        <Row label="Password" value="••••••••">
          {!changingPassword && (
            <button
              onClick={() => setChangingPassword(true)}
              className="text-sm underline text-zinc-600"
            >
              Change
            </button>
          )}
        </Row>
      </div>

      {changingPassword && (
        <div className="border rounded-lg p-4 mt-4">
          <ChangePasswordForm
            onDone={() => {
              setChangingPassword(false);
              toast("Password changed. Other devices have been signed out.", "success");
            }}
            onCancel={() => setChangingPassword(false)}
          />
        </div>
      )}

      <p className="text-sm text-zinc-500 mt-4">
        Manage your profile photo and personal details on the{" "}
        <Link href="/account/profile" className="underline">
          profile page
        </Link>
        .
      </p>
    </div>
  );
}

function Row({
  label,
  value,
  children,
}: {
  label: string;
  value: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex items-center justify-between p-4">
      <div className="min-w-0">
        <div className="text-sm text-zinc-500">{label}</div>
        <div className="font-medium truncate">{value}</div>
      </div>
      <div className="shrink-0 ml-3">{children}</div>
    </div>
  );
}
