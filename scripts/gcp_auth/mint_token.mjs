// Mint a short-lived GCP access token for a service account, using jose.
//
// Self-signed JWT (RS256) → exchanged at the Google token endpoint via the
// JWT-bearer grant. The SA must already trust our public key (uploaded as a
// cert; GCP assigns the key id we pass as `kid`).
//
// Env:
//   GCP_PRIVATE_KEY_PATH  path to private_key.pem (PKCS#8)
//   GCP_SA_EMAIL          e.g. ezra-ai-developer@ezra-498021.iam.gserviceaccount.com
//   GCP_SA_KEY_ID         key id GCP assigned to the uploaded public cert (JWT `kid`)
//   GCP_SCOPE             default https://www.googleapis.com/auth/cloud-platform
//
// Prints the access token to stdout (so callers can capture it). Run inside a
// Node container — see README.md.

import { SignJWT, importPKCS8 } from 'jose'
import { readFileSync } from 'node:fs'

const keyPath = process.env.GCP_PRIVATE_KEY_PATH
const saEmail = process.env.GCP_SA_EMAIL
const kid = process.env.GCP_SA_KEY_ID
const scope = process.env.GCP_SCOPE || 'https://www.googleapis.com/auth/cloud-platform'

for (const [name, val] of [
	['GCP_PRIVATE_KEY_PATH', keyPath],
	['GCP_SA_EMAIL', saEmail],
	['GCP_SA_KEY_ID', kid]
]) {
	if (!val) {
		console.error(`missing required env: ${name}`)
		process.exit(2)
	}
}

const TOKEN_URI = 'https://oauth2.googleapis.com/token'
const now = Math.floor(Date.now() / 1000)
const key = await importPKCS8(readFileSync(keyPath, 'utf8'), 'RS256')

const assertion = await new SignJWT({ scope })
	.setProtectedHeader({ alg: 'RS256', typ: 'JWT', kid })
	.setIssuer(saEmail)
	.setSubject(saEmail)
	.setAudience(TOKEN_URI)
	.setIssuedAt(now)
	.setExpirationTime(now + 3600)
	.sign(key)

const resp = await fetch(TOKEN_URI, {
	method: 'POST',
	headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
	body: new URLSearchParams({
		grant_type: 'urn:ietf:params:oauth:grant-type:jwt-bearer',
		assertion
	})
})

const data = await resp.json()
if (!resp.ok) {
	console.error('token exchange failed:', JSON.stringify(data))
	process.exit(1)
}
process.stdout.write(data.access_token)
