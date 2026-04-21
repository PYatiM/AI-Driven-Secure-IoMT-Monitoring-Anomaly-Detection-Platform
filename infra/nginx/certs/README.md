# TLS Certificates

Place TLS certificate files here before starting the stack in production:

- `fullchain.pem`
- `privkey.pem`

For local testing, you can generate a self-signed certificate:

```powershell
openssl req -x509 -nodes -newkey rsa:4096 `
  -keyout privkey.pem `
  -out fullchain.pem `
  -days 365 `
  -subj "/CN=localhost"
```

For production, use a trusted CA (for example Let's Encrypt) and keep private keys secure.

