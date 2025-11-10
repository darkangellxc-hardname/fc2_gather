简介
=====
fc2_gather 是一个用于批量收集 FC2 影片番号并获取磁力链接的工具，支持图形界面（GUI）。已提供打包好的可执行文件 `dist/FC2Gather.exe`，也可直接运行源码。
<img src=https://github.com/supsupsuperstar/fc2_gather/raw/main/menu.png>

系统要求
====
- Windows 10/11（推荐）
- 网络可选代理（HTTP/SOCKS5）
- 运行源码时需要 Python 3.10+ 以及常用依赖（如 `requests`、`PySocks`、`tldextract` 等）

参数配置
====
具体设置见 `config.ini` 文件：

```
[下载设置]
proxy = 127.0.0.1:7897     ; 手动代理，支持 http/socks5（示例：http://127.0.0.1:7897 或 socks5://127.0.0.1:7897）
autoproxy = 是             ; 是否自动检测系统代理（是/否）
download_path = ./Downloads/ ; 下载与输出文件保存路径
max_dl = 2                  ; 同时处理的线程数（建议 2-4）
max_retry = 3               ; 网络异常时的重试次数
verifyssl = 否              ; 是否验证 SSL 证书（是/否）
```

缓存文件说明：
- `list.txt`：存储查找到的番号
- `magnet.txt`：存储获取到的磁力链接
- `no_magnet.txt`：存储未搜索到磁力的番号
- `error.txt`：存储因网络等问题导致搜索失败的番号

使用说明
====

1.获取番号列表
---------
登录 https://adult.contents.fc2.com/ 找到先要的卖家，使用网站的分类标签或者搜索功能筛选需要的影片<br>
<img src=https://github.com/supsupsuperstar/fc2_gather/raw/main/%E6%88%AA%E5%9B%BE1.png><br>
复制到工具运行，即可得到该页面分类下的所有的番号<br>
<img src=https://github.com/supsupsuperstar/fc2_gather/raw/main/%E6%88%AA%E5%9B%BE2.png>

<img src=https://github.com/supsupsuperstar/fc2_gather/raw/main/%E6%88%AA%E5%9B%BE3.png><br>
2.获取磁力
-----
自动从sukebei 上搜索list.txt内的所有番号，番号文件可自行增删改，当然你用来查找其他非FC2番号也行<br>

<img src=https://github.com/supsupsuperstar/fc2_gather/raw/main/%E6%88%AA%E5%9B%BE4.png>

运行方式
====
- 优先推荐：双击 `dist/FC2Gather.exe` 直接使用（无需安装 Python）
- 运行源码：在命令行执行 `python fc2_gui.py`（需 Python 环境）

打包脚本与放行
====
- 一键打包：在项目根目录执行 `./build_exe.ps1`
- 如遇到 PowerShell 执行策略限制，请先放行脚本：

```
# 放行当前用户级脚本签名（推荐，无需管理员权限）
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned

# 或仅本次执行放行（不改变全局策略）
powershell -ExecutionPolicy Bypass -File .\build_exe.ps1

# 如果脚本被标记为“来自互联网”，可解除阻止
Unblock-File .\build_exe.ps1
```

注意事项
=====
工具数据来源https://adult.contents.fc2.com/  https://sukebei.nyaa.si/ <br>
`请勿长时间、大批量、多线程使用本工具抓取数据，以免给服务器带来负担`<br>
国内用户获取磁力需要设置代理<br>

版本信息
=====
当前版本：v0.1（2025 年）

更新日志
=====
- v0.1：首次发布 GUI 版本并提供打包的 `FC2Gather.exe`


免责声明
=====
本应用仅用于爬虫技术交流学习，搜索结果均来自源站，不提供任何资源下载，亦不承担任何责任<br>
