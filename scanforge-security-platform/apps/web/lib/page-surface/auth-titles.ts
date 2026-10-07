export function getAuthPageTitle(path: string): string {
  switch (path) {
    case "sign-in": return "Sign in";
    case "sign-up": return "Create account";
    case "forgot-password": return "Reset password";
    case "reset-password": return "Set a new password";
    case "email-otp": return "Verify email";
    case "magic-link": return "Magic link";
    case "sign-out": return "Sign out";
    default: return "Sign in";
  }
}

export function getAuthPageDescription(path: string): string {
  switch (path) {
    case "sign-in": return "Sign in to review open findings and decide what to do with each one.";
    case "sign-up": return "Create an account, then connect a repository.";
    case "forgot-password": return "Enter the email on the account. A reset link is sent there.";
    case "reset-password": return "Choose a new password for this account.";
    case "email-otp": return "Enter the code from the email.";
    case "magic-link": return "Open the link in the email to finish signing in.";
    case "sign-out": return "You are signed out.";
    default: return "Sign in to continue.";
  }
}
