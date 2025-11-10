# -*- coding:utf-8 -*-
# 批量获取fc2 影片磁力
#name = fc2_gater
#version = 'v0.01'

import requests, os, sys, time, re, threading
from configparser import RawConfigParser
from traceback import format_exc
try:
    from pypac import PACSession
except Exception:
    PACSession = None
import platform
import argparse
import socket
import urllib3
from urllib3.util.retry import Retry

#读取&初始化配置文件
def read_config():
    if os.path.exists('config.ini'):
        config_settings = RawConfigParser()
        try:
            config_settings.read('config.ini', encoding='UTF-8-SIG')  # UTF-8-SIG 适配 Windows 记事本
            proxy = config_settings.get("下载设置", "Proxy")
            download_path = config_settings.get("下载设置", "Download_Path")
            max_dl = config_settings.get("下载设置", "Max_dl")
            max_retry = config_settings.get("下载设置", "Max_retry")
            # 自动代理开关（兼容旧配置：默认启用）
            try:
                auto_proxy = config_settings.get("下载设置", "AutoProxy")
            except Exception:
                auto_proxy = '是'
            try:
                verify_ssl = config_settings.get("下载设置", "VerifySSL")
            except Exception:
                verify_ssl = '否'

            # 创建文件夹
            if not os.path.exists(download_path):
                os.makedirs(download_path)
            return (proxy, download_path, max_dl, max_retry, auto_proxy, verify_ssl)
        except:
            print(format_exc())
            print('× 无法读取 config.ini。如果这是旧版本的配置文件，请删除后重试。\n')
            print('按任意键退出程序...');os.system('pause>nul')
            sys.exit()
    else:
        context='''[下载设置]
# http / socks5 局部代理 
# http 代理格式为 http://ip:端口 , 如 http://localhost:8088 
# socks5 代理格式为 socks5://ip:端口 , 如 socks5://localhost:8088 
Proxy = 否

# 自动代理（系统/环境/PAC）
# 是：自动检测系统代理（包含 PAC 或环境变量），若关闭则直连
# 否：仅使用上面的 Proxy 配置；若为“否”且未配置 Proxy，则直连
AutoProxy = 是

# SSL 证书验证
# 是：严格验证证书；否：在某些代理拦截或自签证书场景下可关闭
VerifySSL = 是

#存储番号文件目录 
Download_path = ./Downloads/

# 下载线程数 
# 若网络不稳定、丢包率或延迟较高，可适当减小下载线程数 
# 默认线程2，小量数据不建议修改，多线程容易报502，建议线程 n/30
Max_dl = 2

# 下载失败重试数 
# 若网络不稳定、丢包率或延迟较高，可适当增加失败重试数 
# 避免晚上网络高峰期爬取大量数据，容易报错，也会增加服务器负担
Max_retry = 3'''
        txt = open("config.ini", 'a', encoding="utf-8")
        txt.write(context)
        txt.close()
        print('× 没有找到 config.ini。已生成，请修改配置后重新运行程序。\n')
        print('按任意键退出程序...');os.system('pause>nul')
        sys.exit()

def _is_true(val):
    if val is None:
        return False
    s = str(val).strip().lower()
    return s in ('是','yes','y','true','1')

def build_session(auto_proxy, manual_proxy, max_retry):
    # 优先自动代理（系统/环境/PAC），向后兼容手动代理
    try:
        max_retry_int = int(max_retry)
    except Exception:
        max_retry_int = 3

    auto_enabled = _is_true(auto_proxy)
    if auto_enabled and PACSession is not None:
        try:
            sess = PACSession()
        except Exception:
            # 自动代理不可用时回退到普通会话
            sess = requests.Session()
    else:
        sess = requests.Session()

    # 始终忽略环境代理变量，统一由 PacSession/直连控制
    sess.trust_env = False

    # 简化：不再使用手动代理。AutoProxy=是 => PacSession；AutoProxy=否 => 直连

    # 设置重试适配器（含退避与指定状态码）
    retry_strategy = Retry(
        total=max_retry_int,
        backoff_factor=0.5,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
        raise_on_status=False,
    )
    adapter = requests.adapters.HTTPAdapter(max_retries=retry_strategy)
    sess.mount('http://', adapter)
    sess.mount('https://', adapter)

    # 自动模式下，无环境代理且未设置手动代理时，应用 Windows 系统代理
    try:
        env_p = _get_env_proxies()
        no_env = not env_p.get('http') and not env_p.get('https')
        no_manual = not getattr(sess, 'proxies', None)
        if auto_enabled and no_env and no_manual:
            win_p = _get_windows_system_proxy()
            if win_p:
                # 从系统代理中提取地址并尝试协议（HTTP / SOCKS5）
                addr = ''
                if win_p.get('https'):
                    addr = win_p.get('https')
                elif win_p.get('http'):
                    addr = win_p.get('http')
                elif isinstance(win_p, dict):
                    # 回退：若只提供了无协议的地址，已在 _get_windows_system_proxy 处理中双写
                    addr = win_p.get('http') or ''
                hostport = _extract_hostport(addr)
                chosen = _select_proxy_protocol(hostport, _is_true(verify_ssl))
                if chosen:
                    sess.proxies = chosen
    except Exception:
        pass

    try:
        if getattr(sess, 'proxies', None):
            ok = _probe_proxy(sess, _is_true(verify_ssl))
            if not ok:
                # 不强制清空代理，保持“浏览器式”行为；失败时由请求层优雅降级
                print('！代理自检失败（可能拦截或协议不匹配），仍使用系统/手动代理；若请求失败将自动降级直连')
    except Exception:
        pass
    return sess

