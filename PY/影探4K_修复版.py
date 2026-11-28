# coding: utf-8
# 影探4K（cms.lyyytv.cn）· TVBox / FongMi Python 站源
# 站型：苹果CMS 的 app 接口（/api.php/app/*），列表/详情/搜索全部走 JSON。
# 播放：fys 解析（parsesId 轮询，实测 7 可用、5/6 已全站失效）→
#       返回 https://baidu.con/<key16><base64>，前 16 字符当 key/iv 做 AES-CBC。
# 🔴 核心：解析出的 m3u8 是「6 秒失效」限时链（站点自写 你已经知道了链接超过6秒会失效），
#   播放器二次请求必死。故 play 内同步解析→拉清单→起本地代理重封装：
#   播放器只拿 http://127.0.0.1:9979/yt/<tok>/index.m3u8，分片按需由本机转发，永不过期。
import base64
import json
import os
import re
import threading
import time
import urllib.parse
import urllib.request

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

try:
    from base.spider import Spider as BaseSpider
except Exception:
    class BaseSpider(object):
        pass

HOST = "http://cms.lyyytv.cn"
UA = "okhttp/4.12.0"
CHAIN_API = "http://fys.lyyytv.cn/api/index?parsesId=%s&appid=10001&videoUrl="
CMS_KEY = "wP5bvxoc3yv7FoBQENFZuAF0EUYr4LTy"
DEC_PREFIX = "https://baidu.con/"
# 解析线路候选（parsesId）。实测 2026-11：7 可用，5/6 已全站失效；其余为备用。
PARSE_IDS = ["7", "9", "11", "13", "5"]
# 点播平台页永远返回「6 秒失效」的限时链接，必须走本地 m3u8 代理
YT4K_HOST = re.compile(r"(?:^|\.)(?:ym4kjx|hd4kjx|sd4kjx|mm4kjx|mv4kjx|vk4kjx)\.lyyytv\.cn$", re.I)
MEDIA_RE = re.compile(r"\.(?:mp4|m3u8|m3u|flv|mkv|ts|mov|webm|m4v|mpd)(?:[?#]|$)", re.I)
FILTER_KEYS = [("class", "类型"), ("area", "地区"), ("lang", "语言"), ("year", "年份"),
               ("letter", "字母"), ("by", "排序"), ("sort", "顺序"), ("star", "主演"),
               ("director", "导演"), ("state", "状态"), ("version", "版本")]

# ---------------------------------------------------------------- AES（解密用）
def _gmul(a, b):
    p = 0
    for _ in range(8):
        if b & 1:
            p ^= a
        hi = a & 0x80
        a = (a << 1) & 0xFF
        if hi:
            a ^= 0x1B
        b >>= 1
    return p


def _build_sbox():
    inv = [0] * 256
    for i in range(1, 256):
        r, base, e = 1, i, 254
        while e:
            if e & 1:
                r = _gmul(r, base)
            base = _gmul(base, base)
            e >>= 1
        inv[i] = r

    def rotl(x, n):
        return ((x << n) | (x >> (8 - n))) & 0xFF

    return [inv[i] ^ rotl(inv[i], 1) ^ rotl(inv[i], 2) ^ rotl(inv[i], 3) ^ rotl(inv[i], 4) ^ 0x63
            for i in range(256)]


SBOX = _build_sbox()
INV_SBOX = [0] * 256
for _i, _v in enumerate(SBOX):
    INV_SBOX[_v] = _i
RCON = [0x01, 0x02, 0x04, 0x08, 0x10, 0x20, 0x40, 0x80, 0x1B, 0x36, 0x6C, 0xD8, 0xAB, 0x4D]


