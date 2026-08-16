# -*- coding: utf-8 -*-
"""Cifrado ligero SIN dependencias externas - formato cebolla v2:

   - PBKDF2-HMAC-SHA256 (200.000 iteraciones) deriva la clave maestra
   - N capas de ChaCha20 (RFC 8439), N aleatorio entre 3 y 5
   - Cada capa usa una clave derivada de la capa anterior (cadena) y un
     nonce propio de 12 bytes
   - Las capas se aplican en orden ALEATORIO (la permutacion se guarda en
     la cabecera para poder pelarlas en orden inverso)
   - HMAC-SHA256 final: detecta clave incorrecta o archivo alterado
   - Compatibilidad: sigue leyendo el formato v1 anterior (la caja se
     migra a v2 automaticamente al abrirla)

Formato v2 del archivo:
   [MV2 3B][n 1B][orden n B][salt 16B][nonces 12*n B][cifrado...][hmac 32B]
"""

import hashlib
import hmac
import os
import secrets
import struct

VERSION = b"MV2"
MIN_CAPAS = 3
MAX_CAPAS = 5
ITERACIONES = 200_000

_CTA, _CTB, _CTC, _CTD = 0x61707865, 0x3320646E, 0x79622D32, 0x6B206574


def _rotl(v, c):
    return ((v << c) | (v >> (32 - c))) & 0xFFFFFFFF


def _qr(x, a, b, c, d):
    x[a] = (x[a] + x[b]) & 0xFFFFFFFF
    x[d] = _rotl(x[d] ^ x[a], 16)
    x[c] = (x[c] + x[d]) & 0xFFFFFFFF
    x[b] = _rotl(x[b] ^ x[c], 12)
    x[a] = (x[a] + x[b]) & 0xFFFFFFFF
    x[d] = _rotl(x[d] ^ x[a], 8)
    x[c] = (x[c] + x[d]) & 0xFFFFFFFF
    x[b] = _rotl(x[b] ^ x[c], 7)


def _bloque(clave, contador, nonce):
    """Genera un bloque de 64 bytes del keystream ChaCha20."""
    st = [_CTA, _CTB, _CTC, _CTD]
    st += list(struct.unpack("<4I", clave[0:16]))
    st += list(struct.unpack("<4I", clave[16:32]))
    st += [contador & 0xFFFFFFFF]  # RFC 8439: contador de 32 bits
    st += list(struct.unpack("<3I", nonce))
    w = list(st)
    for _ in range(10):
        _qr(w, 0, 4, 8, 12)
        _qr(w, 1, 5, 9, 13)
        _qr(w, 2, 6, 10, 14)
        _qr(w, 3, 7, 11, 15)
        _qr(w, 0, 5, 10, 15)
        _qr(w, 1, 6, 11, 12)
        _qr(w, 2, 7, 8, 13)
        _qr(w, 3, 4, 9, 14)
    return b"".join(struct.pack("<I", (st[i] + w[i]) & 0xFFFFFFFF)
                    for i in range(16))


