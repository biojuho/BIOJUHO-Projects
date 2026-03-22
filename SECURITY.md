# Security Policy

## Supported Versions

Currently supported versions for security updates:

| Version | Supported          |
| ------- | ------------------ |
| main    | :white_check_mark: |
| < 1.0   | :x:                |

## Reporting a Vulnerability

**Please do NOT report security vulnerabilities through public GitHub issues.**

Instead, please report them via:
- **GitHub Security Advisory**: https://github.com/biojuho/BIOJUHO-Projects/security/advisories/new
- **Email**: security@example.com (if you cannot use GitHub Security Advisory)

### Response Timeline:
- **48 hours**: Initial response confirming receipt
- **1 week**: Assessment and triage
- **2 weeks**: Fix development (for critical issues)
- **4 weeks**: Fix deployment and disclosure

### What to include in your report:
- **Type of vulnerability** (e.g., SQL injection, XSS, insecure deserialization)
- **Full paths** of source file(s) related to the vulnerability
- **Location** of the affected source code (tag/branch/commit or direct URL)
- **Step-by-step instructions** to reproduce the issue
- **Proof-of-concept or exploit code** (if possible)
- **Impact** of the vulnerability (what an attacker could achieve)

### What to expect:
1. We will acknowledge your report within 48 hours
2. We will send a more detailed response within 7 days
3. We will keep you informed of our progress
4. We will credit you in our security advisory (unless you prefer to remain anonymous)

## Security Features

This project implements multiple layers of security:

### 1. Automated Secret Detection
- **GitHub Secret Scanning**: Detects 200+ types of credentials
- **Push Protection**: Prevents pushing secrets to GitHub
- **Pre-commit Hooks**: Local Gitleaks scanning before commit

### 2. Dependency Management
- **Dependabot Alerts**: Automated vulnerability detection
- **Dependabot Security Updates**: Automated PR creation for fixes
- **Version Updates**: Weekly dependency update checks

### 3. Code Analysis
- **CodeQL**: Static analysis for security vulnerabilities
  - SQL injection detection
  - XSS vulnerability detection
  - Insecure deserialization detection
  - Path traversal detection
- **Pre-commit Hooks**: Ruff linting + security checks

### 4. Runtime Protection
- **Environment Variables**: All secrets stored in `.env` (gitignored)
- **API Key Rotation**: Quarterly rotation schedule
- **Rate Limiting**: Implemented for all public endpoints

## Security Best Practices

### For Developers

1. **Never commit sensitive data**
   ```bash
   # ✅ Good: Use environment variables
   api_key = os.getenv("OPENAI_API_KEY")

   # ❌ Bad: Hardcoded secrets
   api_key = "sk-proj-abc123..."
   ```

2. **Keep dependencies updated**
   ```bash
   # Check for outdated packages weekly
   pip list --outdated
   npm outdated

   # Review and merge Dependabot PRs promptly
   ```

3. **Follow secure coding guidelines**
   - **Input validation**: Sanitize all user inputs
   - **Parameterized queries**: Never use string concatenation for SQL
   - **HTTPS only**: All external API calls must use HTTPS
   - **Principle of least privilege**: Grant minimal permissions

4. **Code review process**
   - All PRs must be reviewed by at least one other developer
   - Security-sensitive changes require review from security team
   - Use GitHub Code Scanning suggestions

### For DevOps/Deployment

1. **Environment separation**
   - Development: `.env.development`
   - Staging: `.env.staging`
   - Production: `.env.production`

2. **Secret management**
   - Use GitHub Secrets for CI/CD
   - Rotate secrets quarterly
   - Never log secrets

3. **Access control**
   - Enable 2FA for all GitHub accounts
   - Use SSH keys (not passwords) for Git
   - Review team access quarterly

## Security Checklist

Before deploying to production:

### Critical Items
- [ ] All secrets in environment variables (not hardcoded)
- [ ] Pre-commit hooks installed (`pre-commit install`)
- [ ] GitHub Secret Scanning enabled
- [ ] GitHub Push Protection enabled
- [ ] Dependabot alerts enabled
- [ ] CodeQL analysis enabled
- [ ] Branch protection rules configured
- [ ] Security.md file present

### Recommended Items
- [ ] 2FA enabled for all team members
- [ ] Security policy documented and shared
- [ ] Incident response plan in place
- [ ] Regular security audits scheduled (monthly)
- [ ] Dependency updates automated (Dependabot)
- [ ] HTTPS enforced for all endpoints
- [ ] API rate limiting configured
- [ ] Logging and monitoring active

## Incident Response Plan

If a security incident is discovered:

### Phase 1: Detection & Assessment (0-2 hours)
1. **Detect**: Incident reported or auto-detected
2. **Notify**: Alert security team immediately
3. **Assess**: Determine severity (Critical/High/Medium/Low)

### Phase 2: Containment (2-4 hours)
1. **Isolate**: Disable affected systems/API keys
2. **Document**: Record all actions taken
3. **Communicate**: Notify stakeholders based on severity

### Phase 3: Eradication (4-24 hours)
1. **Root cause**: Identify how the breach occurred
2. **Remove**: Eliminate vulnerability from all systems
3. **Verify**: Confirm threat is neutralized

### Phase 4: Recovery (24-48 hours)
1. **Restore**: Bring systems back online
2. **Monitor**: Enhanced monitoring for 7 days
3. **Test**: Verify all functionality works correctly

### Phase 5: Post-Incident (48-72 hours)
1. **Review**: Conduct post-mortem meeting
2. **Document**: Write incident report
3. **Improve**: Update security practices
4. **Disclose**: Public disclosure (if applicable)

### Severity Levels

| Severity | Response Time | Examples |
|----------|--------------|----------|
| **Critical** | 1 hour | Production data breach, active exploitation |
| **High** | 4 hours | Exposed API keys, SQL injection vulnerability |
| **Medium** | 24 hours | XSS vulnerability, outdated dependencies |
| **Low** | 1 week | Minor information disclosure, low-impact bugs |

## Security Contacts

- **Primary Contact**: security@example.com
- **Backup Contact**: admin@example.com
- **GitHub Security Advisory**: https://github.com/biojuho/BIOJUHO-Projects/security/advisories

## Security Training

All team members must complete:
1. **Onboarding Security Training** (Week 1)
2. **Secure Coding Practices** (Month 1)
3. **Annual Security Refresher** (Yearly)

## Compliance

This project adheres to:
- **OWASP Top 10** security practices
- **CWE Top 25** vulnerability mitigation
- **NIST Cybersecurity Framework** guidelines

## Security Audit Log

| Date | Type | Findings | Status |
|------|------|----------|--------|
| 2026-03-22 | System Audit | API keys removed from code, Pre-commit hooks added | ✅ Complete |
| TBD | Penetration Test | Scheduled for Q2 2026 | ⏳ Pending |
| TBD | Dependency Audit | Quarterly review | ⏳ Pending |

## References

- [GitHub Security Best Practices](https://docs.github.com/en/code-security/getting-started/securing-your-repository)
- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [CWE Top 25](https://cwe.mitre.org/top25/archive/2023/2023_top25_list.html)
- [Pre-commit Hooks Setup Guide](docs/PRE_COMMIT_SETUP.md)
- [GitHub Security Setup Guide](docs/GITHUB_SECURITY_SETUP.md)

---

**Last Updated**: 2026-03-22
**Next Review**: 2026-06-22
