# Scanner Binary Setup

## Trivy

Fix for Linux Mint — use `noble` (underlying Ubuntu codename) instead of `zara`:

```bash
echo "deb [signed-by=/usr/share/keyrings/trivy.gpg] https://aquasecurity.github.io/trivy-repo/deb noble main" | sudo tee /etc/apt/sources.list.d/trivy.list
sudo apt-get update && sudo apt-get install trivy -y
```

Verify: `trivy --version`

## Gitleaks

Go install had a module path mismatch. Download binary instead:

```bash
GITLEAKS_VERSION=8.30.1
wget https://github.com/gitleaks/gitleaks/releases/download/v${GITLEAKS_VERSION}/gitleaks_${GITLEAKS_VERSION}_linux_x64.tar.gz
tar -xzf gitleaks_${GITLEAKS_VERSION}_linux_x64.tar.gz
sudo mv gitleaks /usr/local/bin/
```

Verify: `gitleaks version`

## OSV-Scanner

```bash
wget https://github.com/google/osv-scanner/releases/download/v1.9.1/osv-scanner_linux_amd64
chmod +x osv-scanner_linux_amd64
sudo mv osv-scanner_linux_amd64 /usr/local/bin/osv-scanner
```

Verify: `osv-scanner --version`

## Verify All

```bash
trivy --version && gitleaks version && osv-scanner --version
```
