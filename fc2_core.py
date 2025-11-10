# -*- coding:utf-8 -*-
"""
FC2资源收集器 - 核心功能模块
集成原有的fc2_gather功能到GUI
"""

import requests
import os
import sys
import time
import re
import threading
from configparser import RawConfigParser
from traceback import format_exc
from datetime import datetime

try:
    from pypac import PACSession
except Exception:
    PACSession = None

import urllib3
from urllib3.util.retry import Retry
from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse


class FC2GatherCore:
    """FC2资源收集核心功能类"""

    def __init__(self, config, log_callback=None):
        self.config = config
        self.log_callback = log_callback
        self.session = None
        self.is_running = False
        self.current_progress = 0
        self.total_items = 0

    def log(self, message):
        """日志输出"""
        if self.log_callback:
            self.log_callback(message)
        else:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] {message}")

    def read_config_value(self, section, key, default=''):
        """读取配置值"""
        try:
            return self.config.get(section, key)
        except Exception:
            return default

    def _is_true(self, val):
        """判断配置值是否为真"""
        if val is None:
            return False
        s = str(val).strip().lower()
        return s in ('是', 'yes', 'y', 'true', '1')

    def build_session(self):
        """构建HTTP会话"""
        auto_proxy = self.read_config_value('下载设置', 'AutoProxy', '是')
        manual_proxy = self.read_config_value('下载设置', 'Proxy', '否')
        max_retry = self.read_config_value('下载设置', 'Max_retry', '3')

        try:
            max_retry_int = int(max_retry)
        except Exception:
            max_retry_int = 3

        auto_enabled = self._is_true(auto_proxy)
        if auto_enabled and PACSession is not None:
            try:
                sess = PACSession()
            except Exception:
                sess = requests.Session()
        else:
            sess = requests.Session()

        # 禁止环境变量代理干扰，由 PAC 或手动代理控制
        sess.trust_env = False

        # 若启用手动代理，优先使用手动代理地址
        manual_enabled = bool(manual_proxy and manual_proxy.strip() != '否')
        if manual_enabled:
            addr = manual_proxy.strip()
            if not re.match(r'^[a-zA-Z]+://', addr):
                # 缺省协议补全为 http
                addr = 'http://' + addr
            sess.proxies = {
                'http': addr,
                'https': addr,
            }
        elif auto_enabled and PACSession is None:
            # 当AutoProxy开启但pypac不可用时，尝试使用系统环境代理(如称为“系统代理”)
            try:
                env_http = os.environ.get('HTTP_PROXY') or os.environ.get('http_proxy')
                env_https = os.environ.get('HTTPS_PROXY') or os.environ.get('https_proxy')
                if env_http or env_https:
                    sess.proxies = {
                        'http': env_http or env_https,
                        'https': env_https or env_http,
                    }
                    self.log('已从系统环境变量应用代理')
            except Exception:
                pass

        # 设置重试策略
        retry_strategy = Retry(
            total=max_retry_int,
            connect=max_retry_int,
            read=max_retry_int,
            backoff_factor=0.7,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"],
            raise_on_status=False,
            respect_retry_after_header=True,
        )
        adapter = requests.adapters.HTTPAdapter(max_retries=retry_strategy)
        sess.mount('http://', adapter)
        sess.mount('https://', adapter)

        self.session = sess
        if manual_enabled:
            self.log("HTTP会话创建完成（使用手动代理）")
        elif auto_enabled and PACSession is not None:
            self.log("HTTP会话创建完成（自动代理/PAC）")
            # 记录一次探测（非严格）
            try:
                ok = True
                self.log("PAC 会话已启用，实际代理将按系统/PAC规则动态选择")
            except Exception:
                pass
        else:
            self.log("HTTP会话创建完成（直连）")
        return sess

    def _browser_headers(self, url: str):
        """生成浏览器请求头"""
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

        # 针对FC2添加Referer
        if 'adult.contents.fc2.com' in url:
            headers['Referer'] = 'https://adult.contents.fc2.com/'
            headers['Origin'] = 'https://adult.contents.fc2.com'
        elif 'sukebei.nyaa.si' in url:
            headers['Referer'] = 'https://sukebei.nyaa.si/'
            headers['Origin'] = 'https://sukebei.nyaa.si'

        return headers

    def requests_web(self, url):
        """获取网页数据"""
        if not self.session:
            self.build_session()

        headers = self._browser_headers(url)
        timeout_seconds = 15
        max_retry = self.read_config_value('下载设置', 'Max_retry', '3')
        verify_ssl = self.read_config_value('下载设置', 'VerifySSL', '否')

        try:
            attempts = max(1, int(max_retry))
        except Exception:
            attempts = 1

        try:
            for i in range(attempts):
                try:
                    # 第一次使用 keep-alive，失败后切换为关闭连接，缓解某些站点的连接重置
                    req_headers = dict(headers)
                    if i > 0:
                        req_headers['Connection'] = 'close'

                    response = self.session.get(
                        url,
                        headers=req_headers,
                        timeout=timeout_seconds,
                        verify=self._is_true(verify_ssl),
                    )
                    response.encoding = 'utf-8'
                    return response.text
                except Exception as e:
                    # 针对常见网络错误给出更友好的提示
                    name = type(e).__name__
                    if name == 'ConnectionError':
                        self.log('连接错误：可能是地区限制、需要登录或站点防护。建议开启稳定代理（PAC/手动）并稍后重试。')
                    elif name == 'SSLError':
                        self.log('SSL连接异常：可在设置中关闭“验证SSL证书”后再试。')

                    if i == attempts - 1:
                        self.log(f'请求失败: {name}')
                        raise
                    backoff = min(2 ** i, 5)
                    self.log(f'第 {i+1}/{attempts} 次失败，{backoff}s后重试')
                    time.sleep(backoff)
        except Exception:
            # 代理失败时尝试直连
            self.log('尝试直连重试...')
            try:
                direct = requests.Session()
                direct.trust_env = False
                direct_headers = dict(headers)
                direct_headers['Connection'] = 'close'
                response = direct.get(
                    url,
                    headers=direct_headers,
                    timeout=timeout_seconds,
                    verify=self._is_true(verify_ssl),
                )
                response.encoding = 'utf-8'
                return response.text
            except Exception as e:
                self.log(f'直连也失败: {str(e)}')
                return None

    def fc2_get_current_page(self, txt):
        """获取当前页码"""
        pattern = re.compile('<span class="items" aria-selected="true">([0-9]*)</span>', re.S)
        keys = re.findall(pattern, txt or '')
        if keys:
            return int(keys[0])
        return 1

    def fc2_get_next_page(self, txt):
        """获取下一页"""
        pattern = re.compile('<span class="items" aria-selected="true">.*?</span>.*?<a data-pjx="pjx-container" data-link-name="pager".*?href=".*?&page=([0-9]*)" class="items">.*?<', re.S)
        keys = re.findall(pattern, txt or '')
        if keys:
            return int(keys[0])
        return 0

    def parse_fc2_id(self, text):
        """解析FC2番号"""
        pattern = re.compile(r'(?:FC2-PPV-)?(\d+)', re.IGNORECASE)
        matches = pattern.findall(text or '')
        return list(set(matches))  # 去重

    def _set_url_query_param(self, url, name, value):
        """设置或替换URL中的查询参数"""
        try:
            parsed = urlparse(url)
            qs = dict(parse_qsl(parsed.query, keep_blank_values=True))
            if value is None:
                qs.pop(name, None)
            else:
                qs[name] = str(value)
            new_query = urlencode(qs, doseq=True)
            return urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_query, parsed.fragment))
        except Exception:
            return url

    def detect_fc2_page_type(self, html, url):
        """检测FC2页面类型: 用户作品列表/搜索结果/作品详情/未知"""
        try:
            path = urlparse(url).path
        except Exception:
            path = ''
        page_type = 'unknown'
        if re.search(r'^/users/[^/]+/articles', path):
            page_type = 'user_articles'
        elif re.search(r'^/search/', path):
            page_type = 'search_results'
        elif re.search(r'^/article/\d+/?$', path):
            page_type = 'article_detail'

        # 进一步依据HTML中的结构进行校验
        try:
            if 'c-cntCard-110-f' in (html or ''):
                # 列表页通常包含卡片元素
                if page_type == 'unknown':
                    page_type = 'list_unknown'
        except Exception:
            pass

        return page_type

    def get_fc2_info(self, fc2_id):
        """获取FC2影片信息"""
        url = f"https://adult.contents.fc2.com/article/{fc2_id}/"

        try:
            self.log(f"正在获取番号 {fc2_id} 的信息...")
            html = self.requests_web(url)

            if not html:
                self.log(f"番号 {fc2_id}: 无法获取页面内容")
                return None

            info = {
                'id': fc2_id,
                'title': '',
                'magnet': '',
                'size': '',
                'date': '',
                'url': url,
            }

            title_pattern = re.compile(r'<h3[^>]*>([^<]+)</h3>', re.S)
            title_match = title_pattern.search(html or '')
            if title_match:
                info['title'] = title_match.group(1).strip()

            self.log(f"番号 {fc2_id}: 获取成功 - {info['title']}")
            return info

        except Exception as e:
            self.log(f"番号 {fc2_id}: 处理失败 - {str(e)}")
            return None

    def search_magnet_links(self, fc2_id):
        """搜索磁力链接（使用sukebei.nyaa.si）"""
        search_url = f"https://sukebei.nyaa.si/?f=0&c=0_0&q=FC2+PPV+{fc2_id}"

        try:
            self.log(f"正在搜索番号 {fc2_id} 的磁力链接...")
            html = self.requests_web(search_url)

            if not html:
                return []

            magnet_pattern = re.compile(r'magnet:\?[^"\'\s]+', re.S)
            magnets = magnet_pattern.findall(html)

            unique_magnets = list(set(magnets))
            self.log(f"番号 {fc2_id}: 找到 {len(unique_magnets)} 个磁力链接")

            return unique_magnets

        except Exception as e:
            self.log(f"搜索磁力链接失败: {str(e)}")
            return []

    def save_results(self, results, download_path):
        """保存结果到文件"""
        if not os.path.exists(download_path):
            os.makedirs(download_path)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        magnet_file = os.path.join(download_path, f"magnet_{timestamp}.txt")
        with open(magnet_file, 'w', encoding='utf-8') as f:
            for result in results:
                if result.get('magnets'):
                    for magnet in result['magnets']:
                        f.write(f"{magnet}\n")

        detail_file = os.path.join(download_path, f"details_{timestamp}.txt")
        with open(detail_file, 'w', encoding='utf-8') as f:
            for result in results:
                f.write(f"番号: {result['id']}\n")
                f.write(f"标题: {result['title']}\n")
                f.write(f"URL: {result['url']}\n")
                if result.get('magnets'):
                    f.write("磁力链接:\n")
                    for idx, magnet in enumerate(result['magnets']):
                        # 每条磁链独立一行，并在多条磁链之间增加空行便于辨识
                        f.write(f"  {magnet}\n")
                        if idx < len(result['magnets']) - 1:
                            f.write("\n")
                f.write("-" * 50 + "\n")

        self.log(f"结果已保存到: {download_path}")
        self.log(f"磁力链接: {magnet_file}")
        self.log(f"详细信息: {detail_file}")

    def process_fc2_list(self, input_data, progress_callback=None):
        """处理FC2番号列表"""
        self.is_running = True
        results = []

        try:
            if os.path.isfile(input_data):
                with open(input_data, 'r', encoding='utf-8') as f:
                    content = f.read()
                fc2_ids = self.parse_fc2_id(content)
                self.log(f"从文件读取到 {len(fc2_ids)} 个番号")
            else:
                fc2_ids = self.parse_fc2_id(input_data)
                self.log(f"从文本解析到 {len(fc2_ids)} 个番号")

            if not fc2_ids:
                self.log("未找到有效的FC2番号")
                return results

            self.total_items = len(fc2_ids)
            download_path = self.read_config_value('下载设置', 'Download_path', './Downloads/')

            for i, fc2_id in enumerate(fc2_ids):
                if not self.is_running:
                    break

                self.log(f"进度: {i+1}/{self.total_items}")

                info = self.get_fc2_info(fc2_id)
                if info:
                    magnets = self.search_magnet_links(fc2_id)
                    info['magnets'] = magnets
                    results.append(info)

                if progress_callback:
                    progress_callback((i + 1) / self.total_items * 100)

            if results:
                self.save_results(results, download_path)

            self.log(f"处理完成！共处理 {len(results)} 个番号")
            return results

        except Exception as e:
            self.log(f"处理过程出错: {str(e)}")
            self.log(format_exc())
            return results

    def stop(self):
        """停止处理"""
        self.is_running = False
        self.log("正在停止处理...")

    def parse_fc2_id_from_url(self, text):
        """从URL页面内容解析FC2番号"""
        ids = []
        try:
            pattern_card = re.compile(r'<div class="c-cntCard-110-f">.*?<a href="/article/(\d+)/"', re.S)
            ids.extend(re.findall(pattern_card, text or ''))
        except Exception:
            pass
        if not ids:
            try:
                pattern_any = re.compile(r'/article/(\d+)/')
                ids.extend(re.findall(pattern_any, text or ''))
            except Exception:
                pass
        seen = set()
        ordered = []
        for item in ids:
            if item not in seen:
                seen.add(item)
                ordered.append(item)
        return ordered

    def get_fc2_ids_from_url(self, url, progress_callback=None):
        """从FC2用户页面抓取所有番号"""
        self.log(f"开始从URL抓取番号: {url}")
        all_ids = []

        fc2url = 'https://adult.contents.fc2.com'
        if fc2url not in url:
            self.log("× 输入有误,请输入正确的FC2网址")
            return []

        try:
            if re.match(r'^https://adult\.contents\.fc2\.com/users/[^/]+/?$', url):
                url = url.rstrip('/') + '/articles?sort=date&order=desc'
                self.log('→ 已自动识别用户主页，改为作品列表页：' + url)
        except Exception:
            pass

        self.is_running = True
        i = 1
        n = 1
        page_count = 0

        while i <= n and self.is_running:
            try:
                # 规范化分页参数，避免简单字符串拼接导致URL异常
                page_url = self._set_url_query_param(url, 'page', i if i > 1 else None)

                self.log(f"正在获取第 {i} 页...")
                html = self.requests_web(page_url)

                if not html:
                    self.log(f"× 第 {i} 页获取失败，跳过")
                    break

                # 检测并记录页面类型
                page_type = self.detect_fc2_page_type(html, page_url)
                self.log(f"页面类型: {page_type}")

                page_ids = self.parse_fc2_id_from_url(html)
                self.log(f"第 {i} 页解析到 {len(page_ids)} 个番号")

                if page_ids:
                    all_ids.extend(page_ids)
                    preview = ", ".join(page_ids[:10])
                    suffix = ' ...' if len(page_ids) > 10 else ''
                    self.log(f'番号预览: {preview}{suffix}')
                else:
                    self.log('× 本页未解析到任何番号')

                current_page = self.fc2_get_current_page(html)
                next_page = self.fc2_get_next_page(html)
                self.log(f'当前页: {current_page}, 下一页: {next_page}')

                if next_page and next_page > i:
                    n = next_page
                    i += 1
                else:
                    break

                page_count += 1

                if progress_callback:
                    progress_callback(i, n, len(all_ids))

                time.sleep(1)

            except Exception as e:
                self.log(f"抓取第 {i} 页时出错: {str(e)}")
                break

        self.log(f"抓取完成！共获取 {len(all_ids)} 个番号，来自 {page_count} 页")

        download_path = self.read_config_value('下载设置', 'Download_path', './Downloads/')
        try:
            os.makedirs(download_path, exist_ok=True)
            list_file = os.path.join(download_path, 'list.txt')
            with open(list_file, 'w', encoding='utf-8') as f:
                for fc2_id in all_ids:
                    f.write(f"FC2-PPV-{fc2_id}\n")
            self.log(f"番号列表已保存到: {list_file}")
        except Exception as e:
            self.log(f"保存番号列表失败: {str(e)}")

        return all_ids


def main():
    """命令行主函数（保留占位）"""
    pass


if __name__ == "__main__":
    main()