def _get_env_proxies():
    env = os.environ
    return {
        'http': env.get('HTTP_PROXY') or env.get('http_proxy') or '',
        'https': env.get('HTTPS_PROXY') or env.get('https_proxy') or ''
    }

def _get_windows_system_proxy():
    # 读取 Windows 注册表中的系统代理（非 PAC）
    try:
        if platform.system().lower() != 'windows':
            return None
        import winreg
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\\Microsoft\\Windows\\CurrentVersion\\Internet Settings"
        ) as key:
            try:
                proxy_enable, _ = winreg.QueryValueEx(key, 'ProxyEnable')
            except Exception:
                proxy_enable = 0
            try:
                proxy_server, _ = winreg.QueryValueEx(key, 'ProxyServer')
            except Exception:
                proxy_server = ''
            try:
                proxy_override, _ = winreg.QueryValueEx(key, 'ProxyOverride')
            except Exception:
                proxy_override = ''
        if not proxy_enable or not proxy_server:
            return None
        proxies = {}
        for part in proxy_server.split(';'):
            part = part.strip()
            if not part:
                continue
            if '=' in part:
                scheme, addr = part.split('=', 1)
                scheme = scheme.strip().lower()
                addr = addr.strip()
                if not (addr.startswith('http://') or addr.startswith('https://') or addr.startswith('socks5://')):
                    addr = f"{scheme}://{addr}" if scheme in ('http','https') else f"http://{addr}"
                if scheme in ('http','https'):
                    proxies[scheme] = addr
            else:
                addr = part
                if not (addr.startswith('http://') or addr.startswith('https://') or addr.startswith('socks5://')):
                    addr = f"http://{addr}"
                proxies['http'] = addr
                proxies['https'] = addr
        # 将 override 信息附带返回（仅用于显示）
        if proxies:
            proxies['_override'] = proxy_override
        return proxies or None
    except Exception:
        return None

def _extract_hostport(addr: str):
    if not addr:
        return ''
    a = addr.strip()
    # 去掉协议前缀
    a = re.sub(r'^(http|https|socks5)://', '', a, flags=re.IGNORECASE)
    return a

def _build_proxy_map(proto: str, hostport: str):
    u = f"{proto}://{hostport}"
    return {'http': u, 'https': u}

def _probe_proxies(proxies, verify):
    try:
        s = requests.Session()
        s.trust_env = False
        s.proxies = proxies
        adapter = requests.adapters.HTTPAdapter(max_retries=1)
        s.mount('http://', adapter)
        s.mount('https://', adapter)
        r = s.get(_proxy_test_url(), timeout=6, verify=verify)
        return r.status_code == 200
    except Exception:
        return False

def _select_proxy_protocol(hostport: str, verify: bool):
    if not hostport:
        return None
    # 先尝试 HTTP（兼容系统代理通常设置为 HTTP）
    http_map = _build_proxy_map('http', hostport)
    if _probe_proxies(http_map, verify):
        return http_map
    # 再尝试 SOCKS5（Clash 等混合端口常可用）
    socks_map = _build_proxy_map('socks5', hostport)
    if _probe_proxies(socks_map, verify):
        return socks_map
    return None

