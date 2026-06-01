// Generate a self-managed RSA keypair for a GCP service account, using jose.
//
// Outputs (to argv[2], default cwd):
//   private_key.pem        PKCS#8 — we keep this; signs the JWT assertions.
//   public_key.pem         SPKI — informational.
//   private_key.jwk.json   JWK form of the private key.
//
// A self-signed X.509 cert (public_cert.pem) is made separately with openssl;
// that cert is what gets uploaded to the service account. Run inside a Node
// container (no local install) — see README.md.

import { generateKeyPair, exportPKCS8, exportSPKI, exportJWK } from 'jose'
import { mkdirSync, writeFileSync } from 'node:fs'
import { join } from 'node:path'

const outDir = process.argv[2] || '.'
mkdirSync(outDir, { recursive: true })

// RS256 / RSA-2048 — GCP verifies the JWT-bearer assertion against this key.
const { publicKey, privateKey } = await generateKeyPair('RS256', {
	modulusLength: 2048,
	extractable: true
})

writeFileSync(join(outDir, 'private_key.pem'), await exportPKCS8(privateKey))
writeFileSync(join(outDir, 'public_key.pem'), await exportSPKI(publicKey))
writeFileSync(
	join(outDir, 'private_key.jwk.json'),
	JSON.stringify(await exportJWK(privateKey), null, 2) + '\n'
)

console.log('wrote private_key.pem, public_key.pem, private_key.jwk.json to', outDir)