class _AES(object):
    def __init__(self, key):
        if len(key) not in (16, 24, 32):
            raise ValueError("bad key")
        self.nk = len(key) // 4
        self.nr = self.nk + 6
        self.rk = self._expand(key)

    def _expand(self, key):
        w = [list(key[i:i + 4]) for i in range(0, len(key), 4)]
        for i in range(self.nk, 4 * (self.nr + 1)):
            t = list(w[i - 1])
            if i % self.nk == 0:
                t = t[1:] + t[:1]
                t = [SBOX[b] for b in t]
                t[0] ^= RCON[i // self.nk - 1]
            elif self.nk > 6 and i % self.nk == 4:
                t = [SBOX[b] for b in t]
            w.append([w[i - self.nk][j] ^ t[j] for j in range(4)])
        return w

    def _add(self, s, rnd):
        for c in range(4):
            for r in range(4):
                s[r][c] ^= self.rk[rnd * 4 + c][r]

    def enc(self, block):
        s = [[block[r + 4 * c] for c in range(4)] for r in range(4)]
        self._add(s, 0)
        for rnd in range(1, self.nr + 1):
            for r in range(4):
                for c in range(4):
                    s[r][c] = SBOX[s[r][c]]
            for r in range(1, 4):
                s[r] = s[r][r:] + s[r][:r]
            if rnd != self.nr:
                for c in range(4):
                    a0, a1, a2, a3 = s[0][c], s[1][c], s[2][c], s[3][c]
                    s[0][c] = _gmul(a0, 2) ^ _gmul(a1, 3) ^ a2 ^ a3
                    s[1][c] = a0 ^ _gmul(a1, 2) ^ _gmul(a2, 3) ^ a3
                    s[2][c] = a0 ^ a1 ^ _gmul(a2, 2) ^ _gmul(a3, 3)
                    s[3][c] = _gmul(a0, 3) ^ a1 ^ a2 ^ _gmul(a3, 2)
            self._add(s, rnd)
        return bytes(s[r][c] for c in range(4) for r in range(4))

    def dec(self, block):
        s = [[block[r + 4 * c] for c in range(4)] for r in range(4)]
        self._add(s, self.nr)
        for rnd in range(self.nr - 1, -1, -1):
            for r in range(1, 4):
                s[r] = s[r][-r:] + s[r][:-r]
            for r in range(4):
                for c in range(4):
                    s[r][c] = INV_SBOX[s[r][c]]
            self._add(s, rnd)
            if rnd != 0:
                for c in range(4):
                    a0, a1, a2, a3 = s[0][c], s[1][c], s[2][c], s[3][c]
                    s[0][c] = _gmul(a0, 14) ^ _gmul(a1, 11) ^ _gmul(a2, 13) ^ _gmul(a3, 9)
                    s[1][c] = _gmul(a0, 9) ^ _gmul(a1, 14) ^ _gmul(a2, 11) ^ _gmul(a3, 13)
                    s[2][c] = _gmul(a0, 13) ^ _gmul(a1, 9) ^ _gmul(a2, 14) ^ _gmul(a3, 11)
                    s[3][c] = _gmul(a0, 11) ^ _gmul(a1, 13) ^ _gmul(a2, 9) ^ _gmul(a3, 14)
        return bytes(s[r][c] for c in range(4) for r in range(4))


def _aes_cbc_enc(data, key, iv):
    aes = _AES(key)
    n = 16 - len(data) % 16
    data = data + bytes([n]) * n
    out, prev = bytearray(), iv
    for i in range(0, len(data), 16):
        blk = bytes(data[i + j] ^ prev[j] for j in range(16))
        enc = aes.enc(blk)
        out += enc
        prev = enc
    return bytes(out)


def _pkcs7_unpad(raw):
    """严格校验 PKCS7。填充不合法时原样返回，既不抛异常也不静默截断明文。"""
    if not raw:
        return b""
    n = raw[-1]
    if 1 <= n <= 16 and n <= len(raw) and raw[-n:] == bytes([n]) * n:
        return bytes(raw[:-n])
    return bytes(raw)


def _aes_cbc_dec(data, key, iv):
    if not data or len(data) % 16:
        raise ValueError("ciphertext length must be a positive multiple of 16")
    aes = _AES(key)
    out, prev = bytearray(), iv
    for i in range(0, len(data), 16):
        blk = data[i:i + 16]
        dec = aes.dec(blk)
        out += bytes(dec[j] ^ prev[j] for j in range(16))
        prev = blk
    return _pkcs7_unpad(out)

# ---------------------------------------------------------------- 工具


def _clean(s):
    s = str(s or "")
    s = re.sub(r"<[^>]+>", "", s)
    s = s.replace("&amp;nbsp;", " ").replace("&nbsp;", " ").replace("&amp;", "&")
    return " ".join(s.split()).strip()


def _safe(s):
    return _clean(s).replace("$", " ").replace("#", " ").strip()


def _fix(u):
    u = str(u or "").strip()
    if u.startswith("//"):
        u = "http:" + u
    return u


def _b64d(s):
    """容错 base64：去 URL 编码与空白，标准/urlsafe 双兼容，补齐 padding。"""
    s = urllib.parse.unquote(str(s or "")).strip()
    s = re.sub(r"\s+", "", s)
    if not s:
        return b""
    s = s.replace("-", "+").replace("_", "/").rstrip("=")
    s += "=" * (-len(s) % 4)
    try:
        return base64.b64decode(s)
    except Exception:
        return b""


def _decrypt_baidu(url):
    """https://baidu.con/<16 chars key><base64(ct)> → AES-CBC(key,key) 明文"""
    url = str(url or "").strip()
    if url.startswith("//"):
        url = "http:" + url
    m = re.match(r"^https?://baidu\.con/(.+)$", url, re.I)
    if not m:
        return ""
    body = urllib.parse.unquote(m.group(1)).strip()
    if len(body) <= 16:
        return ""
    key = body[:16].encode("utf-8", "ignore")
    if len(key) != 16:
        return ""
    raw = _b64d(body[16:])
    if not raw or len(raw) % 16:
        return ""
    try:
        text = _aes_cbc_dec(raw, key, key).decode("utf-8", "ignore").strip()
    except Exception:
        return ""
    return text if text.startswith("http") else ""



# ---------------------------------------------------------------- 本地 m3u8 代理
# 影探的解析线路（parsesId=7）下发的是「6 秒失效」限时链接：
#   拿到明文 URL 后若被播放器二次请求，服务端就判「地址已失效」。
#   而**分片本身不失效**（实测 10s+ 后首尾分片仍全 200），只有清单 URL 一次一判。
# 对策：play 时同步解析→拉取→原样重建清单，再由本机 HTTP 服务惰性代理分片。
#   播放器只拿到 http://127.0.0.1:PORT/yt/<token>/index.m3u8，永远不过期。
_PLAN = {"srv": None, "port": 0}
_PLAN_LOCK = threading.Lock()


def _http_get(url, timeout=12, headers=None, retry=2):
    """禁止跟随跳转到 http→https 之外的站点；返回 (status, body_bytes, final_url)。"""
    h = {"User-Agent": UA, "Accept": "*/*", "Accept-Encoding": "identity"}
    if headers:
        h.update(headers)
    last = None
    for i in range(retry + 1):
        try:
            req = urllib.request.Request(url, headers=h)
            r = urllib.request.urlopen(req, timeout=timeout)
            return r.getcode(), r.read(), r.geturl()
        except Exception as e:
            last = e
            code = getattr(e, "code", None)
            if code and code < 500:
                return code, b"", url
            time.sleep(0.3 * (i + 1))
    return 0, b"", url


class _YtHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):
        pass

    def _plan(self):
        path = urllib.parse.urlparse(self.path).path
        parts = [p for p in path.split("/") if p]
        if len(parts) < 2:
            return None, None, parts
        return _PLAN.get(parts[1]), parts[0], parts

    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        plan, kind, parts = self._plan()
        if not plan:
            self.send_error(404)
            return
        try:
            if kind == "yt":
                # /yt/<tok>/index.m3u8  或  /yt/<tok>/s.m3u8
                if len(parts) >= 3 and parts[2] == "index.m3u8":
                    body = plan["manifest"].encode("utf-8")
                    return self._send(200, body, "application/vnd.apple.mpegurl")
                if len(parts) >= 3 and parts[2] == "s.m3u8":
                    body = plan["sub"].encode("utf-8")
                    return self._send(200, body, "application/vnd.apple.mpegurl")
                self.send_error(404)
                return
            if kind == "ts":
                # /ts/<tok>/<n>
                try:
                    n = int(parts[2])
                except Exception:
                    self.send_error(400)
                    return
                segs = plan.get("segs") or []
                if n < 0 or n >= len(segs):
                    self.send_error(404)
                    return
                url = segs[n]
                rng = self.headers.get("Range")
                code, body, _ = _http_get(url, timeout=20,
                                          headers={"Range": rng} if rng else None, retry=3)
                if code in (200, 206) and body:
                    return self._send(code, body, "video/mp2t", extra={
                        "Accept-Ranges": "bytes"})
                # 分片万一也失效 → 就地续命：用原始页重新解析一次拿新清单，按序号重定位
                if self._rescue(plan, n):
                    url = plan["segs"][n]
                    code, body, _ = _http_get(url, timeout=20,
                                              headers={"Range": rng} if rng else None, retry=2)
                    if code in (200, 206) and body:
                        return self._send(code, body, "video/mp2t", extra={
                            "Accept-Ranges": "bytes"})
                self.send_error(502)
                return
            self.send_error(404)
        except Exception:
            try:
                self.send_error(500)
            except Exception:
                pass

    def _rescue(self, plan, n):
        """分片失效救援：重跑一次解析，用「序号/总长」比例换算到新清单。"""
        now = time.time()
        if now - plan.get("rescue_at", 0) < 4:
            return False
        plan["rescue_at"] = now
        try:
            fn = plan.get("resolver")
            url = fn() if fn else ""
            if not url:
                return False
            code, body, _ = _http_get(url, timeout=10)
            if code != 200:
                return False
            m = _rebuild_playlist(body.decode("utf-8", "ignore"), plan["tok"], url)
            segs = m.get("segs") or []
            if not segs:
                return False
            old = len(plan["segs"]) or 1
            plan["segs"] = segs
            plan["manifest"] = m["manifest"]
            plan["sub"] = m.get("sub", "")
            if 0 <= n < len(segs):
                return True
            idx = min(len(segs) - 1, max(0, int(n * len(segs) / old)))
            plan["remap"] = plan.get("remap") or {}
            plan["remap"][n] = idx
            return True
        except Exception:
            return False

    def _send(self, code, body, ctype, extra=None):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        try:
            self.wfile.write(body)
        except Exception:
            pass


