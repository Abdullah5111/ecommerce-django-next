"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { api, type Me, type Gender } from "@/lib/api";
import { auth } from "@/lib/auth";
import { useAuth } from "@/lib/useAuth";
import { useToast } from "@/lib/useToast";
import Avatar from "@/components/Avatar";

const GENDERS: { value: Gender; label: string }[] = [
  { value: "", label: "Prefer not to specify" },
  { value: "female", label: "Female" },
  { value: "male", label: "Male" },
  { value: "nonbinary", label: "Non-binary" },
  { value: "prefer_not_to_say", label: "Prefer not to say" },
];

export default function ProfilePage() {
  const router = useRouter();
  const { user, loading, refresh } = useAuth();
  const { toast } = useToast();
  const fileRef = useRef<HTMLInputElement>(null);

  const [me, setMe] = useState<Me | null>(null);
  const [form, setForm] = useState({
    first_name: "",
    last_name: "",
    display_name: "",
    bio: "",
    date_of_birth: "",
    gender: "" as Gender,
  });
  const [saving, setSaving] = useState(false);

  // phone verification
  const [phoneInput, setPhoneInput] = useState("");
  const [codeSent, setCodeSent] = useState(false);
  const [code, setCode] = useState("");

  useEffect(() => {
    if (!loading && !user) router.push("/login?next=/account/profile");
  }, [loading, user, router]);

  const hydrate = (data: Me) => {
    setMe(data);
    setForm({
      first_name: data.first_name || "",
      last_name: data.last_name || "",
      display_name: data.display_name || "",
      bio: data.bio || "",
      date_of_birth: data.date_of_birth || "",
      gender: data.gender || "",
    });
    setPhoneInput(data.phone || "");
  };

  useEffect(() => {
    const token = auth.get();
    if (!user || !token) return;
    api.me(token).then(hydrate).catch(() => toast("Failed to load profile", "error"));
  }, [user]);

  const saveProfile = async (e: React.FormEvent) => {
    e.preventDefault();
    const token = auth.get();
    if (!token) return;
    setSaving(true);
    try {
      const updated = await api.updateMe(token, {
        ...form,
        date_of_birth: form.date_of_birth || null,
      });
      hydrate(updated);
      await refresh();
      toast("Profile saved", "success");
    } catch {
      toast("Could not save profile", "error");
    } finally {
      setSaving(false);
    }
  };

  const onPickAvatar = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const token = auth.get();
    if (!token) return;
    if (file.size > 2 * 1024 * 1024) {
      toast("Image must be 2 MB or smaller", "error");
      return;
    }
    try {
      const updated = await api.uploadAvatar(token, file);
      hydrate(updated);
      await refresh();
      toast("Photo updated", "success");
    } catch {
      toast("Upload failed", "error");
    } finally {
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  const removeAvatar = async () => {
    const token = auth.get();
    if (!token) return;
    try {
      await api.deleteAvatar(token);
      const fresh = await api.me(token);
      hydrate(fresh);
      await refresh();
      toast("Photo removed", "success");
    } catch {
      toast("Could not remove photo", "error");
    }
  };

  const sendCode = async () => {
    const token = auth.get();
    if (!token) return;
    try {
      await api.sendPhoneCode(token, phoneInput.trim());
      setCodeSent(true);
      toast("Verification code sent", "success");
    } catch {
      toast("Could not send code", "error");
    }
  };

  const verifyCode = async () => {
    const token = auth.get();
    if (!token) return;
    try {
      const updated = await api.verifyPhone(token, code.trim());
      hydrate(updated);
      setCodeSent(false);
      setCode("");
      toast("Phone verified", "success");
    } catch {
      toast("Invalid or expired code", "error");
    }
  };

  if (loading || !user || !me) return <p className="text-zinc-600">Loading…</p>;

  const displayName = form.display_name || form.first_name || user.username;

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Login &amp; profile</h1>

      {/* Avatar */}
      <section className="flex items-center gap-4 mb-8">
        <Avatar src={me.avatar} name={displayName} size={72} />
        <div className="flex flex-col gap-2">
          <input
            ref={fileRef}
            type="file"
            accept="image/*"
            onChange={onPickAvatar}
            className="hidden"
          />
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => fileRef.current?.click()}
              className="text-sm border rounded px-3 py-1.5 hover:border-zinc-400"
            >
              {me.avatar ? "Change photo" : "Upload photo"}
            </button>
            {me.avatar && (
              <button
                type="button"
                onClick={removeAvatar}
                className="text-sm text-zinc-500 hover:text-red-600 px-2"
              >
                Remove
              </button>
            )}
          </div>
          <span className="text-xs text-zinc-400">JPG or PNG, up to 2 MB.</span>
        </div>
      </section>

      {/* Profile fields */}
      <form onSubmit={saveProfile} className="space-y-4 mb-10">
        <div className="grid grid-cols-2 gap-3">
          <Field label="First name">
            <input
              className="w-full border rounded p-2.5"
              value={form.first_name}
              onChange={(e) => setForm({ ...form, first_name: e.target.value })}
            />
          </Field>
          <Field label="Last name">
            <input
              className="w-full border rounded p-2.5"
              value={form.last_name}
              onChange={(e) => setForm({ ...form, last_name: e.target.value })}
            />
          </Field>
        </div>
        <Field label="Display name">
          <input
            className="w-full border rounded p-2.5"
            placeholder="How your name appears publicly"
            maxLength={60}
            value={form.display_name}
            onChange={(e) => setForm({ ...form, display_name: e.target.value })}
          />
        </Field>
        <Field label="Bio">
          <textarea
            className="w-full border rounded p-2.5"
            rows={3}
            maxLength={280}
            value={form.bio}
            onChange={(e) => setForm({ ...form, bio: e.target.value })}
          />
        </Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Date of birth">
            <input
              type="date"
              className="w-full border rounded p-2.5"
              value={form.date_of_birth}
              onChange={(e) => setForm({ ...form, date_of_birth: e.target.value })}
            />
          </Field>
          <Field label="Gender">
            <select
              className="w-full border rounded p-2.5 bg-white"
              value={form.gender}
              onChange={(e) => setForm({ ...form, gender: e.target.value as Gender })}
            >
              {GENDERS.map((g) => (
                <option key={g.value} value={g.value}>
                  {g.label}
                </option>
              ))}
            </select>
          </Field>
        </div>
        <button
          disabled={saving}
          className="bg-black text-white py-2 px-4 rounded font-medium disabled:opacity-60"
        >
          {saving ? "Saving…" : "Save profile"}
        </button>
      </form>

      {/* Phone verification */}
      <section className="border-t pt-6">
        <h2 className="text-lg font-semibold mb-1">Phone number</h2>
        <p className="text-sm text-zinc-500 mb-3">
          {me.phone_verified ? (
            <span className="text-green-700">
              ✓ {me.phone} is verified
            </span>
          ) : (
            "Verify a phone number for order updates and account security."
          )}
        </p>
        <div className="flex gap-2 mb-3">
          <input
            className="flex-1 border rounded p-2.5"
            placeholder="+1 555 123 4567"
            value={phoneInput}
            onChange={(e) => setPhoneInput(e.target.value)}
          />
          <button
            type="button"
            onClick={sendCode}
            disabled={!phoneInput.trim()}
            className="border rounded px-4 hover:border-zinc-400 disabled:opacity-50"
          >
            Send code
          </button>
        </div>
        {codeSent && (
          <div className="flex gap-2">
            <input
              className="flex-1 border rounded p-2.5 tracking-widest"
              placeholder="6-digit code"
              inputMode="numeric"
              maxLength={6}
              value={code}
              onChange={(e) => setCode(e.target.value)}
            />
            <button
              type="button"
              onClick={verifyCode}
              disabled={code.trim().length !== 6}
              className="bg-black text-white rounded px-4 disabled:opacity-50"
            >
              Verify
            </button>
          </div>
        )}
      </section>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="block text-sm text-zinc-600 mb-1">{label}</span>
      {children}
    </label>
  );
}