def print_proxy_status(auto_proxy, manual_proxy, sess):
    try:
        env_p = _get_env_proxies()
        is_auto = _is_true(auto_proxy)
        sess_type = 'PACSession' if PACSession is not None and isinstance(sess, PACSession) else 'requests.Session'
        manual_used = False
        print('—— 代理状态 ——')
        print('AutoProxy: ' + ('开启' if is_auto else '关闭'))
        print('会话类型: ' + sess_type)
        print('手动代理: 未使用')
        if env_p.get('http') or env_p.get('https'):
            print('环境代理: ' + str({k:v for k,v in env_p.items() if v}))
        else:
            print('环境代理: 未检测到')
        win_sys = _get_windows_system_proxy()
        if win_sys:
            shown = {k:v for k,v in win_sys.items() if k in ('http','https')}
            if '_override' in win_sys:
                shown['override'] = win_sys['_override']
            print('系统代理(Windows): ' + str(shown))
        else:
            print('系统代理(Windows): 未检测到或未开启')
        print('———————')
    except Exception:
        print('× 显示代理状态失败')

def _debug_snapshot(url: str, phase: str):
    try:
        env_p = _get_env_proxies()
        win_p = _get_windows_system_proxy() or {}
        print(f'[调试] 阶段: {phase}')
        print(f'[调试] URL: {url}')
        print(f'[调试] VerifySSL: {verify_ssl} (effective={_is_true(verify_ssl)})')
        print(f'[调试] AutoProxy: {auto_proxy} (effective={_is_true(auto_proxy)})')
        try:
            print(f'[调试] session.trust_env: {getattr(session, "trust_env", None)}')
            print(f'[调试] session.proxies: {getattr(session, "proxies", None)}')
        except Exception:
            pass
        if env_p.get('http') or env_p.get('https'):
            print('[调试] 环境代理: ' + str({k:v for k,v in env_p.items() if v}))
        shown = {k:v for k,v in win_p.items() if k in ('http','https')}
        if shown:
            print('[调试] 系统代理(Windows): ' + str(shown))
    except Exception:
        print('[调试] 快照输出失败')

def _debug_dump_html(url: str, html: str, limit: int = 500):
    try:
        print(f'[调试] 目标 URL: {url}')
        if html is None:
            print('[调试] 页面内容: None')
            return
        length = len(html)
        print(f'[调试] 页面总长度: {length}')
        head = html[:limit]
        # 为了控制台可读性，压缩换行与过多空白
        head_oneline = re.sub(r"\s+", " ", head)
        print(f'[调试] 页面前{limit}字符: {head_oneline}')
    except Exception:
        print('[调试] 页面内容输出失败')
        print(format_exc())

def _proxy_test_url():
    return 'https://www.baidu.com/'

def _probe_proxy(sess, verify):
    try:
        test_url = _proxy_test_url()
        r = sess.get(test_url, timeout=6, verify=verify)
        return r.status_code == 200
    except Exception:
        return False

def _browser_headers(url: str):
    # 更接近真实浏览器的请求头，提升通过率
    ua = (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/120.0.0.0 Safari/537.36'
    )
    headers = {
        'User-Agent': ua,
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
    }
    # 针对 FC2 添加 Referer/Origin
    try:
        if 'adult.contents.fc2.com' in url:
            headers['Referer'] = 'https://adult.contents.fc2.com/'
            headers['Origin'] = 'https://adult.contents.fc2.com'
        elif 'sukebei.nyaa.si' in url:
            headers['Referer'] = 'https://sukebei.nyaa.si/'
            headers['Origin'] = 'https://sukebei.nyaa.si'
    except Exception:
        pass
    return headers

def fc2_get_current_page(txt):#获当前页码
    pattern = re.compile('<span class="items" aria-selected="true">([0-9]*)</span>', re.S)
    keys = re.findall(pattern, txt)
    if not keys==[]:
        return int(keys[0])

def fc2_get_next_page(txt):#获取下一页
    pattern = re.compile('<span class="items" aria-selected="true">.*?</span>.*?<a data-pjx="pjx-container" data-link-name="pager".*?href=".*?&page=([0-9]*)" class="items">.*?<', re.S)
    keys = re.findall(pattern, txt)
    if not keys==[]:
        return int(keys[0])
    else:return 0