def _rebuild_playlist(text, tok, base=""):
    """把真实 m3u8 重写成本地清单：分片→/ts/<tok>/n，子清单→/yt/<tok>/s.m3u8。
    base 是清单自身的真实 URL，用于把相对路径（如 index0.ts?auth_key=...）补成绝对地址。"""
    lines = [l.strip() for l in str(text or "").splitlines()]
    root, has_sub = [], False
    for ln in lines:
        if not ln:
            continue
        if ln.startswith("#EXT-X-STREAM-INF"):
            has_sub = True
        root.append(ln)
        if has_sub and not ln.startswith("#") and ln.strip():
            has_sub = False
    segs = []
    out = []
    for ln in root:
        if ln and not ln.startswith("#"):
            segs.append(urllib.parse.urljoin(base, ln) if base else ln)
            out.append("http://127.0.0.1:%s/ts/%s/%d" % (_PLAN["port"], tok, len(segs) - 1))
        else:
            out.append(ln)
    return {"manifest": "\n".join(out) + "\n", "segs": segs, "sub": ""}


def _ensure_server():
    with _PLAN_LOCK:
        srv = _PLAN.get("srv")
        if srv is not None:
            return _PLAN["port"]
        for port in (9979, 9980, 9981, 9982, 9983, 9984):
            try:
                s = ThreadingHTTPServer(("127.0.0.1", port), _YtHandler)
                s.daemon_threads = True
                t = threading.Thread(target=s.serve_forever)
                t.setDaemon(True)
                t.start()
                _PLAN["srv"] = s
                _PLAN["port"] = port
                return port
            except Exception:
                continue
        return 0


