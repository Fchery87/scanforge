export type PageState =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "empty" }
  | { kind: "ready" };

export interface PageStateInput {
  loading: boolean;
  error?: string | null;
  itemCount: number;
}

export function derivePageState(input: PageStateInput): PageState {
  if (input.loading) {
    return { kind: "loading" };
  }
  if (input.error) {
    return { kind: "error", message: input.error };
  }
  if (input.itemCount === 0) {
    return { kind: "empty" };
  }
  return { kind: "ready" };
}
