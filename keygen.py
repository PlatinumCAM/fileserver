#!/usr/bin/env python3
"""
Génération d'une clé RSA et d'un certificat autosigné en Python
- key.pem : clé privée
- cert.pem : certificat autosigné
"""

import datetime

from cryptography import x509
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

# 1. Génération de la clé privée
key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

# 2. Informations du sujet et de l’émetteur (identiques car autosigné)
subject = issuer = x509.Name([
    x509.NameAttribute(NameOID.COUNTRY_NAME, u"FR"),
    x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, u"IDF"),
    x509.NameAttribute(NameOID.LOCALITY_NAME, u"Paris"),
    x509.NameAttribute(NameOID.ORGANIZATION_NAME, u"MonOrganisation"),
    x509.NameAttribute(NameOID.COMMON_NAME, u"localhost"),
])

# 3. Construction du certificat
cert = (
    x509.CertificateBuilder()
    .subject_name(subject)
    .issuer_name(issuer)
    .public_key(key.public_key())
    .serial_number(x509.random_serial_number())
    .not_valid_before(datetime.datetime.utcnow())
    .not_valid_after(datetime.datetime.utcnow() + datetime.timedelta(days=365))
    .add_extension(x509.SubjectAlternativeName([x509.DNSName(u"localhost")]), critical=False)
    .sign(key, hashes.SHA256())
)

# 4. Sauvegarde de la clé privée
with open("key.pem", "wb") as f:
    f.write(
        key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )

# 5. Sauvegarde du certificat
with open("cert.pem", "wb") as f:
    f.write(cert.public_bytes(serialization.Encoding.PEM))

print("✅ Fichiers générés : cert.pem et key.pem")
