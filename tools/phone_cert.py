"""Keep an HTTPS certificate in a LedFx config directory, for the phone remote.

Usage:
    python tools/phone_cert.py <config_dir>

Phone browsers only hand motion sensors to secure pages, so the /phone remote
needs LedFx's HTTPS port, which serves <config_dir>/ssl/fullchain.pem and
privkey.pem. This writes them, signed by the local authority in
<config_dir>/ssl/ca.crt and ca.key: an existing one is reused (a phone that
already trusts it needs nothing new), otherwise one is created. Either way the
authority may only vouch for private addresses and this PC's names, so a phone
that trusts it cannot be fooled about any Internet site. The phone downloads it
from /phone/ca.crt.

The certificate is reissued when this PC gets a new LAN address or nears
expiry; otherwise the run changes nothing, so the launcher calls it every time.
"""

import datetime as dt
import ipaddress
import socket
import sys
from pathlib import Path

import psutil
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

PRIVATE_NETS = [
    ipaddress.ip_network(net)
    for net in ("127.0.0.0/8", "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16")
]
# Apple refuses server certificates valid for more than 825 days
LEAF_DAYS = 397
RENEW_BEFORE = dt.timedelta(days=30)


def host_names(hostname: str) -> list[str]:
    return list(
        dict.fromkeys([hostname.lower(), f"{hostname.lower()}.local", "localhost"])
    )


def lan_ips() -> list[str]:
    """This PC's private IPv4 addresses on interfaces that are up."""
    stats = psutil.net_if_stats()
    ips = ["127.0.0.1"]
    for interface, addresses in psutil.net_if_addrs().items():
        if interface in stats and not stats[interface].isup:
            continue
        for address in addresses:
            if address.family != socket.AF_INET:
                continue
            ip = ipaddress.ip_address(address.address)
            if any(ip in net for net in PRIVATE_NETS) and not ip.is_link_local:
                ips.append(address.address)
    return list(dict.fromkeys(ips))


def write_key(path: Path, key: ec.EllipticCurvePrivateKey) -> None:
    path.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )


def key_usage(sign_certificates: bool) -> x509.KeyUsage:
    return x509.KeyUsage(
        digital_signature=True,
        key_cert_sign=sign_certificates,
        crl_sign=sign_certificates,
        content_commitment=False,
        key_encipherment=False,
        data_encipherment=False,
        key_agreement=False,
        encipher_only=False,
        decipher_only=False,
    )


def make_authority(
    hostname: str,
) -> tuple[ec.EllipticCurvePrivateKey, x509.Certificate]:
    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name(
        [
            x509.NameAttribute(NameOID.COMMON_NAME, f"LedFx phone CA ({hostname})"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "LedFx (local)"),
        ]
    )
    now = dt.datetime.now(dt.UTC)
    permitted: list[x509.GeneralName] = [x509.DNSName(n) for n in host_names(hostname)]
    permitted += [x509.IPAddress(net) for net in PRIVATE_NETS]
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - dt.timedelta(minutes=5))
        .not_valid_after(now + dt.timedelta(days=3650))
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
        .add_extension(key_usage(sign_certificates=True), critical=True)
        .add_extension(
            x509.NameConstraints(permitted_subtrees=permitted, excluded_subtrees=None),
            critical=True,
        )
        .add_extension(
            x509.SubjectKeyIdentifier.from_public_key(key.public_key()), critical=False
        )
        .sign(key, hashes.SHA256())
    )
    return key, cert


def make_leaf(
    ca_key: ec.EllipticCurvePrivateKey,
    ca_cert: x509.Certificate,
    hostname: str,
    ips: list[str],
) -> tuple[ec.EllipticCurvePrivateKey, x509.Certificate]:
    key = ec.generate_private_key(ec.SECP256R1())
    now = dt.datetime.now(dt.UTC)
    san: list[x509.GeneralName] = [x509.DNSName(n) for n in host_names(hostname)]
    san += [x509.IPAddress(ipaddress.ip_address(ip)) for ip in ips]
    cert = (
        x509.CertificateBuilder()
        .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, hostname)]))
        .issuer_name(ca_cert.subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - dt.timedelta(minutes=5))
        .not_valid_after(now + dt.timedelta(days=LEAF_DAYS))
        .add_extension(x509.SubjectAlternativeName(san), critical=False)
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(key_usage(sign_certificates=False), critical=True)
        .add_extension(
            x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=False
        )
        .add_extension(
            x509.SubjectKeyIdentifier.from_public_key(key.public_key()), critical=False
        )
        .add_extension(
            x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()),
            critical=False,
        )
        .sign(ca_key, hashes.SHA256())
    )
    return key, cert


def leaf_is_current(
    leaf: x509.Certificate, ca_cert: x509.Certificate, hostname: str, ips: list[str]
) -> bool:
    if leaf.issuer != ca_cert.subject:
        return False
    if leaf.not_valid_after_utc - dt.datetime.now(dt.UTC) < RENEW_BEFORE:
        return False
    san = leaf.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
    have_ips = {str(ip) for ip in san.get_values_for_type(x509.IPAddress)}
    have_names = set(san.get_values_for_type(x509.DNSName))
    return set(ips) <= have_ips and set(host_names(hostname)) <= have_names


def ensure(config_dir: Path) -> str:
    """Make sure the certificate is in place; returns what was done."""
    ssl_dir = config_dir / "ssl"
    ssl_dir.mkdir(parents=True, exist_ok=True)
    hostname = socket.gethostname()
    ips = lan_ips()
    ca_key_path, ca_cert_path = ssl_dir / "ca.key", ssl_dir / "ca.crt"
    key_path, chain_path = ssl_dir / "privkey.pem", ssl_dir / "fullchain.pem"

    if ca_key_path.exists() and ca_cert_path.exists():
        loaded = serialization.load_pem_private_key(
            ca_key_path.read_bytes(), password=None
        )
        if not isinstance(loaded, ec.EllipticCurvePrivateKey):
            raise SystemExit(f"{ca_key_path} is not an EC key")
        ca_key = loaded
        ca_cert = x509.load_pem_x509_certificate(ca_cert_path.read_bytes())
    else:
        ca_key, ca_cert = make_authority(hostname)
        write_key(ca_key_path, ca_key)
        ca_cert_path.write_bytes(ca_cert.public_bytes(serialization.Encoding.PEM))

    if key_path.exists() and chain_path.exists():
        leaf = x509.load_pem_x509_certificate(chain_path.read_bytes())
        if leaf_is_current(leaf, ca_cert, hostname, ips):
            return "certificate up to date"
    key, leaf = make_leaf(ca_key, ca_cert, hostname, ips)
    write_key(key_path, key)
    # The full chain, so a phone that trusts the authority can build the path
    chain_path.write_bytes(
        leaf.public_bytes(serialization.Encoding.PEM)
        + ca_cert.public_bytes(serialization.Encoding.PEM)
    )
    return f"certificate issued for {', '.join(ips)}"


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    print(ensure(Path(sys.argv[1])))
