import { Input } from "./Input";
import type { InputProps } from "./Input";

// Native date/time inputs, styled through the shared Input. Israeli-week ordering
// is a composite concern (HoursTable/HoursSection), not the field's.
export function TimeField(props: Omit<InputProps, "type">) {
  return <Input type="time" {...props} />;
}

export function DateField(props: Omit<InputProps, "type">) {
  return <Input type="date" {...props} />;
}
