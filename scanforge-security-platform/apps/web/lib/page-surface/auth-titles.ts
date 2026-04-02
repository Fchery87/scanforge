export function getAuthPageTitle(path: string): string {
  switch (path) {
    case "sign-in": return "Sign In";
    case "sign-up": return "Create Account";
    case "forgot-password": return "Reset Password";
    case "reset-password": return "Set New Password";
    case "email-otp": return "Verify Email";
    case "magic-link": return "Magic Link";
    case "sign-out": return "Sign Out";
    default: return "Authentication";
  }
}

export function getAuthPageDescription(path: string): string {
  switch (path) {
    case "sign-in": return "Access your ScanForge workspace to review findings, run scans, and manage security posture.";
    case "sign-up": return "Create your ScanForge account to start securing your codebase.";
    case "forgot-password": return "Enter your email to receive a password reset link.";
    case "reset-password": return "Set a new secure password for your account.";
    case "email-otp": return "Enter the verification code sent to your email.";
    case "magic-link": return "Check your email for a secure login link.";
    case "sign-out": return "You have been signed out successfully.";
    default: return "Authenticate to access your ScanForge workspace.";
  }
}
