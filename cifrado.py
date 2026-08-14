# -*- coding: utf-8 -*-
"""Cifrado ligero SIN dependencias externas:
   - ChaCha20 (RFC 8439) para cifrar el contenido
   - PBKDF2-HMAC-SHA256 (200.000 iteraciones) para derivar la clave
   - HMAC-SHA256 para detectar clave incorrecta o archivo alterado

Formato del archivo cifrado:
   [salt 16 bytes][nonce 12 bytes][cifrado...][hmac 32 bytes]
"""

import hashlib
import hmac
import os
import struct

_CTA, _CTB, _CTC, _CTD = 0x61707865, 0x3320646E, 0x79622D32, 0x6B206574
ITERACIONES = 200_000


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


def cifrar_archivo(ruta, datos_bytes, passphrase):
    salt = os.urandom(16)
    nonce = os.urandom(12)
    clave = derivar_clave(passphrase, salt)
    cifrado = chacha20_xor(datos_bytes, clave[:32], nonce)
    tag = hmac.new(clave[32:], salt + nonce + cifrado, hashlib.sha256).digest()
    with open(ruta, "wb") as f:
        f.write(salt + nonce + cifrado + tag)


def descifrar_archivo(ruta, passphrase):
    with open(ruta, "rb") as f:
        blob = f.read()
    if len(blob) < 60:
        raise ValueError("Archivo corrupto")
    salt, nonce = blob[:16], blob[16:28]
    cifrado, tag = blob[28:-32], blob[-32:]
    clave = derivar_clave(passphrase, salt)
    esperado = hmac.new(clave[32:], salt + nonce + cifrado,
                        hashlib.sha256).digest()
    if not hmac.compare_digest(tag, esperado):
        raise ValueError("Clave incorrecta o archivo alterado")
    return chacha20_xor(cifrado, clave[:32], nonce)


if __name__ == "__main__":
    # Vector de prueba oficial RFC 8439 (seccion 2.3.2)
    clave = bytes(range(32))
    texto = b"Ladies and Gentlemen of the class of '99: If I could offer you only one tip for the future, sunscreen would be it."

    # Vector 2.3.2: keystream del bloque (nonce 00000009 0000004a 00000000, contador 1)
    nonce_b = bytes.fromhex("000000090000004a00000000")
    esperado_b = bytes.fromhex(
        "10f1e7e4d13b5915500fdd1fa32071c4c7d1f4c733c068030422aa9ac3d46c4e"
        "d2826446079faa0914c2d705d98b02a2b5129cd1de164eb9cbd083e8a2503c4e")
    ks = chacha20_xor(bytes(64), clave, nonce_b, contador=1)
    ok_b = ks == esperado_b

    # Vector 2.4.2: cifrado del texto (nonce 00000000 0000004a 00000000, contador 1)
    nonce_c = bytes.fromhex("000000000000004a00000000")
    esperado_c = bytes.fromhex(
        "6e2e359a2568f98041ba0728dd0d6981e97e7aec1d4360c20a27afccfd9fae0b"
        "f91b65c5524733ab8f593dabcd62b3571639d624e65152ab8f530c359f0861d8"
        "07ca0dbf500d6a6156a38e088a22b65e52bc514d16ccf806818ce91ab7793736"
        "5af90bbf74a35be6b40b8eedf2785e42874d")
    ct = chacha20_xor(texto, clave, nonce_c, contador=1)
    ok_c = ct == esperado_c

    print("RFC 8439 2.3.2 (bloque):", "OK" if ok_b else "FALLO")
    print("RFC 8439 2.4.2 (cifrado):", "OK" if ok_c else "FALLO")
    assert ok_b and ok_c
    print("Implementacion de ChaCha20 correcta.")
