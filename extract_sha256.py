# -*- coding: utf-8 -*-
"""从一个 APK 里提取签名证书的 SHA-256 指纹(纯标准库,无需 Java/apksigner)。
支持 APK Signature Scheme v2(0x7109871a)和 v3(0xf05368c0)。
用法:python extract_sha256.py <apk路径>
"""
import sys, struct, hashlib

MAGIC = b"APK Sig Block 42"
V2_ID = 0x7109871a
V3_ID = 0xf05368c0


def find_signing_block(data):
    # APK 末尾的中央目录前面是签名块;块尾有 16 字节 magic,magic 前是 uint64 块大小
    idx = data.rfind(MAGIC)
    if idx < 0:
        raise SystemExit("没找到 APK 签名块(可能是仅 v1/JAR 签名)")
    size_end = struct.unpack_from("<Q", data, idx - 8)[0]   # 块大小(含尾部 size+magic)
    block_start = idx + 16 - size_end - 8                    # 回推到块首的 uint64 size 字段
    total = struct.unpack_from("<Q", data, block_start)[0]
    body = data[block_start + 8: block_start + 8 + total - 24 + 16]
    # body 是若干 ID-value 对,直到尾部 size(8)+magic(16);精确切到 magic 前
    return data[block_start + 8: idx - 8]


def iter_id_value(block):
    off = 0
    n = len(block)
    while off + 12 <= n:
        (pair_len,) = struct.unpack_from("<Q", block, off)   # 该对长度(含 4 字节 ID)
        off += 8
        if pair_len < 4 or off + pair_len > n + 0:
            break
        (pid,) = struct.unpack_from("<I", block, off)
        value = block[off + 4: off + pair_len]
        yield pid, value
        off += pair_len


def lp_u32(buf, off):
    """读一个 uint32 长度前缀的块,返回(内容bytes, 新off)"""
    (ln,) = struct.unpack_from("<I", buf, off)
    off += 4
    return buf[off: off + ln], off + ln


def first_cert_from_scheme(value):
    # value: uint32-len 的 signers 序列
    signers, _ = lp_u32(value, 0)
    # 第一个 signer
    signer, _ = lp_u32(signers, 0)
    # signer: signed_data | signatures | public_key
    signed_data, _ = lp_u32(signer, 0)
    # signed_data: digests | certificates | additional_attrs
    digests, off = lp_u32(signed_data, 0)
    certificates, off = lp_u32(signed_data, off)
    # certificates: 序列,每个 cert 是 uint32-len 的 DER
    cert_der, _ = lp_u32(certificates, 0)
    return cert_der


def main():
    if len(sys.argv) < 2:
        raise SystemExit("用法: python extract_sha256.py <apk路径>")
    with open(sys.argv[1], "rb") as f:
        data = f.read()
    block = find_signing_block(data)
    found = {}
    for pid, value in iter_id_value(block):
        if pid in (V2_ID, V3_ID):
            try:
                der = first_cert_from_scheme(value)
                found[pid] = der
            except Exception as e:
                print("解析 scheme 0x%08x 失败: %s" % (pid, e))
    if not found:
        raise SystemExit("没在签名块里找到 v2/v3 证书")
    # 优先用 v2(和 keytool 显示的一致);v2/v3 证书相同
    der = found.get(V2_ID) or found.get(V3_ID)
    sha256 = hashlib.sha256(der).hexdigest().upper()
    sha1 = hashlib.sha1(der).hexdigest().upper()
    fmt = lambda h: ":".join(h[i:i+2] for i in range(0, len(h), 2))
    print("SHA-256:", fmt(sha256))
    print("SHA-1:  ", fmt(sha1))


if __name__ == "__main__":
    main()