# 获取网页数据
def requests_web(url):
    headers = _browser_headers(url)
    timeout_seconds = 15  # 默认超时，可后续从配置扩展
    attempts = 1
    try:
        attempts = max(1, int(max_retry))
    except Exception:
        attempts = 1
    # 初始快照，便于定位代理/证书/环境差异
    _debug_snapshot(url, 'request-start')
    try:
        # 带退避的多次尝试（会话使用代理/自动代理）
        for i in range(attempts):
            try:
                response = session.get(url, headers=headers, timeout=timeout_seconds, verify=_is_true(verify_ssl))
                response.encoding = 'utf-8'
                break
            except Exception as e:
                if i == attempts - 1:
                    print('[调试] 代理路径最终失败: ' + type(e).__name__)
                    print(format_exc())
                    raise
                # 指数退避，最多 5 秒
                backoff = min(2 ** i, 5)
                print(f'→ 第 {i+1}/{attempts} 次失败，退避 {backoff}s 后重试：{type(e).__name__}')
                time.sleep(backoff)
    except:
        print(format_exc())
        try:
            # 代理失败时优雅降级直连重试一次
            print('→ 尝试直连重试一次...')
            direct = requests.Session()
            # 明确关闭环境代理，确保是真正直连
            direct.trust_env = False
            adapter = requests.adapters.HTTPAdapter(max_retries=Retry(total=1, backoff_factor=0))
            direct.mount('http://', adapter)
            direct.mount('https://', adapter)
            _debug_snapshot(url, 'direct-retry')
            response = direct.get(url, headers=headers, timeout=timeout_seconds, verify=_is_true(verify_ssl))
            response.encoding = 'utf-8'
        except:
            print(format_exc())
            print('× 网络连接异常且代理与直连均失败')
            print('× 可能原因：网络防火墙、地区屏蔽、证书问题或系统代理不可用')
            print('× 建议：确认 Clash 端口/协议、尝试切换节点、或临时关闭 VerifySSL')
            return None
            sys.exit()

    if response.status_code != 200:
        print('x 连接错误：'+str(response.status_code))
        return None
        sys.exit()
    else:
        return response.text

def _test_single_url(url: str):
    print(f'→ 测试目标：{url}')
    html = None
    try:
        html = requests_web(url)
    except requests.exceptions.ProxyError:
        print('× 代理错误：可能端口不可达或协议不匹配（HTTP/SOCKS5）')
    except requests.exceptions.SSLError:
        print('× SSL 错误：证书校验失败，可尝试在 config.ini 设置 VerifySSL = 否')
    except requests.exceptions.ConnectTimeout:
        print('× 连接超时：网络拥塞或被目标站限制，已启用退避重试')
    except requests.exceptions.ReadTimeout:
        print('× 读取超时：目标响应过慢，建议增大超时或减少线程')
    except ConnectionResetError:
        print('× 连接被重置 (10054)：可能是防火墙、地区屏蔽或反爬触发，已使用浏览器特征请求头')
    except Exception as e:
        print(f'× 未知错误：{type(e).__name__}')
        print(format_exc())
    if html:
        print(f'√ 成功获取页面，长度：{len(html)} 字符')
        print('√ 说明：已使用浏览器特征请求头与退避重试，如仍不稳定可切换代理节点')
    else:
        print('× 页面获取失败：请检查系统/手动代理是否可用，或切换节点后重试')

def _probe_port(host: str, port: int, timeout: float = 2.0):
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except Exception:
        return False

def diagnose_network(test_urls):
    print('—— 诊断开始 ——')
    # 1) 探测常见端口
    host = '127.0.0.1'
    candidates = [7897, 7890, 1080]
    for p in candidates:
        ok = _probe_port(host, p)
        print(f'端口探测 {host}:{p} => {"开放" if ok else "不可达"}')

    # 2) 输出系统代理与环境变量
    env_p = _get_env_proxies()
    win_p = _get_windows_system_proxy()
    print('环境代理：', {k:v for k,v in env_p.items() if v})
    print('系统代理(Windows)：', {k:v for k,v in (win_p or {}).items() if k in ("http","https")})

    # 3) 直连测试
    print('→ 测试直连（不使用代理）')
    direct = requests.Session()
    direct.trust_env = False
    adapter = requests.adapters.HTTPAdapter(max_retries=Retry(total=1))
    direct.mount('http://', adapter)
    direct.mount('https://', adapter)
    for u in test_urls:
        try:
            r = direct.get(u, headers=_browser_headers(u), timeout=10, verify=_is_true(verify_ssl))
            print(f'直连 {u} => {r.status_code}')
        except Exception as e:
            print(f'直连 {u} 失败：{type(e).__name__}')

    # 4) 系统代理测试（HTTP 与 SOCKS5）
    hostports = []
    if win_p:
        addr = win_p.get('https') or win_p.get('http')
        hp = _extract_hostport(addr or '')
        if hp:
            hostports.append(hp)
    for hp in hostports:
        for proto in ('http','socks5'):
            print(f'→ 使用系统代理尝试 {proto}://{hp}')
            s = requests.Session()
            s.trust_env = False
            s.proxies = { 'http': f'{proto}://{hp}', 'https': f'{proto}://{hp}' }
            adapter = requests.adapters.HTTPAdapter(max_retries=Retry(total=1))
            s.mount('http://', adapter)
            s.mount('https://', adapter)
            for u in test_urls:
                try:
                    r = s.get(u, headers=_browser_headers(u), timeout=10, verify=_is_true(verify_ssl))
                    print(f'系统代理({proto}) {u} => {r.status_code}')
                except Exception as e:
                    print(f'系统代理({proto}) {u} 失败：{type(e).__name__}')
    print('—— 诊断结束 ——')

