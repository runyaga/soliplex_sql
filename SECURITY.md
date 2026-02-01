# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.2.x   | :white_check_mark: |
| < 0.2   | :x:                |

## Reporting a Vulnerability

If you discover a security vulnerability, please report it privately:

1. **Do not** open a public issue
2. Email: runyaga@gmail.com
3. Include:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if any)

You can expect:
- Acknowledgment within 48 hours
- Status update within 7 days
- Credit in release notes (if desired)

## Security Best Practices

When using soliplex_sql:

1. **Use read-only mode** for untrusted queries
2. **Never commit** database credentials to version control
3. **Use environment variables** for connection strings
4. **Limit query results** with `max_rows` configuration
5. **Review queries** before enabling write access
