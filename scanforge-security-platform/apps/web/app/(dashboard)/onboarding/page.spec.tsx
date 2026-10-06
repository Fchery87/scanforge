import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import OnboardingPage from "./page";
import { api } from "@/lib/api";

vi.mock("next/navigation", () => ({
  useSearchParams: () => new URLSearchParams("org_id=org"),
  useRouter: () => ({ push: vi.fn() }),
}));
vi.mock("@/lib/api", () => ({ api: { github: { getInstallUrl: vi.fn() } } }));
vi.mock("@/lib/onboarding/checklist", () => ({
  loadOnboardingChecklist: async () => ({ user_id: "user", organization_id: "org", steps: [
    { id: "connect_github", label: "Connect GitHub", description: "Install the GitHub App.", completed: false, action_url: null },
  ] }),
}));

afterEach(() => { cleanup(); localStorage.clear(); vi.clearAllMocks(); });

it("shows GitHub connection failure and permits retry", async () => {
  vi.mocked(api.github.getInstallUrl).mockRejectedValue(new Error("Installation unavailable"));
  render(<OnboardingPage />);
  const button = await screen.findByRole("button", { name: "Connect GitHub" });
  fireEvent.click(button);
  expect(await screen.findByRole("alert")).toHaveTextContent("Installation unavailable");
  expect(button).toBeEnabled();
  fireEvent.click(button);
  expect(api.github.getInstallUrl).toHaveBeenCalledTimes(2);
  expect(api.github.getInstallUrl).toHaveBeenLastCalledWith("org");
});