#获取番号正则
def parse_fc2id(txt):
    # 兼容多种版式：优先卡片结构，其次通用 /article/{id}/ 链接扫描
    ids = []
    try:
        pattern_card = re.compile(r'<div class="c-cntCard-110-f">.*?<a href="/article/([0-9]+)/"', re.S)
        ids.extend(re.findall(pattern_card, txt or ''))
    except Exception:
        pass
    if not ids:
        try:
            pattern_any = re.compile(r'/article/([0-9]+)/')
            ids.extend(re.findall(pattern_any, txt or ''))
        except Exception:
            pass
    # 去重并保持顺序
    seen = set()
    for item in ids:
        if item not in seen:
            seen.add(item)
            yield item

#获取磁力正则
def parse_magnet(html):
    pattern = re.compile('<a href="magnet:\?xt=(.*?)&amp;dn=', re.S)
    urls = re.findall(pattern, html)
    if not urls==[]:
        return 'magnet:?xt='+urls[0]

#获取每页番号并导出txt
def get_fc2id(url):
    clean_list('list.txt')
    i=1;n=1
    while i<=n:
        html=requests_web(url)
        _debug_dump_html(url, html, limit=500)
        if not html:
            print('× 页面获取失败，跳过解析与写入')
            break
        f2ids = list(parse_fc2id(html))
        print(f'[调试] 解析到番号数量: {len(f2ids)}')
        if f2ids:
            try:
                preview = ", ".join(f2ids[:20])
                suffix = ' ...' if len(f2ids) > 20 else ''
                print('[调试] 番号预览: ' + preview + suffix)
            except Exception:
                pass
            for num in f2ids:
                write_to_file('list.txt', 'FC2 '+str(num))
        else:
            print('× 未解析到任何番号，可能是页面结构变化、需要登录或地区限制')
        i=i+1
        n=fc2_get_next_page(html)
        print(f'[调试] 下一页页码: {n}')
        if n:
            url=url+'&page='+str(n)
    print('获取番号列表完成，数据已存到' + download_path + 'list.txt文件中')

#获取磁力链接并导出txt
def get_magnet(start,stop):
    for i in range(start,stop):
        url = 'https://sukebei.nyaa.si/?f=0&c=0_0&q=' + idlist[i]+'&s=downloads&o=desc'
        html = requests_web(url)
        if html is not None:
            magnet = parse_magnet(html)
            if magnet is not None:
                f = open(download_path + 'magnet.txt', 'a', encoding='UTF-8')
                mu.acquire()
                print('已找到磁力，数据写入magnet.txt文件中 ====> ' + idlist[i])
                f.write(str(magnet) + '\n')
                time.sleep(1)
                f.close()
                mu.release()
            else:
                f = open(download_path + 'no_magnet.txt', 'a', encoding='UTF-8')
                mu.acquire()
                print('× 没有磁力，失败列表写入no_magnet.txt ====> ' + idlist[i])
                f.write(idlist[i])
                time.sleep(1)
                f.close()
                mu.release()
        else:
            mu.acquire()
            write_to_file('error.txt',idlist[i].replace('\n','')+'--连接失败')
            time.sleep(1)
            mu.release()



#读取本地txt番号list
def read_list(file):
    file = download_path + file
    if os.path.exists(file):
        try:
            f2 = open(file, encoding='utf-8')
            line = f2.readlines()
            f2.close()
        except:
            print(format_exc())
            print('× 打开文件失败重试')
        return line
    else:
        print('× 没找到番号列表list.txt文件！请重新获取番号列表！')


