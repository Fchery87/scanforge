import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import AuthPage, { generateStaticParams } from "./page";

vi.mock("next/navigation", () => ({ notFound: () => { throw new Error("Signup unavailable"); } }));
vi.mock("@/components/auth/auth-view-client", () => ({ AuthViewClient: ({ path }: { path: string }) => <div>{path}</div> }));

afterEach(cleanup);

it("denies direct signup requests and excludes signup from published pages", async () => {
  expect(generateStaticParams()).not.toContainEqual({ path: "sign-up" });
  await expect(AuthPage({ params: Promise.resolve({ path: "sign-up" }) })).rejects.toThrow("Signup unavailable");
});

it("explains invitation access on the sign-in page", async () => {
  render(await AuthPage({ params: Promise.resolve({ path: "sign-in" }) }));
  expect(screen.getByText(/Private beta access is by invitation/)).toBeInTheDocument();
});
