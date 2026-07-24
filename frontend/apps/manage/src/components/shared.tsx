// Deliberately plain styling — Feature 9's design gate restyles the console.
export const inputClass =
  "w-full rounded border border-stone-300 bg-white px-3 py-2 text-sm focus:outline-none focus:ring-1";
export const primaryButtonClass =
  "rounded bg-stone-800 px-4 py-2 text-sm text-white disabled:opacity-50";
export const secondaryButtonClass =
  "rounded border border-stone-300 px-3 py-1.5 text-sm text-stone-700";
export const dangerButtonClass = "rounded border border-red-300 px-3 py-1.5 text-sm text-red-700";
export const labelClass = "mb-1 block text-sm font-medium";
export const cardClass = "rounded-lg border border-stone-200 bg-white p-5";

export function ErrorNotice({ message }: { message: string }) {
  return (
    <p role="alert" className="rounded border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-800">
      {message}
    </p>
  );
}

export function SavedNotice() {
  return (
    <p role="status" className="rounded border border-green-300 bg-green-50 px-3 py-2 text-sm text-green-800">
      נשמר בהצלחה
    </p>
  );
}

export function Loading() {
  return <p className="py-6 text-sm text-stone-500">טוען…</p>;
}