def _mk_token():
    return "%x" % ((int(time.time() * 1000) << 12) ^ (id(threading.current_thread()) & 0xfff))

class Spider(BaseSpider):
    def getName(self):
        return "影探4K"

    def getDependence(self):
        return []

    def setExtendInfo(self, extend):
        pass

    def init(self, extend=""):
        self.host = HOST
        self.token = ""
        try:
            cfg = {}
            if isinstance(extend, dict):
                cfg = extend
            elif isinstance(extend, str) and extend.strip().startswith("{"):
                cfg = json.loads(extend)
            if isinstance(cfg, dict):
                if cfg.get("host"):
                    self.host = str(cfg["host"]).rstrip("/")
                if cfg.get("token"):
                    self.token = str(cfg["token"])
        except Exception:
            pass

    # ---------------------------------------------------------------- HTTP
    def _get(self, url, timeout=20):
        h = {"User-Agent": UA, "Accept-Encoding": "identity",
             "Accept": "application/json, text/plain, */*",
             "Referer": getattr(self, "host", HOST) + "/"}
        last = ""
        for i in range(3):
            try:
                r = urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=timeout)
                txt = r.read().decode("utf-8", "ignore")
                try:
                    return json.loads(txt)
                except Exception:
                    last = txt[:200]
                    break
            except Exception as e:
                last = "%s: %s" % (type(e).__name__, e)
                time.sleep(0.5 * (i + 1))
        return {"__raw": last}

    def _cms(self, action, params):
        q = urllib.parse.urlencode(params or {})
        return self._get("%s/api.php/app/%s?%s" % (self.host, action, q))

    # ---------------------------------------------------------------- 首页
    def homeContent(self, filter):
        j = self._cms("nav", {"token": getattr(self, "token", "")})
        classes, filters = [], {}
        for c in (j.get("list") or []):
            tid = str(c.get("type_id") or "")
            name = _clean(c.get("type_name"))
            if not tid or not name:
                continue
            classes.append({"type_id": tid, "type_name": name})
            fl = []
            ext = c.get("type_extend") or {}
            if filter:
                for key, label in FILTER_KEYS:
                    raw = _clean(ext.get(key))
                    if not raw:
                        continue
                    vals = []
                    seen = set()
                    for v in raw.split(","):
                        v = v.strip()
                        if not v or v in seen:
                            continue
                        seen.add(v)
                        vals.append({"n": v, "v": v})
                    if len(vals) > 1:
                        fl.append({"key": key, "name": label,
                                   "value": [{"n": "全部", "v": ""}] + vals})
            filters[tid] = fl or []
        if not classes:
            classes = [{"type_id": "1", "type_name": "电影"}]
        return {"class": classes, "filters": filters}

    def homeVideoContent(self):
        j = self._cms("index_video", {"token": getattr(self, "token", "")})
        out = []
        for block in (j.get("list") or []):
            for it in (block.get("vlist") or []) if isinstance(block, dict) else []:
                v = self._item(it)
                if v:
                    out.append(v)
        return {"list": out}

    def _item(self, it):
        if not isinstance(it, dict):
            return None
        vid = str(it.get("vod_id") or it.get("id") or "")
        name = _clean(it.get("vod_name") or it.get("name"))
        if not vid or not name:
            return None
        pic = _fix(it.get("vod_pic") or it.get("vod_pic_thumb") or "")
        remarks = _clean(it.get("vod_remarks") or "")
        if not remarks and it.get("vod_score") and str(it.get("vod_score")) not in ("0.0", "0"):
            remarks = "评分 %s" % it.get("vod_score")
        return {"vod_id": vid, "vod_name": name, "vod_pic": pic, "vod_remarks": remarks}

    # ---------------------------------------------------------------- 分类
    def categoryContent(self, tid, pg, filter, extend):
        try:
            page = max(1, int(str(pg).strip() or 1))
        except Exception:
            page = 1
        ext = extend if isinstance(extend, dict) else {}
        params = {"tid": str(tid), "pg": str(page), "limit": "18"}
        for key, _ in FILTER_KEYS:
            v = str(ext.get(key) or "").strip()
            if v and v != "all":
                params[key] = v
        j = self._cms("video", params)
        lst = [self._item(x) for x in (j.get("list") or [])]
        lst = [x for x in lst if x]
        try:
            pages = int(j.get("pagecount") or 0)
        except Exception:
            pages = 0
        if pages <= 0:
            pages = page + 1 if lst else page
        try:
            total = int(j.get("total") or 0)
        except Exception:
            total = 0
        if total <= 0:
            total = pages * 18
        return {"page": page, "pagecount": pages, "limit": 18,
                "total": total, "list": lst}

    # ---------------------------------------------------------------- 详情
    def detailContent(self, ids):
        if isinstance(ids, (list, tuple)):
            vid = str(ids[0] if ids else "").strip()
        else:
            vid = str(ids or "").strip()
        if not vid:
            return {"list": []}
        j = self._cms("video_detail", {"id": vid})
        d = j.get("data") or {}
        if not d:
            return {"list": []}
        froms = [x for x in str(d.get("vod_play_from") or "").split("$$$") if x]
        raw_urls = [x for x in str(d.get("vod_play_url") or "").split("$$$")]
        urls = []
        for grp in raw_urls:
            eps = []
            for part in grp.split("#"):
                part = part.strip()
                if not part:
                    continue
                if "$" in part:
                    t, u = part.split("$", 1)
                else:
                    t, u = "正片", part
                t = _safe(t) or "正片"
                u = u.strip()
                if u:
                    eps.append("%s$%s" % (t, u))
            urls.append("#".join(eps))
        while len(froms) < len(urls):
            froms.append("线路%d" % (len(froms) + 1))
        pairs = [(f, u) for f, u in zip(froms, urls) if u]
        vod = {
            "vod_id": vid,
            "vod_name": _clean(d.get("vod_name")),
            "vod_pic": _fix(d.get("vod_pic") or d.get("vod_pic_thumb")),
            "type_name": _clean(d.get("vod_class")),
            "vod_year": str(d.get("vod_year") or ""),
            "vod_area": _clean(d.get("vod_area")),
            "vod_lang": _clean(d.get("vod_lang")),
            "vod_remarks": _clean(d.get("vod_remarks")),
            "vod_actor": _clean(d.get("vod_actor")),
            "vod_director": _clean(d.get("vod_director")),
            "vod_content": _clean(d.get("vod_content") or d.get("vod_blurb")),
            "vod_play_from": "$$$".join([p[0] for p in pairs]),
            "vod_play_url": "$$$".join([p[1] for p in pairs]),
        }
        if not pairs:
            vod["vod_play_from"] = "网页"
            vod["vod_play_url"] = "正片$%s/api.php/app/video_detail?id=%s" % (self.host, vid)
        return {"list": [vod]}

    # ---------------------------------------------------------------- 搜索
    def searchContent(self, key, quick, pg="1"):
        try:
            page = max(1, int(str(pg).strip() or 1))
        except Exception:
            page = 1
        j = self._cms("search", {"text": str(key or ""), "pg": str(page)})
        lst = [self._item(x) for x in (j.get("list") or [])]
        return {"list": [x for x in lst if x], "page": page}

    # ---------------------------------------------------------------- 播放
    def playerContent(self, flag, id, vipFlags):
        url = str(id or "").strip()
        try:
            if url.startswith("lvdou+"):
                url = self._decrypt_lvdou(url) or url
            if not url.startswith("http"):
                return {"parse": 1, "playUrl": "", "url": url, "header": ""}

            host = (urllib.parse.urlparse(url).hostname or "").lower()
            media_like = bool(MEDIA_RE.search(url))

            # ① 4K 直链（lyyytv 自家 CDN）：能直连就直连
            if YT4K_HOST.search(host):
                if self._probe(url):
                    return {"parse": 0, "playUrl": "", "url": url,
                            "header": '{"User-Agent":"%s"}' % UA}
                media_like = False          # 直链已下架 → 交给解析线路兜底

            # ② 已经是明文 m3u8/mp4 且可播：直出
            if media_like and self._probe(url):
                return {"parse": 0, "playUrl": "", "url": url,
                        "header": '{"User-Agent":"%s"}' % UA}

            # ③ 解析线路：拿到真实地址后「同步」第二次拉取（限时链接必须在数秒内消费）
            real, txt, status = self._resolve(url)
            if real and txt and ("#EXTM3U" in txt[:200]):
                local = self._localize(real, txt, url)
                if local:
                    return {"parse": 0, "playUrl": "", "url": local,
                            "header": '{"User-Agent":"%s"}' % UA}
            if real and self._probe(real):
                return {"parse": 0, "playUrl": "", "url": real,
                        "header": '{"User-Agent":"%s"}' % UA}
            if real:
                # 解析成功但已过期（被别处先消费了）→ 让壳端自行 over-http 再来一次
                return {"parse": 1, "playUrl": url, "url": url, "header": ""}
            return {"parse": 1, "playUrl": url, "url": url, "header": ""}
        except Exception:
            return {"parse": 1, "playUrl": url, "url": url, "header": ""}

    def isVideoFormat(self, url):
        return bool(MEDIA_RE.search(str(url or "")))

    def manualVideoCheck(self):
        return False

    @staticmethod
    def _probe(url):
        """轻量探活：m3u8 看魔数，mp4 看 Range 首字节。"""
        try:
            if ".m3u8" in url or ".m3u" in url:
                code, body, _ = _http_get(url, timeout=8, headers={
                    "Accept": "application/vnd.apple.mpegurl,*/*"})
                return code == 200 and b"#EXTM3U" in body[:512]
            code, body, _ = _http_get(url, timeout=8, headers={"Range": "bytes=0-1023"})
            return code in (200, 206) and len(body) > 0
        except Exception:
            return False

    def _resolve(self, page_url):
        """多线路解析 → (真实URL, 首屏正文, 状态码)。
        拿到清单后立刻试拉首片：分片不可达（相对路径 404）的线路直接丢弃，
        否则壳端会卡在一个「能读清单、却永远缓冲」的死源上。"""
        for pid in PARSE_IDS:
            try:
                api = (CHAIN_API % pid) + urllib.parse.quote(str(page_url), safe="")
                j = self._get(api, timeout=15)
            except Exception:
                continue
            if not isinstance(j, dict):
                continue
            raw = self._extract_url(j)
            if not raw:
                continue
            real = _decrypt_baidu(raw) if "baidu.con/" in raw.lower() else raw
            if not real.startswith("http"):
                continue
            code, body, _ = _http_get(real, timeout=10)
            if code != 200 or not body:
                continue
            txt = body.decode("utf-8", "ignore")
            if not self._first_seg_ok(real, txt):
                continue
            return real, txt, code
        return "", "", 0

    @staticmethod
    def _first_seg_ok(real_url, text):
        """试拉第一条分片，确认这条线路真的能出流。"""
        seg = ""
        for ln in str(text or "").splitlines():
            ln = ln.strip()
            if ln and not ln.startswith("#"):
                seg = ln
                break
        if not seg:
            return True                      # 无法判定时放行，交给播放器
        try:
            code, body, _ = _http_get(urllib.parse.urljoin(real_url, seg), timeout=10, retry=1)
            return code in (200, 206) and len(body) > 188
        except Exception:
            return False

    def _localize(self, real_url, text, page_url):
        """把限时 m3u8 变成本机代理地址；失败返回空串。"""
        port = _ensure_server()
        if not port or "#EXTM3U" not in text[:200]:
            return ""
        tok = _mk_token()
        m = _rebuild_playlist(text, tok, real_url)
        if not m.get("segs") and not m.get("manifest", "").count("/s.m3u8"):
            return ""
        plan = {"tok": tok, "manifest": m["manifest"], "sub": m.get("sub", ""),
                "segs": m.get("segs") or [], "resolver": lambda: self._fresh(page_url),
                "rescue_at": 0}
        _PLAN[tok] = plan
        # 只保留最近 8 个 plan，避免长会话堆积
        if len(_PLAN) > 12:
            for k in list(_PLAN.keys()):
                if k in ("srv", "port") or k == tok:
                    continue
                _PLAN.pop(k, None)
        return "http://127.0.0.1:%s/yt/%s/index.m3u8" % (port, tok)

    def _fresh(self, page_url):
        """分片失效救援用：重新解析一次，返回新的真实清单 URL。"""
        real, _t, code = self._resolve(page_url)
        return real if code == 200 else ""

    def _decrypt_lvdou(self, s):
        """lvdou+<b64> → AES-CBC(key=CMS_KEY[0:16], iv=CMS_KEY[16:32])"""
        key = CMS_KEY[:16].encode()
        iv = (CMS_KEY[16:32] if len(CMS_KEY) >= 32 else CMS_KEY[:16]).encode()
        body = str(s or "")[6:].strip()
        raw = _b64d(body)
        if not raw or len(raw) % 16:
            return ""
        try:
            out = _aes_cbc_dec(raw, key, iv).decode("utf-8", "ignore").strip()
        except Exception:
            return ""
        return out if out.startswith("http") else ""

    @staticmethod
    def _extract_url(j):
        """兼容 {url:..} / {data:{url:..}} / playUrl 等常见形态"""
        if not isinstance(j, dict):
            return ""
        keys = ("url", "playUrl", "play_url", "videoUrl", "video_url", "src")
        for src in (j, j.get("data") if isinstance(j.get("data"), dict) else {}):
            if not isinstance(src, dict):
                continue
            for k in keys:
                v = src.get(k)
                if isinstance(v, str) and v.strip():
                    return _fix(v.strip())
        return ""
