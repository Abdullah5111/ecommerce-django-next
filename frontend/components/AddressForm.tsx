"use client";

import { useState } from "react";
import type { AddressInput } from "@/lib/api";

const COUNTRIES: { code: string; name: string }[] = [
  { code: "US", name: "United States" },
  { code: "CA", name: "Canada" },
  { code: "GB", name: "United Kingdom" },
  { code: "AU", name: "Australia" },
  { code: "DE", name: "Germany" },
  { code: "FR", name: "France" },
  { code: "IT", name: "Italy" },
  { code: "ES", name: "Spain" },
  { code: "NL", name: "Netherlands" },
  { code: "IN", name: "India" },
  { code: "PK", name: "Pakistan" },
  { code: "BD", name: "Bangladesh" },
  { code: "XX", name: "Other" },
];

const EMPTY: AddressInput = {
  label: "",
  recipient: "",
  phone: "",
  line1: "",
  line2: "",
  city: "",
  state: "",
  postal_code: "",
  country: "US",
  is_default_shipping: false,
};

type Props = {
  initial?: Partial<AddressInput>;
  onSubmit: (input: AddressInput) => Promise<void>;
  submitLabel: string;
  onCancel?: () => void;
};

export default function AddressForm({ initial, onSubmit, submitLabel, onCancel }: Props) {
  const [form, setForm] = useState<AddressInput>({ ...EMPTY, ...initial });
  const [errors, setErrors] = useState<Partial<Record<keyof AddressInput, string>>>({});
  const [submitting, setSubmitting] = useState(false);

  const setField = <K extends keyof AddressInput>(key: K, value: AddressInput[K]) => {
    setForm((prev) => ({ ...prev, [key]: value }));
    if (errors[key]) setErrors((prev) => ({ ...prev, [key]: undefined }));
  };

  const validate = (): boolean => {
    const e: Partial<Record<keyof AddressInput, string>> = {};
    if (!form.recipient.trim()) e.recipient = "Required";
    if (!form.line1.trim()) e.line1 = "Required";
    if (!form.city.trim()) e.city = "Required";
    if (!form.postal_code.trim()) e.postal_code = "Required";
    if (!form.country.trim()) e.country = "Required";
    setErrors(e);
    return Object.keys(e).length === 0;
  };

  const handleSubmit = async (ev: React.FormEvent) => {
    ev.preventDefault();
    if (!validate()) return;
    setSubmitting(true);
    try {
      await onSubmit(form);
    } finally {
      setSubmitting(false);
    }
  };

  const inputCls = "w-full border border-zinc-300 rounded p-3 text-sm";
  const labelCls = "block text-xs font-medium text-zinc-600 mb-1";
  const errCls = "text-xs text-red-600 mt-1";

  return (
    <form onSubmit={handleSubmit} className="space-y-3 bg-white border border-zinc-200 rounded p-4">
      <div>
        <label className={labelCls}>Label (e.g. Home, Work)</label>
        <input
          className={inputCls}
          value={form.label}
          onChange={(e) => setField("label", e.target.value)}
        />
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className={labelCls}>Recipient *</label>
          <input
            className={inputCls}
            value={form.recipient}
            onChange={(e) => setField("recipient", e.target.value)}
          />
          {errors.recipient && <p className={errCls}>{errors.recipient}</p>}
        </div>
        <div>
          <label className={labelCls}>Phone</label>
          <input
            className={inputCls}
            value={form.phone}
            onChange={(e) => setField("phone", e.target.value)}
          />
        </div>
      </div>
      <div>
        <label className={labelCls}>Address line 1 *</label>
        <input
          className={inputCls}
          value={form.line1}
          onChange={(e) => setField("line1", e.target.value)}
        />
        {errors.line1 && <p className={errCls}>{errors.line1}</p>}
      </div>
      <div>
        <label className={labelCls}>Address line 2</label>
        <input
          className={inputCls}
          value={form.line2}
          onChange={(e) => setField("line2", e.target.value)}
        />
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className={labelCls}>City *</label>
          <input
            className={inputCls}
            value={form.city}
            onChange={(e) => setField("city", e.target.value)}
          />
          {errors.city && <p className={errCls}>{errors.city}</p>}
        </div>
        <div>
          <label className={labelCls}>State / Province</label>
          <input
            className={inputCls}
            value={form.state}
            onChange={(e) => setField("state", e.target.value)}
          />
        </div>
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className={labelCls}>Postal code *</label>
          <input
            className={inputCls}
            value={form.postal_code}
            onChange={(e) => setField("postal_code", e.target.value)}
          />
          {errors.postal_code && <p className={errCls}>{errors.postal_code}</p>}
        </div>
        <div>
          <label className={labelCls}>Country *</label>
          <select
            className={inputCls}
            value={form.country}
            onChange={(e) => setField("country", e.target.value)}
          >
            {COUNTRIES.map((c) => (
              <option key={c.code} value={c.code}>
                {c.name}
              </option>
            ))}
          </select>
          {errors.country && <p className={errCls}>{errors.country}</p>}
        </div>
      </div>
      <label className="flex items-center gap-2 text-sm text-zinc-700">
        <input
          type="checkbox"
          checked={!!form.is_default_shipping}
          onChange={(e) => setField("is_default_shipping", e.target.checked)}
        />
        Set as default shipping address
      </label>
      <div className="flex items-center gap-3 pt-1">
        <button
          type="submit"
          disabled={submitting}
          className="bg-black text-white py-2 px-4 rounded text-sm font-medium disabled:opacity-60"
        >
          {submitting ? "Saving…" : submitLabel}
        </button>
        {onCancel && (
          <button
            type="button"
            onClick={onCancel}
            className="text-sm text-zinc-600 hover:underline"
          >
            Cancel
          </button>
        )}
      </div>
    </form>
  );
}
