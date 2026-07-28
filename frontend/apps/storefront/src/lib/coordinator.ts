// The IS 5568 §35 accessibility coordinator.
//
// One constant for every tenant — the PLATFORM OPERATOR, not the boutique owner
// (decided: the boutique has no accessibility remit; the platform builds and
// operates the site). Until the operator supplies these, it stays null and the
// statement falls back to the boutique's own contact, which is a real reachable
// channel and is legally coherent because the boutique is the service provider.
//
// A placeholder must never render: a statement page that declares conformance
// while showing «fill this in» is itself the non-conformance it declares against,
// and it ships a dead mailto: to every visitor. Hence null, not a dummy string.
//
// TODO(launch blocker): fill this in before the pilot goes live.
export interface AccessibilityCoordinator {
  name: string;
  role: string;
  phone: string;
  email: string;
}

export const ACCESSIBILITY_COORDINATOR: AccessibilityCoordinator | null = null;