def chacha20_xor(datos, clave, nonce, contador=0):
    """Aplica el keystream sobre los datos (clave de 32 bytes, nonce de 12)."""
    salida = bytearray()
    for i in range(0, len(datos), 64):
        bloque = _bloque(clave, contador + i // 64, nonce)
        trozo = datos[i:i + 64]
        salida += bytes(a ^ c for a, c in zip(trozo, bloque))
    return bytes(salida)


def derivar_clave(passphrase, salt):
    return hashlib.pbkdf2_hmac("sha256", passphrase.encode("utf-8"),
                               salt, ITERACIONES, dklen=64)


def _cadena_capas(clave_maestra, n):
    """Claves en cadena: la clave de cada capa depende de la anterior."""
    claves = []
    base = clave_maestra
    for i in range(1, n + 1):
        base = hmac.new(base, b"MailVault-capa-" + bytes([i]),
                        hashlib.sha256).digest()
        claves.append(base)
    return claves


def _plan_capas():
    """Numero de capas aleatorio (3-5) y orden de aplicacion aleatorio."""
    n = secrets.randbelow(MAX_CAPAS - MIN_CAPAS + 1) + MIN_CAPAS
    orden = list(range(n))
    for i in range(n - 1, 0, -1):
        j = secrets.randbelow(i + 1)
        orden[i], orden[j] = orden[j], orden[i]
    return n, orden


def cifrar_archivo(ruta, datos_bytes, passphrase):
    salt = os.urandom(16)
    maestro = derivar_clave(passphrase, salt)
    kc, kh = maestro[:32], maestro[32:]
    n, orden = _plan_capas()
    claves = _cadena_capas(kc, n)
    nonces = [os.urandom(12) for _ in range(n)]
    blob = datos_bytes
    for idx in orden:
        blob = chacha20_xor(blob, claves[idx], nonces[idx])
    cabecera = VERSION + bytes([n]) + bytes(orden) + salt + b"".join(nonces)
    tag = hmac.new(kh, cabecera + blob, hashlib.sha256).digest()
    with open(ruta, "wb") as f:
        f.write(cabecera + blob + tag)


def _validar_cabecera_v2(blob):
    if len(blob) < 3 + 1 + 1 + 16 + 12 + 32:
        raise ValueError("Archivo corrupto")
    n = blob[3]
    if not 1 <= n <= 8:
        raise ValueError("Archivo corrupto")
    if len(blob) < 3 + 1 + n + 16 + 12 * n + 32:
        raise ValueError("Archivo corrupto")


def descifrar_archivo(ruta, passphrase):
    with open(ruta, "rb") as f:
        blob_total = f.read()
    if len(blob_total) < 60:
        raise ValueError("Archivo corrupto")

    if blob_total[:3] == VERSION:
        # --- formato cebolla v2 ---
        _validar_cabecera_v2(blob_total)
        pos = 3
        n = blob_total[pos]
        pos += 1
        orden = list(blob_total[pos:pos + n])
        pos += n
        salt = blob_total[pos:pos + 16]
        pos += 16
        nonces = [blob_total[pos + 12 * i:pos + 12 * (i + 1)]
                  for i in range(n)]
        pos += 12 * n
        cifrado = blob_total[pos:-32]
        tag = blob_total[-32:]

        maestro = derivar_clave(passphrase, salt)
        kc, kh = maestro[:32], maestro[32:]
        esperado = hmac.new(kh, blob_total[:-32], hashlib.sha256).digest()
        if not hmac.compare_digest(tag, esperado):
            raise ValueError("Clave incorrecta o archivo alterado")

        claves = _cadena_capas(kc, n)
        blob = cifrado
        for idx in reversed(orden):  # pelar la cebolla en orden inverso
            blob = chacha20_xor(blob, claves[idx], nonces[idx])
        return blob

    # --- formato v1 (compatibilidad con la caja existente) ---
    salt, nonce = blob_total[:16], blob_total[16:28]
    cifrado, tag = blob_total[28:-32], blob_total[-32:]
    clave = derivar_clave(passphrase, salt)
    esperado = hmac.new(clave[32:], salt + nonce + cifrado,
                        hashlib.sha256).digest()
    if not hmac.compare_digest(tag, esperado):
        raise ValueError("Clave incorrecta o archivo alterado")
    return chacha20_xor(cifrado, clave[:32], nonce)


def formato_archivo(ruta):
    """Devuelve 'v2' (cebolla), 'v1' (antiguo) o None si no existe."""
    try:
        with open(ruta, "rb") as f:
            inicio = f.read(3)
    except OSError:
        return None
    if inicio == VERSION:
        return "v2"
    if inicio:
        return "v1"
    return None


if __name__ == "__main__":
    # Vectores oficiales RFC 8439 (el nucleo ChaCha20 no cambia)
    clave = bytes(range(32))
    texto = b"Ladies and Gentlemen of the class of '99: If I could offer you only one tip for the future, sunscreen would be it."

    nonce_b = bytes.fromhex("000000090000004a00000000")
    esperado_b = bytes.fromhex(
        "10f1e7e4d13b5915500fdd1fa32071c4c7d1f4c733c068030422aa9ac3d46c4e"
        "d2826446079faa0914c2d705d98b02a2b5129cd1de164eb9cbd083e8a2503c4e")
    assert chacha20_xor(bytes(64), clave, nonce_b, contador=1) == esperado_b

    nonce_c = bytes.fromhex("000000000000004a00000000")
    esperado_c = bytes.fromhex(
        "6e2e359a2568f98041ba0728dd0d6981e97e7aec1d4360c20a27afccfd9fae0b"
        "f91b65c5524733ab8f593dabcd62b3571639d624e65152ab8f530c359f0861d8"
        "07ca0dbf500d6a6156a38e088a22b65e52bc514d16ccf806818ce91ab7793736"
        "5af90bbf74a35be6b40b8eedf2785e42874d")
    assert chacha20_xor(texto, clave, nonce_c, contador=1) == esperado_c
    print("RFC 8439: OK")

    # Cebolla v2: redondeo + cabecera + capas aleatorias
    import tempfile
    ruta = os.path.join(tempfile.gettempdir(), "mailvault_test_v2.enc")
    datos = b'{"nombre": "Gmail", "correo": "yo@gmail.com"}'
    cifrar_archivo(ruta, datos, "mi-clave-123")
    with open(ruta, "rb") as f:
        blob = f.read()
    n = blob[3]
    assert blob[:3] == b"MV2" and 3 <= n <= 5
    print("v2: cabecera MV2, capas =", n, "-> OK")
    assert descifrar_archivo(ruta, "mi-clave-123") == datos
    print("v2: redondeo OK")
    try:
        descifrar_archivo(ruta, "clave-equivocada")
        raise SystemExit("ERROR: debio rechazar clave mala")
    except ValueError:
        print("v2: clave incorrecta rechazada OK")
    # manipulacion del archivo
    with open(ruta, "r+b") as f:
        f.seek(-20, 2)
        f.write(b"X")
    try:
        descifrar_archivo(ruta, "mi-clave-123")
        raise SystemExit("ERROR: debio detectar alteracion")
    except ValueError:
        print("v2: archivo alterado detectado OK")
    os.remove(ruta)

    # Compatibilidad v1
    ruta1 = os.path.join(tempfile.gettempdir(), "mailvault_test_v1.enc")
    salt1, nonce1 = os.urandom(16), os.urandom(12)
    k1 = derivar_clave("clave-vieja", salt1)
    ct1 = chacha20_xor(datos, k1[:32], nonce1)
    tag1 = hmac.new(k1[32:], salt1 + nonce1 + ct1, hashlib.sha256).digest()
    with open(ruta1, "wb") as f:
        f.write(salt1 + nonce1 + ct1 + tag1)
    assert formato_archivo(ruta1) == "v1"
    assert descifrar_archivo(ruta1, "clave-vieja") == datos
    print("v1: compatibilidad OK")
    os.remove(ruta1)

    print("CIFRADO CEBOLIA v2 VERIFICADO")