#写入txt
def write_to_file(filename,txt):
    filename=download_path+filename
    try:
        print('开始写入数据 ====> ' + str(txt))
        with open(filename, 'a', encoding='UTF-8') as f:
            f.write(txt+'\n')
            f.close()
    except Exception:
        print('× 写入文件失败: ' + filename)
        print(format_exc())
#清空输出txt文件
def clean_list(filename):
    filename = download_path + filename
    print('× 清空txt数据 ===>'+filename)
    with open(filename, 'w', encoding='UTF-8') as f:
        f.truncate(0)
        f.close()

#多线程，按线程数分组
def creta_thread():
    lmax = len(idlist)
    remaider = lmax % int(max_dl)
    number = int(lmax / int(max_dl))
    offset = 0
    for i in range(int(max_dl)):
        if remaider > 0:
            t = threading.Thread(target=get_magnet, args=(i * number + offset, (i + 1) * number + offset + 1))
            remaider = remaider - 1
            offset = offset + 1
        else:
            t = threading.Thread(target=get_magnet, args=(i * number + offset, (i + 1) * number + offset))
        t.start()
        time.sleep(0.1)

#获取用户输出url，并简单判断合规
def input_url():
    print('例如：https://adult.contents.fc2.com/users/yamasha/articles?sort=date&order=desc')
    while True:
        url = input("请输入需要抓取番号的网页：")
        fc2url='https://adult.contents.fc2.com'
        if fc2url in url:
            # 若用户只输入了用户主页，自动补全为 articles 列表页
            try:
                if re.match(r'^https://adult\.contents\.fc2\.com/users/[^/]+/?$', url):
                    url = url.rstrip('/') + '/articles?sort=date&order=desc'
                    print('→ 已自动识别用户主页，改为作品列表页：' + url)
            except Exception:
                pass
            return url
            break
        else:
            print('× 输入有误,请输入正确的网址')
#菜单
def set_memu():
    running = True
    menu = """
     Main Menu  
--------------------
   1: 获取番号
   2: 获取磁力
   q: Quit
--------------------
"""
    global idlist
    while running:
        print(menu)
        cmd = str(input("请选择操作:"))
        if cmd != 'q':
            os.system('cls')
            try:
                #print(menu)
                if cmd != None:
                    if cmd == '1':
                        target_url=input_url()
                        get_fc2id(target_url)
                        continue
                    elif cmd == '2':
                        idlist = read_list('list.txt')
                        if idlist is not None or idlist!=[]:
                            clean_list('magnet.txt')
                            clean_list('no_magnet.txt')
                            clean_list('error.txt')
                            creta_thread()
                            while threading.active_count() != 1:
                                pass
                            else:
                                print('获取磁力完成，数据已存到' + download_path)

                        else:
                            print('× 没找到番号列表list.txt文件！请重新获取番号列表！')

                    else:
                        print('× 输入有误，清输入菜单指定字符!')
            except:
                print(menu)
        else:
            print('即将退出...')
            os.system('cls')
            sys.exit()

if __name__ == '__main__':
    (proxy, download_path, max_dl, max_retry, auto_proxy, verify_ssl) = read_config()
    # 若关闭证书校验，抑制不安全证书警告
    try:
        if not _is_true(verify_ssl):
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    except Exception:
        pass
    session = build_session(auto_proxy, proxy, max_retry)
    print_proxy_status(auto_proxy, proxy, session)

    parser = argparse.ArgumentParser(description='FC2 Gather Utility')
    parser.add_argument('--test-url', type=str, help='指定一个 URL 进行直测（跳过交互菜单）')
    parser.add_argument('--fetch-ids', type=str, help='指定一个 FC2 用户页面，直接抓取番号（跳过交互菜单）')
    parser.add_argument('--diagnose', action='store_true', help='运行网络诊断（直连/系统代理/端口探测）')
    args, unknown = parser.parse_known_args()

    if args.test_url:
        _test_single_url(args.test_url)
        sys.exit(0)

    if args.fetch_ids:
        get_fc2id(args.fetch_ids)
        sys.exit(0)

    if args.diagnose:
        diagnose_network([
            'https://adult.contents.fc2.com/users/sevenseeds/',
            'https://adult.contents.fc2.com/',
        ])
        sys.exit(0)

    target_url=''
    idlist = read_list("list.txt")
    mu = threading.Lock()
    set_memu()

